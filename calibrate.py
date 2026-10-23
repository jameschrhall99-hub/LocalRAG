"""Review judge labels and measure the exact current evaluator prompts."""
import argparse
import hashlib
import json
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import evidenceops as app
import evaluate as ev

ROOT = Path(__file__).resolve().parent
LABELS = {'support': ['supported', 'contradicted', 'insufficient'],
          'correctness': ['correct', 'incorrect']}


def validate(cases):
    if not cases or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Empty dataset or duplicate IDs')
    families = {}
    for case in cases:
        if case['task'] not in LABELS or case['proposed_label'] not in LABELS[case['task']]:
            raise ValueError('Invalid task or proposed label')
        if case['split'] not in ('calibration', 'validation'):
            raise ValueError('Invalid split')
        family = case['family']
        if family in families and families[family] != case['split']:
            raise ValueError('Family leaks across calibration and validation')
        families[family] = case['split']
        review = case['review']
        if review['status'] not in ('pending', 'approved'):
            raise ValueError('Invalid review status')
        if review['status'] == 'approved':
            if not review.get('reviewer', '').strip() or review.get('label') not in LABELS[case['task']]:
                raise ValueError('Approved case requires a named reviewer and a valid reviewed label')
        if case['task'] == 'support':
            if not case['claim'] or not case['evidence'] or not all(e['text'] for e in case['evidence']):
                raise ValueError('Missing support input')
        elif not all(case[k] for k in ('question', 'reference_answer', 'answer')):
            raise ValueError('Missing correctness input')
    for split in ('calibration', 'validation'):
        for task, labels in LABELS.items():
            subset = [c for c in cases if c['split'] == split and c['task'] == task]
            if {c['proposed_label'] for c in subset} != set(labels):
                raise ValueError('Each split/task must include every label')


def messages_and_schema(case):
    if case['task'] == 'correctness':
        return ([{'role': 'system', 'content': ev.JUDGE_PROMPT},
                 {'role': 'user', 'content': json.dumps({'question': case['question'],
                    'reference': case['reference_answer'], 'answer': [case['answer']]})}], ev.CORRECTNESS_SCHEMA)
    evidence = case['evidence']
    quote = evidence[0]['text']
    claim = {'text': case['claim'], 'evidence_id': evidence[0]['id'], 'quote': quote,
             'start': 0, 'end': len(quote), 'source_sha256': hashlib.sha256(quote.encode()).hexdigest()}
    return ([{'role': 'system', 'content': ev.SUPPORT_JUDGE_PROMPT},
             {'role': 'user', 'content': json.dumps({'claims': [claim], 'evidence': evidence})}], app.SUPPORT_SCHEMA)


def validate_sources(cases, corpus):
    for case in cases:
        if case['task'] != 'support':
            continue
        for source in case['evidence']:
            authentic = source.get('authentic_excerpt', source['text'])
            if not authentic or not any(p.get('doc_id', p['id']) == source['doc_id']
                    and p['revision'] == source['revision'] and authentic in p['text'] for p in corpus):
                raise ValueError('Source excerpt does not match pinned corpus: ' + case['id'])
            if source.get('synthetic_injection') and not source['text'].startswith(authentic):
                raise ValueError('Synthetic attack lost its authentic source prefix')


def predict(case, model=app.chat):
    messages, schema = messages_and_schema(case)
    raw = model(messages, schema)
    if case['task'] == 'support':
        app.supported(raw, 1)
        return raw['verdicts'][0]['label'], raw
    if not isinstance(raw, dict) or set(raw) != {'label', 'reason'} or raw['label'] not in LABELS['correctness'] or not isinstance(raw['reason'], str):
        raise ValueError('Malformed correctness judgment')
    return raw['label'], raw


def ratio(a, b):
    return a / b if b else None


def classification(rows, labels, bad_labels):
    if not rows:
        raise ValueError('Empty task results')
    matrix = {label: {prediction: 0 for prediction in labels + ['error']} for label in labels}
    for row in rows:
        if row['expected'] not in labels or row['prediction'] not in labels + ['error']:
            raise ValueError('Invalid result label')
        matrix[row['expected']][row['prediction']] += 1
    per_label = {}
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[gold][label] for gold in labels if gold != label)
        fn = sum(matrix[label][prediction] for prediction in labels + ['error'] if prediction != label)
        per_label[label] = {'precision': ratio(tp, tp + fp), 'recall': ratio(tp, tp + fn),
                            'f1': ratio(2 * tp, 2 * tp + fp + fn), 'cases': sum(matrix[label].values())}
    if not all(per_label[label]['cases'] for label in labels):
        raise ValueError('Task result is missing a required class')
    bad = [row for row in rows if row['expected'] in bad_labels]
    good_label = 'supported' if 'supported' in labels else 'correct'
    good = [row for row in rows if row['expected'] == good_label]
    return {'cases': len(rows), 'errors': sum(row['prediction'] == 'error' for row in rows),
            'accuracy': sum(row['prediction'] == row['expected'] for row in rows) / len(rows),
            'macro_f1': sum(per_label[label]['f1'] or 0 for label in labels) / len(labels),
            'bad_case_detection_recall': ratio(sum(row['prediction'] in bad_labels for row in bad), len(bad)),
            'false_acceptance_rate': ratio(sum(row['prediction'] == good_label for row in bad), len(bad)),
            'good_case_acceptance_recall': ratio(sum(row['prediction'] == good_label for row in good), len(good)),
            'per_label': per_label, 'confusion_matrix': matrix}


