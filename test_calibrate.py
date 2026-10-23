import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import calibrate as cal
import evaluate as ev
import evidenceops as app


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.cases = ev.read(cal.ROOT / 'eval/judge_cases.json')
        self.thresholds = ev.read(cal.ROOT / 'eval/judge_thresholds.json')

    def rows(self, split='calibration'):
        return [{'id': c['id'], 'task': c['task'], 'family': c['family'],
                 'expected': c['proposed_label'], 'prediction': c['proposed_label']}
                for c in self.cases if c['split'] == split]

    def test_source_checked_dataset(self):
        cal.validate(self.cases)
        cal.validate_sources(self.cases, app.load_corpus())
        self.assertEqual(sum(c['task'] == 'support' for c in self.cases), 60)
        self.assertEqual(sum(c['task'] == 'correctness' for c in self.cases), 20)

    def test_families_do_not_leak(self):
        self.cases[0]['split'] = 'validation'
        with self.assertRaises(ValueError):
            cal.validate(self.cases)

    def test_approval_requires_reviewer(self):
        self.cases[0]['review'] = {'status': 'approved', 'reviewer': '', 'label': 'supported'}
        with self.assertRaises(ValueError):
            cal.validate(self.cases)

    def test_fabricated_source_rejected(self):
        self.cases[0]['evidence'][0]['text'] = 'Fabricated source excerpt.'
        with self.assertRaises(ValueError):
            cal.validate_sources(self.cases, app.load_corpus())

    def test_ground_truth_not_sent_to_model(self):
        for case in self.cases:
            messages, _ = cal.messages_and_schema(case)
            text = json.dumps(messages)
            self.assertNotIn('proposed_label', text)
            self.assertNotIn('rationale', text)
            self.assertNotIn('reviewer', text)

    def test_shared_correctness_prompt(self):
        case = next(c for c in self.cases if c['task'] == 'correctness')
        messages, _ = cal.messages_and_schema(case)
        self.assertEqual(messages[0]['content'], ev.JUDGE_PROMPT)

    def test_shared_support_prompt(self):
        messages, _ = cal.messages_and_schema(self.cases[0])
        self.assertEqual(messages[0]['content'], ev.SUPPORT_JUDGE_PROMPT)

    def test_malformed_model_output_rejected(self):
        with self.assertRaises(ValueError):
            cal.predict(self.cases[0], Mock(return_value={'verdicts': []}))

    def test_perfect_predictions_do_not_approve_draft_labels(self):
        report = cal.assess(self.cases, self.rows(), 'calibration', True, self.thresholds)
        self.assertTrue(report['targets_met'])
        self.assertFalse(report['all_labels_human_approved'])
        self.assertFalse(report['validation_targets_met_with_reviewed_labels'])
        self.assertFalse(report['semantic_release_gates_enabled'])

    def test_missing_results_rejected(self):
        with self.assertRaises(ValueError):
            cal.assess(self.cases, self.rows()[:-1], 'calibration', True, self.thresholds)

    def test_changed_expected_label_rejected(self):
        rows = self.rows()
        rows[0]['expected'] = 'contradicted'
        with self.assertRaises(ValueError):
            cal.assess(self.cases, rows, 'calibration', True, self.thresholds)

    def test_errors_reduce_scores_and_fail_targets(self):
        rows = self.rows()
        for row in rows:
            row['prediction'] = 'error'
        report = cal.assess(self.cases, rows, 'calibration', True, self.thresholds)
        self.assertEqual(report['tasks']['support']['macro_f1'], 0)
        self.assertFalse(report['targets_met'])

    def test_missing_class_cannot_pass(self):
        with self.assertRaises(ValueError):
            cal.classification([{'expected': 'supported', 'prediction': 'supported'}], cal.LABELS['support'], ['contradicted', 'insufficient'])

    def test_bad_cases_accepted_are_detected(self):
        rows = [{'expected': label, 'prediction': 'supported'} for label in cal.LABELS['support']]
        metrics = cal.classification(rows, cal.LABELS['support'], ['contradicted', 'insufficient'])
        self.assertEqual(metrics['false_acceptance_rate'], 1)
        self.assertEqual(metrics['bad_case_detection_recall'], 0)

    def test_draft_validation_blocked_without_model_call(self):
        model = Mock()
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            cal.run(cal.ROOT / 'eval/judge_cases.json', 'validation', True, Path(directory) / 'new', model)
        model.assert_not_called()

    def test_unreviewed_normal_run_blocked(self):
        model = Mock()
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            cal.run(cal.ROOT / 'eval/judge_cases.json', 'calibration', False, Path(directory) / 'new', model)
        model.assert_not_called()

    def test_review_saves_only_human_confirmed_case(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.json'
            ev.write(path, self.cases)
            answers = iter(['', 'Checked source and meaning.', 'q'])
            with patch('builtins.print'):
                cal.review(path, 'calibration', 'human-reviewer', lambda _: next(answers))
            saved = ev.read(path)
            self.assertEqual(saved[0]['review']['status'], 'approved')
            self.assertEqual(saved[0]['review']['reviewer'], 'human-reviewer')
            self.assertTrue(all(c['review']['status'] == 'pending' for c in saved[1:]))


if __name__ == '__main__':
    unittest.main()
