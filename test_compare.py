import unittest
from pathlib import Path
from unittest.mock import patch
import compare_runs


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.manifest = dict.fromkeys(('dataset_sha256', 'thresholds_sha256', 'corpus_sha256', 'evaluator_sha256', 'pipeline_sha256'), 'hash')
        self.manifest['model_api_identity'] = {'data': [{'id': 'model'}]}
        self.cases = [{'id': 'case'}]
        self.results = {'case': {'status': 'answered', 'evidence': [{'id': 'source'}]}}
        self.report = {'metrics': {}, 'gates': [{'passed': True}], 'semantic_judging_enabled': True,
            'judge_model_identity': {'data': [{'id': 'model'}]}, 'judge_prompt_sha256': 'rubric'}

    def run_comparison(self, manifest=None, results=None):
        loads = [(self.manifest, self.cases, self.results), (manifest or self.manifest, self.cases, results or self.results)]
        with patch('compare_runs.ev.load_run', side_effect=loads), patch('compare_runs.ev.read', side_effect=[self.report, self.report]):
            return compare_runs.compare(Path('baseline'), Path('candidate'))

    def test_matching_inputs(self):
        self.assertEqual(self.run_comparison()['retrieval_changes'], [])

    def test_changed_dataset_rejected(self):
        with self.assertRaises(ValueError):
            self.run_comparison(dict(self.manifest, dataset_sha256='other'))

    def test_changed_model_rejected(self):
        with self.assertRaises(ValueError):
            self.run_comparison(dict(self.manifest, model_api_identity={'data': [{'id': 'different'}]}))

    def test_retrieval_changes_reported(self):
        results = {'case': {'status': 'answered', 'evidence': [{'id': 'other'}]}}
        self.assertEqual(self.run_comparison(results=results)['retrieval_changes'], ['case'])


if __name__ == '__main__':
    unittest.main()
