import json
import io
from contextlib import redirect_stdout
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import evidenceops
import ingest


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(redirect_stdout(io.StringIO()))

    def test_includes_preserve_code_origin(self):
        text, origins = ingest.expand_markdown('# Errors\n{* ../../docs_src/errors/demo.py hl[1] *}\n',
                                               'docs/en/docs/tutorial/errors.md', lambda _: 'raise HTTPException()\n')
        self.assertIn('```python\nraise HTTPException()\n```', text)
        self.assertEqual(origins[2]['path'], 'docs_src/errors/demo.py')
        self.assertEqual(origins[2]['line'], 1)

    def test_snippets_not_executed(self):
        text, _ = ingest.expand_markdown('{* ../../docs_src/a.py *}', 'doc.md', lambda _: 'raise RuntimeError("never execute")')
        self.assertIn('raise RuntimeError', text)

    def test_traversal_rejected(self):
        for path in ('../../docs_src/../../secret.py', 'https://example.com/file.py', '/tmp/a.py', '../../docs_src/C:\\a.py'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                ingest.include_target(path)

    def test_unresolved_directive_rejected(self):
        with self.assertRaises(ValueError):
            ingest.expand_markdown('prefix {* unknown *}', 'a.md', lambda _: '')

    def test_missing_snippet_fails(self):
        def fetch(_):
            raise OSError('missing')
        with self.assertRaises(OSError):
            ingest.expand_markdown('{* ../../docs_src/missing.py *}', 'a.md', fetch)

    def test_chunks_reconstruct_exact_spans(self):
        text = '# Title\n' + 'Example words for a paragraph.\n' * 40
        origins = [{'path': 'a.md', 'line': i + 1, 'synthetic': False} for i in range(len(text.splitlines()))]
        chunks = ingest.make_chunks(text, 'doc', 'a.md', 'a' * 40, origins, 200, 30)
        for chunk in chunks:
            self.assertEqual(chunk['text'], text[chunk['document_start']:chunk['document_end']])
            self.assertLessEqual(len(chunk['text']), 200)
            self.assertEqual(chunk['sha256'], ingest.digest(chunk['text']))
        covered = set()
        for chunk in chunks:
            covered.update(range(chunk['document_start'], chunk['document_end']))
        self.assertEqual(covered, set(range(len(text))))
        self.assertEqual(chunks, ingest.make_chunks(text, 'doc', 'a.md', 'a' * 40, origins, 200, 30))

    def test_invalid_chunk_configuration(self):
        with self.assertRaises(ValueError):
            ingest.make_chunks('text', 'a', 'a.md', 'a' * 40, [], 200, 200)

    def fixture_root(self, root):
        root.joinpath('corpus.json').write_text('[]', encoding='utf-8')
        def fake(url):
            if url.endswith('commits/master'):
                return json.dumps({'sha': 'a' * 40})
            if url.endswith('/LICENSE'):
                return 'MIT test licence\n'
            return '# Test\nA reproducible documentation passage.\n'
        return fake

    def test_ingestion_repeatable_and_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('ingest.download', side_effect=self.fixture_root(root)) as fetch:
                first = ingest.ingest(root)
                count = fetch.call_count
                second = ingest.ingest(root, offline=True)
                self.assertEqual(fetch.call_count, count)
                self.assertEqual(first, second)
            with patch.object(evidenceops, 'ROOT', root):
                self.assertTrue(evidenceops.load_corpus())

    def test_corrupt_cache_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('ingest.download', side_effect=self.fixture_root(root)):
                ingest.ingest(root)
            cached = root / 'corpus/cache' / ('a' * 40) / 'docs/en/docs/tutorial/body.md'
            cached.write_text('tampered', encoding='utf-8')
            with self.assertRaises(ValueError):
                ingest.ingest(root, offline=True)

    def test_corrupt_index_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('ingest.download', side_effect=self.fixture_root(root)):
                ingest.ingest(root)
            path = root / 'indexes/corpus.json'
            index = json.loads(path.read_text(encoding='utf-8'))
            index['chunks'][0]['text'] = 'changed'
            ingest.write_json(path, index)
            with patch.object(evidenceops, 'ROOT', root), self.assertRaises(ValueError):
                evidenceops.load_corpus()

    def test_unpinned_offline_run_rejected(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            ingest.ingest(Path(directory), offline=True)


if __name__ == '__main__':
    unittest.main()
