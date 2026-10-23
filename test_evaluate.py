import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import evidenceops as app
import evaluate as ev


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.doc = app.load_corpus(app.ROOT / 'corpus.json')[2]
        self.case = {'id': 'timeout', 'tag': 'answerable', 'question': 'request timeout',
            'expected_status': 'answered', 'reference_answer': '30 seconds',
            'required_patterns': [r'30 seconds'], 'gold_evidence': [[{
                'doc_id': self.doc['id'], 'revision': self.doc['revision'], 'quote': 'request timeout is 30 seconds'}]]}
        self.unknown = {'id': 'unknown', 'tag': 'unanswerable', 'question': 'password',
            'expected_status': 'abstained', 'reference_answer': 'Unknown',
            'required_patterns': [], 'gold_evidence': []}
        draft = {'status': 'answered', 'claims': [{'text': 'The timeout is 30 seconds.',
            'evidence_id': self.doc['id'], 'quote': 'request timeout is 30 seconds'}]}
        self.result = {'status': 'answered', 'claims': app.validate_answer(draft, [self.doc]),
            'evidence': [self.doc], 'latency_ms': 10}
        self.refusal = {'status': 'abstained', 'claims': [], 'evidence': [], 'latency_ms': 20}

    def test_real_dataset_source_anchors(self):
        ev.validate_dataset(ev.read(ev.ROOT / 'eval/dev.json'), app.load_corpus())

    def test_exact_quote_and_offsets_pass(self):
        row = ev.check_case(self.case, self.result)
        self.assertTrue(row['citation_integrity'])
        self.assertEqual(row['gold_hits'], [True])

    def test_changed_offset_fails(self):
        self.result['claims'][0]['start'] += 1
        self.assertFalse(ev.check_case(self.case, self.result)['citation_integrity'])

    def test_wrong_revision_cannot_count_as_gold(self):
        self.result['evidence'][0]['revision'] = 'another-version'
        self.assertEqual(ev.check_case(self.case, self.result)['gold_hits'], [False])

    def test_missing_case_fails_aggregation(self):
        with self.assertRaises(ValueError):
            ev.aggregate([self.case, self.unknown], [ev.check_case(self.case, self.result)])

    def test_duplicates_fail_aggregation(self):
        row = ev.check_case(self.case, self.result)
        with self.assertRaises(ValueError):
            ev.aggregate([self.case, self.unknown], [row, row])

    def test_abstaining_everywhere_fails(self):
        rows = [ev.check_case(self.case, self.refusal), ev.check_case(self.unknown, self.refusal)]
        report = ev.aggregate([self.case, self.unknown], rows)
        self.assertEqual(report['metrics']['required_pattern_check_rate'], 0)
        self.assertEqual(report['metrics']['false_abstention_rate'], 1)
        self.assertIsNone(report['metrics']['citation_integrity_rate'])
        self.assertFalse(all(g['passed'] for g in ev.gates(report, {'citation_integrity_rate': {'min': 1},
            'false_abstention_rate': {'max': .1}})))

    def test_error_never_counts_as_abstention(self):
        self.refusal['status'] = 'error'
        row = ev.check_case(self.unknown, self.refusal)
        self.assertFalse(row['status_correct'])

    def test_boundary_threshold(self):
        report = {'metrics': {'score': .8}, 'semantic_judging_enabled': False}
        self.assertTrue(ev.gates(report, {'score': {'min': .8}})[0]['passed'])
        self.assertFalse(ev.gates(report, {'score': {'min': .81}})[0]['passed'])

    def test_nan_fails(self):
        report = {'metrics': {'score': float('nan')}, 'semantic_judging_enabled': False}
        self.assertFalse(ev.gates(report, {'score': {'min': 0}})[0]['passed'])

    def test_unknown_threshold_operator_fails(self):
        with self.assertRaises(ValueError):
            ev.gates({'metrics': {}, 'semantic_judging_enabled': False}, {'x': {'equal': 1}})

    def test_empty_gate_fails(self):
        with self.assertRaises(ValueError):
            ev.gates({'metrics': {}, 'semantic_judging_enabled': False}, {})

    def test_judge_timeout_fails_completeness(self):
        row = ev.check_case(self.case, self.result)
        ev.judge_case(self.case, self.result, row, Mock(side_effect=TimeoutError()))
        report = ev.aggregate([self.case, self.unknown], [row, ev.check_case(self.unknown, self.refusal)], True)
        outcomes = ev.gates(report, {'status_accuracy': {'min': 0}})
        self.assertEqual(outcomes[-1]['metric'], 'judge_completeness')
        self.assertFalse(outcomes[-1]['passed'])

    def test_reference_not_used_as_support_evidence(self):
        model = Mock(side_effect=[{'label': 'correct', 'reason': 'matches'},
            {'verdicts': [{'claim_index': 0, 'label': 'supported'}]}])
        ev.judge_case(self.case, self.result, ev.check_case(self.case, self.result), model)
        support_messages = str(model.call_args_list[1])
        self.assertNotIn('reference_answer', support_messages)
        self.assertNotIn('reviewed reference', support_messages)

    def test_changed_result_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [self.case, self.unknown]
            manifest = {'generation_complete': True, 'dataset_sha256': ev.sha(cases),
                'thresholds_sha256': ev.sha({}), 'case_hashes': {'timeout': ev.sha(self.result), 'unknown': ev.sha(self.refusal)}}
            ev.write(root / 'dataset.json', cases)
            ev.write(root / 'thresholds.json', {})
            ev.write(root / 'manifest.json', manifest)
            ev.write(root / 'cases/timeout.json', dict(self.result, question='tampered'))
            with self.assertRaises(ValueError):
                ev.load_run(root)

    def test_incomplete_generation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ev.write(root / 'dataset.json', [self.case])
            ev.write(root / 'manifest.json', {'generation_complete': False})
            with self.assertRaises(ValueError):
                ev.load_run(root)

    def test_gate_recomputes_instead_of_trusting_pass_label(self):
        cases = [self.case, self.unknown]
        rows = [ev.check_case(self.case, self.result), ev.check_case(self.unknown, self.result)]
        manifest = {'test': 'manifest'}
        report = {'rows': rows, 'generation_manifest_sha256': ev.sha(manifest),
            'scores_sha256': ev.sha(rows), 'semantic_judging_enabled': False,
            'gates': [{'passed': True}], 'metrics': {'status_accuracy': 1.0}}
        with patch('evaluate.load_run', return_value=(manifest, cases, {})), \
             patch('evaluate.read', side_effect=[report, {'status_accuracy': {'min': 1.0}}]), \
             patch('builtins.print'):
            self.assertEqual(ev.gate_run(Path('unused')), 1)


if __name__ == '__main__':
    unittest.main()
