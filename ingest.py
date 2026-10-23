"""Pin and ingest an allowlisted FastAPI documentation snapshot. No dependencies."""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
VERSION = 'markdown-char-v1'
PAGES = [
    'first-steps.md', 'path-params.md', 'query-params.md', 'body.md',
    'query-params-str-validations.md', 'path-params-numeric-validations.md',
    'body-multiple-params.md', 'body-fields.md', 'body-nested-models.md',
    'extra-data-types.md', 'cookie-params.md', 'header-params.md',
    'response-model.md', 'response-status-code.md', 'handling-errors.md',
    'encoder.md', 'body-updates.md', 'middleware.md', 'cors.md', 'testing.md',
]
INCLUDE = re.compile(r'^\s*\{\*\s+(\S+)(?:\s+.*?)?\s*\*\}\s*$')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def safe_path(path):
    candidate = PurePosixPath(path)
    if '\\' in path or ':' in path or candidate.is_absolute() or '..' in candidate.parts:
        raise ValueError('Unsafe repository path: ' + path)
    if not path or path.startswith('.'):
        raise ValueError('Invalid repository path')
    return path


def download(url):
    request = Request(url, headers={'User-Agent': 'EvidenceOps-local-corpus/1.0'})
    with urlopen(request, timeout=30) as response:
        if response.geturl().split('/')[2] != url.split('/')[2]:
            raise ValueError('Unexpected download redirect')
        content = response.read(1_000_001)
    if len(content) > 1_000_000:
        raise ValueError('Source exceeds 1 MB limit')
    return content.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')


def include_target(value):
    # FastAPI's documentation directives use this known docs_src prefix.
    # Do not resolve arbitrary document-supplied filesystem paths or URLs.
    prefix = '../../docs_src/'
    if not value.startswith(prefix):
        raise ValueError('Unsupported include: ' + value)
    relative = safe_path(value[len(prefix):])
    if not relative.endswith(('.py', '.json', '.txt')):
        raise ValueError('Unsupported snippet type')
    return 'docs_src/' + relative


def expand_markdown(text, path, fetch):
    """Retain prose verbatim; expand code includes without executing them."""
    output, origins = [], []
    for number, line in enumerate(text.splitlines(), 1):
        match = INCLUDE.fullmatch(line)
        if match:
            snippet_path = include_target(match[1])
            snippet = fetch(snippet_path)
            if '{*' in snippet or '--8<--' in snippet:
                raise ValueError('Nested snippet include requires explicit support')
            fence = '`' * max(3, max([len(m.group()) + 1 for m in re.finditer(r'`+', snippet)] or [3]))
            output.append(fence + ('python' if snippet_path.endswith('.py') else 'text'))
            origins.append({'path': path, 'line': number, 'synthetic': True})
            for index, code_line in enumerate(snippet.splitlines(), 1):
                output.append(code_line)
                origins.append({'path': snippet_path, 'line': index, 'synthetic': False})
            output.append(fence)
            origins.append({'path': path, 'line': number, 'synthetic': True})
        else:
            if '{*' in line or '--8<--' in line or '{%' in line:
                raise ValueError('Unresolved directive in ' + path + ':' + str(number))
            output.append(line)
            origins.append({'path': path, 'line': number, 'synthetic': False})
    return '\n'.join(output) + '\n', origins


