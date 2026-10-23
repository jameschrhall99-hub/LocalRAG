import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import evidenceops as app


class RagTests(unittest.TestCase):
    def setUp(self):
        self.docs = app.load_corpus()
        self.doc = next(d for d in self.docs if d['id'] == 'demo-timeout-v1')
        self.draft = {'status': 'answered', 'claims': [{'text': 'The demo-v1 timeout is 30 seconds.',
            'evidence_id': self.doc['id'], 'quote': 'the request timeout is 30 seconds.'}]}

    def test_retrieval(self):
        self.assertEqual(app.retrieve('request timeout', self.docs)[0]['id'], self.doc['id'])

    def test_query_is_not_sql(self):
        self.assertIsInstance(app.retrieve('"; DROP TABLE passages; --', self.docs), list)

    def test_quote_offsets(self):
        claim = app.validate_answer(self.draft, [self.doc])[0]
        self.assertEqual(self.doc['text'][claim['start']:claim['end']], claim['quote'])

    def test_fabricated_id(self):
        self.draft['claims'][0]['evidence_id'] = 'invented'
        with self.assertRaises(ValueError):
            app.validate_answer(self.draft, [self.doc])

    def test_fabricated_quote(self):
        self.draft['claims'][0]['quote'] = 'timeout is 900 seconds'
        with self.assertRaises(ValueError):
            app.validate_answer(self.draft, [self.doc])

    def test_unselected_source(self):
        with self.assertRaises(ValueError):
            app.validate_answer(self.draft, [])

    def test_no_claims_in_abstention(self):
        self.draft['status'] = 'abstained'
        with self.assertRaises(ValueError):
            app.validate_answer(self.draft, [self.doc])

    def test_no_evidence_skips_model(self):
        model = Mock()
        result = app.answer_question('zyxwvunobibliography', self.docs, model)
        self.assertEqual(result['status'], 'abstained')
        model.assert_not_called()

    def test_full_answer_path(self):
        model = Mock(side_effect=[self.draft, {'verdicts': [{'claim_index': 0, 'label': 'supported'}]}])
        result = app.answer_question('request timeout', self.docs, model)
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(model.call_count, 2)

    def test_unsupported_claim_is_withheld(self):
        model = Mock(side_effect=[self.draft, {'verdicts': [{'claim_index': 0, 'label': 'insufficient'}]}])
        result = app.answer_question('request timeout', self.docs, model)
        self.assertEqual(result['status'], 'abstained')
        self.assertEqual(result['claims'], [])

    def test_verifier_timeout_is_error(self):
        model = Mock(side_effect=[self.draft, TimeoutError()])
        self.assertEqual(app.answer_question('request timeout', self.docs, model)['status'], 'error')

    def test_duplicate_verdicts_rejected(self):
        with self.assertRaises(ValueError):
            app.supported({'verdicts': [{'claim_index': 0, 'label': 'supported'}] * 2}, 2)

    def test_missing_verdict_is_error(self):
        model = Mock(side_effect=[self.draft, {'verdicts': []}])
        self.assertEqual(app.answer_question('request timeout', self.docs, model)['status'], 'error')

    def test_generation_timeout_is_error(self):
        self.assertEqual(app.answer_question('request timeout', self.docs, Mock(side_effect=TimeoutError()))['status'], 'error')

    def test_records_saved(self):
        result = app.answer_question('zyxwvunobibliography', self.docs)
        with tempfile.TemporaryDirectory() as directory:
            target = app.save_result(result, Path(directory))
            self.assertTrue(target.exists())
            self.assertIn('evidence', target.read_text())


if __name__ == '__main__':
    unittest.main()
