import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

from maturity_data import (BLACK_ROT_VIEW_PAIRS, CLASSES, REVISION, audit_prepared_classifier, cluster_records,
                           curate_dragon, dominant_fruit, fingerprint, load_black_rot, rebalance_classification_groups)
from prepare_two_stage_data import read_yolo_boxes
from train_two_stage import require_maturity_readiness, run

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import download_dragon_black_rot as download


class MaturityCurationTests(unittest.TestCase):
    def test_reviewed_rot_views_share_group_despite_different_filenames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for i, checksum in enumerate(BLACK_ROT_VIEW_PAIRS[0]):
                p = root / f'{i}.jpg'; Image.new('RGB', (96, 96), ['brown', 'orange'][i]).save(p)
                rows.append({'image': p.name, 'source_image': p.name, 'source_class': 'Black_Rot',
                             'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'source_sha256': checksum,
                             'group': f'dfmod:{i}'})
            (root/'import_report.json').write_text(json.dumps({'source_dataset': 'kpsywfwkrf/1', 'selected_images': 2}))
            (root/'import_manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            records, missing = load_black_rot(root)
            self.assertIsNone(missing)
            self.assertEqual(records[0]['original_group'], records[1]['original_group'])

    def test_nested_tip_is_not_an_independent_subject(self):
        boxes = [(0, .5, .5, .8, .8), (2, .6, .4, .05, .2)]
        self.assertEqual(dominant_fruit(boxes, (800, 800))[0], 0)

    def test_disjoint_and_tiny_subjects_are_quarantined(self):
        self.assertIsNone(dominant_fruit([(0, .3, .5, .5, .5), (2, .8, .5, .2, .2)], (800, 800))[0])
        self.assertIsNone(dominant_fruit([(1, .5, .5, .02, .02)], (800, 800))[0])

    def test_quality_label_is_not_promoted_to_rotten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, label = root / 'Defect_Dragon_Original_Data1.jpg', root / 'label.txt'
            Image.new('RGB', (128, 128), 'red').save(image)
            label.write_text('1 0.5 0.5 0.8 0.8\n')
            accepted, detector, report = curate_dragon([(image, label)], {1: 'Rotten'}, read_yolo_boxes,
                                                       root / 'missing', root / 'audit')
            self.assertEqual(accepted, [])
            self.assertEqual(len(detector), 1)
            self.assertEqual(report['quarantine_reasons']['quality_label_is_not_a_verified_maturity_label'], 1)

    def test_similar_images_with_conflicting_classes_are_quarantined(self):
        im = Image.new('RGB', (96, 96), 'green')
        records = [{'candidate_id': str(i), 'sha256': str(i), 'original_group': str(i),
                    'fingerprint': fingerprint(im), 'status': 'accepted', 'class_name': CLASSES[i]}
                   for i in range(2)]
        result = cluster_records(records)
        self.assertEqual(result['conflicting_candidates_quarantined'], 2)
        self.assertEqual(records[0]['group'], records[1]['group'])

    def test_rebalance_moves_groups_without_inventing_examples(self):
        groups = {str(i): [SimpleNamespace(class_name='early')] for i in range(156)}
        assignments = {str(i): 'train' if i < 101 else 'val' if i < 125 else 'calib' if i < 140 else 'test' for i in range(156)}
        result = rebalance_classification_groups(groups, assignments)
        self.assertEqual(set(result), set(groups))
        for split in ['val', 'calib', 'test']:
            self.assertGreaterEqual(sum(s == split for s in result.values()), 20)
        self.assertGreaterEqual(sum(s == 'train' for s in result.values()), 80)

    def test_decoded_duplicates_across_splits_fail_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for split in ['train', 'val', 'calib', 'test']:
                p = root / (split + '.png');Image.new('RGB', (80, 80), 'red').save(p)
                rows.append({'split': split, 'class_name': 'ripe', 'group': split, 'output_image': p.name})
            with (root / 'manifest.csv').open('w') as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
            result = audit_prepared_classifier(root, ['ripe'], {s: 1 for s in ['train', 'val', 'calib', 'test']})
            self.assertFalse(result['ready_for_training_trial'])
            self.assertIn('Identical decoded image crosses splits', result['failures'])

    def test_failed_audit_stops_training_before_model_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = {'data_revision': REVISION, 'stages': {'dragon_classifier': {
                'ready_for_training_trial': False, 'failures': ['Missing Rotten source groups']}}}
            (root / 'data_readiness.json').write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'Missing Rotten'):
                require_maturity_readiness(root, 'dragon')

    def test_detector_only_does_not_require_a_ready_classifier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = SimpleNamespace(dataset_root=root, project=root/'runs', skip_detector=False,
                                   skip_mango_classifier=True, skip_dragon_classifier=True)
            with patch('train_two_stage.validate_detector_dataset'), patch('train_two_stage.train_detector', return_value=root/'best.pt'), patch('train_two_stage.require_maturity_readiness') as gate:
                run(args)
                gate.assert_not_called()