def assess(cases, rows, split, draft, thresholds):
    selected = [c for c in cases if c['split'] == split]
    if len(rows) != len(selected) or {r['id'] for r in rows} != {c['id'] for c in selected}:
        raise ValueError('Missing or duplicate judge results')
    lookup = {c['id']: c for c in selected}
    for row in rows:
        case = lookup[row['id']]
        if row['task'] != case['task'] or row['family'] != case['family'] or row['expected'] != case['review'].get('label', case['proposed_label']):
            raise ValueError('Results differ from the selected labels or tasks')
    if set(thresholds['minimums']) != {'macro_f1', 'bad_case_detection_recall', 'good_case_acceptance_recall'} or not all(
            type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in thresholds['minimums'].values()):
        raise ValueError('Invalid judge thresholds')
    approved = all(c['review']['status'] == 'approved' for c in selected)
    results = {}
    for task, labels in LABELS.items():
        task_rows = [r for r in rows if r['task'] == task]
        bad = ['contradicted', 'insufficient'] if task == 'support' else ['incorrect']
        results[task] = classification(task_rows, labels, bad)
    targets = []
    for task, metrics in results.items():
        for metric, minimum in thresholds['minimums'].items():
            value = metrics[metric]
            targets.append({'task': task, 'metric': metric, 'actual': value, 'minimum': minimum,
                            'passed': value is not None and math.isfinite(value) and value >= minimum})
        targets.append({'task': task, 'metric': 'errors', 'actual': metrics['errors'], 'maximum': 0,
                        'passed': metrics['errors'] == 0})
    targets_met = all(t['passed'] for t in targets)
    return {'split': split, 'draft_labels': draft, 'all_labels_human_approved': approved,
        'tasks': results, 'targets': targets, 'targets_met': targets_met,
        'validation_targets_met_with_reviewed_labels': split == 'validation' and not draft and approved and targets_met,
        'semantic_release_gates_enabled': False,
        'status': 'DRAFT_DIAGNOSTIC' if draft else ('REVIEWED_VALIDATION' if split == 'validation' else 'REVIEWED_CALIBRATION_ONLY')}


def review(path, split, reviewer, input_fn=input):
    cases = ev.read(path)
    validate(cases)
    for case in [c for c in cases if c['split'] == split and c['review']['status'] != 'approved']:
        print('\nCASE:', case['id'], '|', case['task'])
        print('Question:', case['question'])
        if case['task'] == 'support':
            print('Claim:', case['claim'])
            for source in case['evidence']:
                print('Evidence:', source['text'])
                print('Provenance:', source.get('doc_id'), source.get('revision'))
        else:
            print('Reference:', case['reference_answer'])
            print('Candidate answer:', case['answer'])
        print('Proposed label:', case['proposed_label'])
        print('Proposed rationale:', case['rationale'])
        print('Labels:', ', '.join(LABELS[case['task']]))
        while True:
            response = input_fn('Enter accepts after review; type another label, s to skip, or q to quit: ').strip()
            if response in ('q', 's') or response == '' or response in LABELS[case['task']]:
                break
            print('Please choose a listed label, s, q, or Enter.')
        if response == 'q':
            break
        if response == 's':
            continue
        label = response or case['proposed_label']
        notes = input_fn('Optional review notes: ').strip()
        case['review'] = {'status': 'approved', 'reviewer': reviewer, 'label': label,
                          'notes': notes, 'reviewed_utc': datetime.now(timezone.utc).isoformat()}
        ev.write(path, cases)
    remaining = sum(c['split'] == split and c['review']['status'] != 'approved' for c in cases)
    print(f'Pending {split} reviews: {remaining}. Progress is saved after each approval.')