def make_chunks(text, doc_id, path, revision, origins, size=1800, overlap=200):
    if not 0 <= overlap < size or size < 100:
        raise ValueError('Invalid chunk configuration')
    title = next((line.lstrip('# ').strip() for line in text.splitlines() if line.startswith('# ')), path)
    result, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind('\n', start + size // 2, end)
            if boundary != -1:
                end = boundary + 1
        passage = text[start:end]
        first_line = text.count('\n', 0, start)
        last_line = text.count('\n', 0, end - 1)
        spans = []
        for origin in origins[first_line:last_line + 1]:
            if origin['synthetic']:
                continue
            if spans and spans[-1]['path'] == origin['path'] and spans[-1]['end_line'] + 1 == origin['line']:
                spans[-1]['end_line'] = origin['line']
            else:
                spans.append({'path': origin['path'], 'start_line': origin['line'], 'end_line': origin['line']})
        chunk_id = digest(f'{doc_id}:{revision}:{VERSION}:{start}:{end}')[:20]
        result.append({'id': chunk_id, 'doc_id': doc_id, 'title': title,
                       'source_url': f'https://github.com/fastapi/fastapi/blob/{revision}/{path}#L{spans[0]["start_line"]}' if spans and spans[0]['path'] == path else f'https://github.com/fastapi/fastapi/blob/{revision}/{path}',
                       'source_path': path, 'revision': revision, 'licence': 'MIT',
                       'kind': 'upstream_documentation', 'chunker_version': VERSION,
                       'document_start': start, 'document_end': end,
                       'source_spans': spans, 'text': passage, 'sha256': digest(passage)})
        if end == len(text):
            break
        next_start = max(start + 1, end - overlap)
        # Move overlap to a word boundary rather than splitting an identifier.
        while next_start < end and not text[next_start - 1].isspace():
            next_start += 1
        start = next_start
    return result


def ingest(root=ROOT, revision=None, offline=False):
    manifest_path = root / 'corpus' / 'manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else None
    if previous and revision and previous['revision'] != revision:
        raise ValueError('An existing snapshot is pinned. Use a fresh project copy for a revision change.')
    revision = revision or (previous['revision'] if previous else None)
    if revision is None:
        if offline:
            raise ValueError('Offline ingestion requires an existing manifest')
        revision = json.loads(download('https://api.github.com/repos/fastapi/fastapi/commits/master'))['sha']
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Revision must be a full 40-character commit SHA')
    sources = {}

    def fetch(path):
        safe_path(path)
        cache = root / 'corpus' / 'cache' / revision / path
        cache_root = (root / 'corpus' / 'cache').resolve()
        if not cache.resolve().is_relative_to(root.resolve()) or not cache.resolve().is_relative_to(cache_root):
            raise ValueError('Cache path escapes project')
        if cache.exists():
            text = cache.read_text(encoding='utf-8')
        else:
            if offline:
                raise ValueError('Missing cached source: ' + path)
            text = download(f'https://raw.githubusercontent.com/fastapi/fastapi/{revision}/{path}')
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(text, encoding='utf-8', newline='\n')
        expected = previous['sources'].get(path) if previous else None
        if expected and digest(text) != expected:
            raise ValueError('Cached source hash mismatch: ' + path)
        sources[path] = digest(text)
        return text

    licence = fetch('LICENSE')
    chunks, documents = [], []
    for name in PAGES:
        path = 'docs/en/docs/tutorial/' + name
        raw = fetch(path)
        text, origins = expand_markdown(raw, path, fetch)
        doc_id = 'fastapi:' + name[:-3]
        chunks.extend(make_chunks(text, doc_id, path, revision, origins))
        documents.append({'id': doc_id, 'source_path': path, 'text': text,
                          'sha256': digest(text), 'line_origins': origins})
        print('Prepared:', name, flush=True)
    # Retain explicitly fictional fixtures, not the old authored upstream summaries.
    fixtures = json.loads((root / 'corpus.json').read_text(encoding='utf-8'))
    for fixture in fixtures:
        if fixture['kind'] == 'fictional_test_fixture':
            chunks.append(dict(fixture, sha256=digest(fixture['text'])))
    manifest = {'repository': 'https://github.com/fastapi/fastapi', 'revision': revision,
                'pages': PAGES, 'chunker_version': VERSION, 'chunk_characters': 1800,
                'overlap_characters': 200, 'sources': dict(sorted(sources.items())),
                'fixture_sha256': digest(json.dumps(fixtures, sort_keys=True))}
    manifest['snapshot_sha256'] = digest(json.dumps(manifest, sort_keys=True))
    index = {'snapshot_sha256': manifest['snapshot_sha256'], 'chunks': chunks}
    index['chunks_sha256'] = digest(json.dumps(chunks, sort_keys=True))
    # Finish processing every document before publishing any new usable index.
    write_json(root / 'corpus' / 'cache' / 'normalised.json', documents)
    write_json(manifest_path, manifest)
    write_json(root / 'indexes' / 'corpus.json', index)
    licence_path = root / 'corpus' / 'LICENSE.fastapi.txt'
    licence_path.write_text(licence, encoding='utf-8')
    print(f'\nPinned revision: {revision}\nUpstream pages: {len(PAGES)}\nPassages including fixtures: {len(chunks)}')
    print('Saved: corpus/manifest.json and indexes/corpus.json')
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', help='Full commit SHA; first run defaults to current master, then pins it')
    parser.add_argument('--offline', action='store_true', help='Rebuild only from verified cached sources')
    args = parser.parse_args()
    try:
        ingest(revision=args.revision, offline=args.offline)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f'Ingestion failed: {error}\nNo new usable index was intentionally published.\n')


if __name__ == '__main__':
    main()
