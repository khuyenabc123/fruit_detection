import ast
import base64
import gzip
import hashlib
import json
import unittest
from pathlib import Path


class ColabBundleTests(unittest.TestCase):
    def test_notebook_contains_exact_current_helpers_and_valid_code(self):
        root = Path(__file__).resolve().parents[1]
        notebook = json.loads((root/'training/train_two_stage_colab.ipynb').read_text())
        constants = {}
        for cell in notebook['cells']:
            if cell['cell_type'] != 'code':
                continue
            code = ''.join(cell['source']);tree = ast.parse(code)
            if code.startswith('# STEP 1'):
                for node in tree.body:
                    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                        name = node.targets[0].id
                        if name in {'EMBEDDED_HELPERS_B64', 'HELPERS_SHA256'}:
                            constants[name] = ast.literal_eval(node.value)
        payload = gzip.decompress(base64.b64decode(constants['EMBEDDED_HELPERS_B64']))
        self.assertEqual(hashlib.sha256(payload).hexdigest(), constants['HELPERS_SHA256'])
        helpers = json.loads(payload)
        self.assertIn('training/maturity_data.py', helpers)
        self.assertIn('scripts/download_dragon_black_rot.py', helpers)
        for name, code in helpers.items():
            self.assertEqual(code, (root/name).read_text(), name + ': rerun scripts/embed_colab_helpers.py')


if __name__ == '__main__':
    unittest.main()
