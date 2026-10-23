"""Compare frozen development runs without modifying their results."""
import argparse
import json
from pathlib import Path
import evaluate as ev


def compare(baseline, candidate):
    old, old_cases, old_results = ev.load_run(baseline)
    new, new_cases, new_results = ev.load_run(candidate)
    for key in ('dataset_sha256', 'thresholds_sha256', 'corpus_sha256', 'evaluator_sha256'):
        if old[key] != new[key]:
            raise ValueError('Comparison inputs differ: ' + key)
    old_report, new_report = ev.read(baseline / 'report.json'), ev.read(candidate / 'report.json')
    if old_report['semantic_judging_enabled'] != new_report['semantic_judging_enabled']:
        raise ValueError('Semantic judging modes differ')
    if old_report['judge_prompt_sha256'] != new_report['judge_prompt_sha256']:
        raise ValueError('Judge prompts differ')
    if old_report['semantic_judging_enabled']:
        old_judge_ids = [m['id'] for m in (old_report.get('judge_model_identity') or {}).get('data', [])]
        new_judge_ids = [m['id'] for m in (new_report.get('judge_model_identity') or {}).get('data', [])]
        if not old_judge_ids or old_judge_ids != new_judge_ids:
            raise ValueError('Judge model API identities differ or unavailable')
    old_model_ids = [m['id'] for m in old['model_api_identity'].get('data', [])]
    new_model_ids = [m['id'] for m in new['model_api_identity'].get('data', [])]
    if not old_model_ids or old_model_ids != new_model_ids:
        raise ValueError('Generator model API identities differ or unavailable')
    changed, retrieval_changes = [], []
    for case in old_cases:
        key = case['id']
        before, after = old_results[key], new_results[key]
        if [p['id'] for p in before['evidence']] != [p['id'] for p in after['evidence']]:
            retrieval_changes.append(key)
        if before['status'] != after['status']:
            changed.append({'id': key, 'before': before['status'], 'after': after['status']})
    return {'baseline': str(baseline), 'candidate': str(candidate),
        'same_dataset_corpus_thresholds_evaluator': True,
        'pipeline_changed': old['pipeline_sha256'] != new['pipeline_sha256'],
        'retrieval_changes': retrieval_changes, 'status_changes': changed,
        'baseline_metrics': old_report['metrics'], 'candidate_metrics': new_report['metrics'],
        'baseline_gate_passed': all(g['passed'] for g in old_report['gates']),
        'candidate_gate_passed': all(g['passed'] for g in new_report['gates']),
        'limits': 'Development-set comparison, same uncalibrated judge; model file hashes not available. Latency is not a controlled benchmark.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    try:
        result = compare(args.baseline, args.candidate)
        print(json.dumps(result, indent=2))
        ev.write(args.candidate / 'comparison.json', result)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