def render_report(path, report, rows):
    lines = ['# Judge assessment', '', f"**Status: {report['status']}**", '',
        'The following targets assess judge agreement; semantic release gates remain disabled.', '',
        '| Task | Cases | Macro-F1 | Bad-case detection recall | Good-case acceptance recall | Errors |',
        '|---|---:|---:|---:|---:|---:|']
    for task, metrics in report['tasks'].items():
        lines.append(f"| {task} | {metrics['cases']} | {metrics['macro_f1']:.3f} | {metrics['bad_case_detection_recall']:.3f} | {metrics['good_case_acceptance_recall']:.3f} | {metrics['errors']} |")
    for task, metrics in report['tasks'].items():
        lines += ['', f'## {task}: confusion matrix', '', 'Rows are proposed/reviewed labels; columns are judge predictions.', '',
            '| Gold | ' + ' | '.join(LABELS[task] + ['error']) + ' |',
            '|---|' + '---:|' * (len(LABELS[task]) + 1)]
        for gold, predictions in metrics['confusion_matrix'].items():
            lines.append('| ' + gold + ' | ' + ' | '.join(str(predictions[p]) for p in LABELS[task] + ['error']) + ' |')
    lines += ['', '## Disagreements and errors', '']
    for row in rows:
        if row['prediction'] != row['expected']:
            lines.append(f"- {row['id']}: expected {row['expected']}, predicted {row['prediction']}.")
    lines += ['', '## Predeclared targets', '', '| Task | Metric | Actual | Required | Result |', '|---|---|---:|---|---|']
    for target in report['targets']:
        requirement = '>=' + str(target['minimum']) if 'minimum' in target else '<=' + str(target['maximum'])
        lines.append(f"| {target['task']} | {target['metric']} | {target['actual']} | {requirement} | {'MET' if target['passed'] else 'MISSED'} |")
    lines += ['', '## Limits', '',
        '- Draft labels were proposed by the assistant, not independently human reviewed.',
        '- Validation is blocked until human review; draft validation runs are not permitted.',
        '- Calibration and validation use disjoint claim families. This is judge validation, not a held-out RAG question benchmark.',
        '- Related examples within a family are correlated; counts are not independent observations.',
        '- Recorded API identity and prompt/schema hashes do not replace an exact model binary hash.',
        '- Thresholds were specified before this run. A failing diagnostic must not be made green by relabelling examples to match the judge.', '']
    path.write_text('\n'.join(lines), encoding='utf-8')


def run(dataset, split, draft, output, model=app.chat):
    cases = ev.read(dataset)
    validate(cases)
    validate_sources(cases, app.load_corpus())
    if split == 'validation' and draft:
        raise ValueError('Draft validation runs are blocked; review labels before validation')
    selected = [c for c in cases if c['split'] == split]
    if not draft and any(c['review']['status'] != 'approved' for c in selected):
        raise ValueError('Human review is pending. Use review, or --draft for calibration diagnostics only.')
    if output.exists():
        raise ValueError('Output folder already exists; use a fresh run')
    thresholds = ev.read(ROOT / 'eval/judge_thresholds.json')
    output.mkdir(parents=True)
    ev.write(output / 'dataset.json', selected)
    ev.write(output / 'thresholds.json', thresholds)
    manifest = {'split': split, 'draft': draft, 'dataset_sha256': ev.sha(selected),
        'thresholds_sha256': ev.sha(thresholds), 'judge_model_identity': ev.model_identity(),
        'prompts_sha256': ev.sha([ev.JUDGE_PROMPT, ev.SUPPORT_JUDGE_PROMPT]),
        'schemas_sha256': ev.sha([ev.CORRECTNESS_SCHEMA, app.SUPPORT_SCHEMA]),
        'runner_sha256': ev.sha(Path(__file__).read_bytes()), 'complete': False}
    ev.write(output / 'manifest.json', manifest)
    rows = []
    for index, case in enumerate(selected, 1):
        started = time.perf_counter()
        row = {'id': case['id'], 'task': case['task'], 'family': case['family'],
            'expected': case['review'].get('label', case['proposed_label']), 'prediction': 'error', 'raw': None}
        try:
            row['prediction'], row['raw'] = predict(case, model)
        except (ValueError, KeyError, IndexError, TypeError, OSError) as error:
            row['error_type'] = type(error).__name__
        row['latency_ms'] = round((time.perf_counter() - started) * 1000, 2)
        rows.append(row)
        ev.write(output / 'results.partial.json', rows)
        print(f"[{index}/{len(selected)}] {case['id']}: {row['prediction']} (proposed/reviewed: {row['expected']})", flush=True)
    report = assess(cases, rows, split, draft, thresholds)
    report['rows'] = rows
    manifest['complete'] = True
    manifest['results_sha256'] = ev.sha(rows)
    ev.write(output / 'manifest.json', manifest)
    report['manifest_sha256'] = ev.sha(manifest)
    ev.write(output / 'report.json', report)
    render_report(output / 'report.md', report, rows)
    print('Report:', output / 'report.md')
    print('Status:', report['status'], '| targets met:', report['targets_met'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['review', 'run'])
    parser.add_argument('--split', choices=['calibration', 'validation'], default='calibration')
    parser.add_argument('--reviewer', help='Your name/identifier; required for interactive human review')
    parser.add_argument('--draft', action='store_true', help='Calibration diagnostic using proposed labels; never certification')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    path = ROOT / 'eval/judge_cases.json'
    try:
        if args.action == 'review':
            if not args.reviewer or not args.reviewer.strip():
                parser.error('--reviewer is required for human review')
            review(path, args.split, args.reviewer)
            return 0
        output = args.out or ROOT / 'runs' / ('judge-' + uuid.uuid4().hex[:10])
        report = run(path, args.split, args.draft, output)
        if any(metrics['errors'] for metrics in report['tasks'].values()):
            return 2
        return 0 if args.draft or report['targets_met'] else 1
    except (ValueError, KeyError, TypeError, OSError) as error:
        print('Judge assessment incomplete:', error)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