class BlackRotImportTests(unittest.TestCase):
    def test_publisher_folders_exclude_balanced_copy(self):
        folders = [{'id': 'original', 'name': 'Dragon Fruit'},
                   {'id': 'balanced', 'name': 'Dragon Fruit Balanced'},
                   {'id': 'fruit', 'name': 'Fruit', 'parent_id': 'original'},
                   {'id': 'fruit-copy', 'name': 'Fruit', 'parent_id': 'balanced'},
                   {'id': 'rot', 'name': 'Black_Rot', 'parent_id': 'fruit'},
                   {'id': 'rot-copy', 'name': 'Black_Rot', 'parent_id': 'fruit-copy'}]
        self.assertEqual(download.original_black_rot_folder(folders), ('rot', 'Dragon Fruit/Fruit/Black_Rot'))
        row = {'filename': 'Black_Rot_1.jpg', 'id': 'file1', 'status': 'COMPLETED',
               'content_details': {'size': 100, 'download_url': 'https://example.org/image.jpg', 'sha256_hash': 'a'*64}}
        with patch.object(download, 'folder_files', side_effect=[[], [row]]), patch.object(download, 'api_json', return_value=folders):
            source = download.discover_source()
            self.assertEqual(source['transport'], 'individual_files')
            self.assertEqual(source['files'][0]['publisher_sha256'], 'a'*64)

    def test_direct_image_download_verifies_publisher_checksum(self):
        raw = b'fixture-bytes'
        row = {'name': 'Black_Rot/a.jpg', 'url': 'https://example.org/a.jpg', 'size': len(raw),
               'publisher_sha256': hashlib.sha256(raw).hexdigest()}
        with patch.object(download.subprocess, 'run', return_value=SimpleNamespace(stdout=raw)):
            self.assertEqual(download.download_file(row), (row, raw))
            row['publisher_sha256'] = '0'*64
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                download.download_file(row)

    def test_selects_only_original_fruit_rot(self):
        self.assertTrue(download.black_rot_member('Original/Fruit/Black_Rot/photo.jpg'))
        for name in ['Augmented/Fruit/Black_Rot/photo.jpg', 'Fruit/Fungi/photo.jpg', 'Stem/Black_Rot/photo.jpg']:
            self.assertFalse(download.black_rot_member(name))
        selected = download.choose_archive([{'filename': 'Original.zip'}, {'filename': 'Augmented.zip'}])
        self.assertEqual(selected['filename'], 'Original.zip')

    def test_local_archive_import_checks_count_and_preserves_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);archive_path = root/'fixture.zip'
            data = io.BytesIO();Image.new('RGB', (100, 100), 'brown').save(data, format='JPEG')
            with zipfile.ZipFile(archive_path, 'w') as archive:
                archive.writestr('Original/Fruit/Black_Rot/a.jpg', data.getvalue())
                archive.writestr('Original/Fruit/Black_Rot/b.jpg', data.getvalue())
                archive.writestr('Augmented/Fruit/Black_Rot/c.jpg', data.getvalue())
            with patch.object(download, 'EXPECTED_IMAGES', 2):
                download.import_images(root/'out', archive_path=archive_path)
                self.assertTrue(download.valid_import(root/'out'/download.NAME))
            with self.assertRaisesRegex(ValueError, 'Expected 675'):
                download.import_images(root/'wrong', archive_path=archive_path)
            self.assertFalse((root/'wrong'/download.NAME/'import_report.json').exists())


if __name__ == '__main__':
    unittest.main()
