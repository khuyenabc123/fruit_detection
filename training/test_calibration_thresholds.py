import json
import unittest

import numpy as np

from train_two_stage import choose_class_thresholds
from evaluate_orchard_pipeline import match_boxes


class CalibrationThresholdTests(unittest.TestCase):
    def test_serialization_preserves_accepted_near_one_confidence(self):
        confidence = 0.9999997868076128
        probabilities = np.array([[confidence, 1-confidence]] * 5)
        thresholds = choose_class_thresholds(probabilities, np.zeros(5, dtype=int), {0: 'rotten', 1: 'ripe'}, .8)
        restored = json.loads(json.dumps(thresholds))
        self.assertLess(restored['rotten'], 1.0)
        self.assertTrue(np.all(probabilities[:, 0] >= restored['rotten']))

    def test_ties_cannot_hide_errors_below_precision_target(self):
        probabilities = np.array([[.9, .1]] * 10)
        # An optimistic five-item prefix would meet the target, but a threshold
        # accepts all ten tied predictions, whose precision is only 50%.
        for labels in [np.array([0]*5+[1]*5), np.array([1]*5+[0]*5)]:
            thresholds = choose_class_thresholds(probabilities, labels, {0: 'early', 1: 'ripe'}, .8)
            self.assertEqual(thresholds['early'], 1.0)

    def test_matching_does_not_count_duplicate_or_wrong_species_boxes(self):
        truth = [{'species': 'mango', 'bbox': [0, 0, 10, 10]}]
        predictions = [dict(species=species, bbox=[0, 0, 10, 10], detection_confidence=confidence,
                            candidate_class='mango_early', uncertain=False)
                       for species, confidence in [('dragonfruit', .99), ('mango', .9), ('mango', .8)]]
        self.assertEqual(len(match_boxes(predictions, truth)), 1)
        self.assertEqual(match_boxes(predictions, []), [])


if __name__ == '__main__':
    unittest.main()
