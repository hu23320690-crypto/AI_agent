"""Sealed component evaluation of report selectors; test requires P3 approval."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
GOLD_SLOTS = ('fields', 'unknown_fields', 'limited', 'full_report', 'target_month',
              'compare', 'comparison_month', 'knowledge_requested', 'unresolved_month')
METRIC_SLOTS = ('fields', 'unknown_fields', 'requested_field_order', 'target_month',
                'comparison_month', 'compare', 'scope', 'knowledge_requested',
                'unresolved_month')
ERROR_ORDER = ('dangerous', 'wrong_scope', 'safe_fail', 'other_error')
BUDGET_REASONS = frozenset({'model_budget', 'time_budget', 'context_budget'})


def _json_value(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _text(value):
    """Only the contract's whitespace/newline normalization, never synonyms."""
    return value.replace('\r\n', '\n').replace('\r', '\n').strip()


def _ordered(values):
    return list(dict.fromkeys(_text(value) for value in values))


def build_case_inputs(case, records):
    """Build authorized inputs without inspecting any gold or alias values.

    records is the trusted CSV loader's (user_id, YYYY-MM) -> section mapping.
    A successful row contributes only 效率/耗材; a not-found current lookup
    still supplies its requested month, but contributes no catalog fields.
    """
    from utils.report_intent import ReportIntent, valid_month
    from utils.report_render import record_fields

    catalog, fallback = [], None
    user_id = case['user_id']
    for lookup in case.get('lookups', []):
        month = lookup.get('month')
        if not valid_month(month):
            raise ValueError('Lookup month must be a valid YYYY-MM')
        phase = lookup.get('phase', 'current')
        if phase not in ('current', 'history'):
            raise ValueError('Lookup phase must be current or history')
        if phase == 'current':
            fallback = month
        record = records.get((user_id, month))
        if record is not None:
            catalog.extend(record_fields(record))
    previous = case.get('previous_intent')
    if previous is not None:
        if not isinstance(previous, dict):
            raise ValueError('previous_intent must be an object or null')
        previous = dict(previous)
        previous['fields'] = tuple(previous.get('fields', ()))
        previous = ReportIntent(**previous)
    history = case.get('history', [])
    if not isinstance(history, list) or any(not isinstance(text, str) for text in history):
        raise ValueError('history must contain only user text')
    if len(history) > 3 or sum(len(text.encode('utf-8')) for text in history) > 1024:
        raise ValueError('history exceeds SCORING limits')
    if not isinstance(case['query'], str):
        raise ValueError('query must be text')
    return {'query': case['query'], 'history_queries': tuple(history),
            'previous_intent': previous, 'known_fields': tuple(dict.fromkeys(catalog)),
            'fallback_month': fallback, 'today': date.fromisoformat(case['today'])}


def adapt_result(result, known_fields):
    """Adapt final selectors only. No question gold or aliases enter this path."""
    intent = result.intent
    scope = result.final_scope
    if scope not in ('only_listed', 'full_report', 'unspecified'):
        raise ValueError('Unknown final scope')
    full = scope == 'full_report'
    # Full + exclusions may have a remaining-field rendering list (even a
    # limited=True rendering guard). Its semantic requested lists stay empty.
    limited = False if full else scope == 'only_listed' or bool(intent.limited)
    order = _ordered(intent.fields) if limited else []
    catalog = set(known_fields)
    return {'fields': [field for field in order if field in catalog],
            'unknown_fields': [field for field in order if field not in catalog],
            'limited': limited, 'full_report': full, 'target_month': intent.target_month,
            'compare': bool(intent.compare), 'comparison_month': intent.comparison_month,
            'knowledge_requested': bool(result.knowledge_requested),
            'unresolved_month': bool(intent.unresolved_month),
            'requested_field_order': order,
            'excluded_fields': _ordered(result.final_excluded_fields)}


def _unknown_key(value):
    return ''.join(value.split())


def _alias_mapping(gold, aliases):
    """Question-local unknown equivalences, restricted to scoring."""
    unknown = _ordered(gold['unknown_fields'])
    mapping = {_unknown_key(value): value for value in unknown}
    if not unknown:
        return mapping  # Aliases never authorize or rename known fields.
    if isinstance(aliases, dict):
        for canonical, values in aliases.items():
            if canonical not in unknown:
                raise ValueError('Unknown aliases may name only gold unknown fields')
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise ValueError('Unknown alias values must be strings')
            for value in values:
                mapping[_unknown_key(value)] = canonical
    elif aliases:
        if (not isinstance(aliases, (list, tuple)) or len(unknown) != 1
                or any(not isinstance(value, str) for value in aliases)):
            raise ValueError('A flat unknown_aliases list requires one gold unknown field')
        for value in aliases:
            mapping[_unknown_key(value)] = unknown[0]
    return mapping


def score_case(prediction, gold, unknown_aliases=(), *, status='ok'):
    """Keep execution and semantics separate, then apply the fixed severity."""
    from utils.report_intent import valid_month

    if any(slot not in gold for slot in (*GOLD_SLOTS, 'requested_field_order')):
        raise ValueError('Gold must supply all nine slots and requested_field_order')
    for slot in ('limited', 'full_report', 'compare', 'knowledge_requested', 'unresolved_month'):
        if type(gold[slot]) is not bool:
            raise ValueError('Gold boolean slots must be actual booleans')
    aliases = _alias_mapping(gold, unknown_aliases)
    differences = {}
    raw = prediction or {}
    # Preserve original values/order even when set scoring or aliases accept
    # the result; semantic_differences below identifies scored failures.
    for slot in (*GOLD_SLOTS, 'requested_field_order'):
        if slot not in raw or raw.get(slot) != gold[slot] or type(raw.get(slot)) is not type(gold[slot]):
            differences[slot] = {'expected': gold[slot], 'actual': raw.get(slot)}
    expected = {**gold, 'fields': _ordered(gold['fields']),
                'unknown_fields': _ordered(gold['unknown_fields']),
                'requested_field_order': _ordered(gold['requested_field_order'])}
    actual = dict(raw)
    actual['fields'] = _ordered(raw.get('fields', ()))
    actual_unknown = _ordered(raw.get('unknown_fields', ()))
    actual['unknown_fields'] = list(dict.fromkeys(
        aliases.get(_unknown_key(value), _unknown_key(value)) for value in actual_unknown))
    expected['unknown_fields'] = [aliases[_unknown_key(value)] for value in expected['unknown_fields']]
    # Alias acceptance never changes a known-field position or classification.
    unknown_set = set(actual_unknown)
    actual['requested_field_order'] = [
        aliases.get(_unknown_key(value), _unknown_key(value)) if value in unknown_set else value
        for value in _ordered(raw.get('requested_field_order', ()))]
    expected_unknown = set(gold['unknown_fields'])
    expected['requested_field_order'] = [
        aliases[_unknown_key(value)] if value in expected_unknown else value
        for value in expected['requested_field_order']]
    slot_correct = {}
    for slot in METRIC_SLOTS:
        if slot == 'scope':
            slot_correct[slot] = (actual.get('limited') is gold['limited']
                                  and actual.get('full_report') is gold['full_report'])
        elif slot in ('fields', 'unknown_fields'):
            slot_correct[slot] = set(actual[slot]) == set(expected[slot])
        elif slot in ('compare', 'knowledge_requested', 'unresolved_month'):
            slot_correct[slot] = actual.get(slot) is gold[slot]
        else:
            slot_correct[slot] = actual.get(slot) == expected[slot]
    if prediction is None:
        slot_correct = dict.fromkeys(METRIC_SLOTS, False)
    flags = []
    extra_fields = set(actual['fields']) - set(expected['fields'])
    dangerous_month = any(valid_month(actual.get(slot)) and actual.get(slot) != gold[slot]
                          for slot in ('target_month', 'comparison_month'))
    if extra_fields or dangerous_month:
        flags.append('dangerous')
    if not slot_correct['scope']:
        flags.append('wrong_scope')
    missing_fields = set(expected['fields']) - set(actual['fields'])
    refused_month = any(valid_month(gold[slot]) and actual.get(slot) is None
                        for slot in ('target_month', 'comparison_month'))
    if missing_fields or refused_month or (actual.get('unresolved_month') is True
                                           and gold['unresolved_month'] is False):
        flags.append('safe_fail')
    semantic_correct = all(slot_correct.values())
    if not semantic_correct and any(not slot_correct[slot] for slot in (
            'unknown_fields', 'requested_field_order', 'compare', 'knowledge_requested')):
        flags.append('other_error')
    if not semantic_correct and not flags:
        flags.append('other_error')
    execution_ok = status == 'ok'
    if not execution_ok and not flags:
        flags.append('other_error')
    return {'pass': execution_ok and semantic_correct, 'execution_ok': execution_ok,
            'semantic_correct': semantic_correct, 'slot_correct': slot_correct,
            'differences': differences, 'raw_differences': differences,
            'semantic_differences': [slot for slot, correct in slot_correct.items() if not correct],
            'error_flags': flags,
            'severity': next((flag for flag in ERROR_ORDER if flag in flags), None)}


def nearest_rank(values, percentile):
    if not 0 < percentile <= 1:
        raise ValueError('percentile must be in (0, 1]')
    values = sorted(values)
    return values[math.ceil(percentile * len(values)) - 1] if values else None


def _aggregate(rows):
    count = len(rows)
    scores = [row['score'] for row in rows]
    conflicts, statuses, severities = Counter(), Counter(), Counter()
    for row in rows:
        conflicts.update(row.get('trace', {}).get('conflicts', ()))
        statuses[row['status']] += 1
        if row['score']['severity']:
            severities[row['score']['severity']] += 1
    fallback = sum(bool(row.get('trace', {}).get('fallback_reason')) for row in rows)
    budget = sum(row.get('trace', {}).get('fallback_reason') in BUDGET_REASONS for row in rows)

    def latency(selected):
        values = [row['wall_seconds'] for row in selected
                  if isinstance(row.get('wall_seconds'), (int, float))
                  and not isinstance(row['wall_seconds'], bool)
                  and math.isfinite(row['wall_seconds']) and row['wall_seconds'] >= 0]
        return {'count': len(values), 'missing_count': len(selected) - len(values),
                'p50': nearest_rank(values, .5), 'p95': nearest_rank(values, .95)}

    return {'planned_count': count, 'exact_count': sum(score['pass'] for score in scores),
            'exact_accuracy': sum(score['pass'] for score in scores) / count if count else None,
            'slot_accuracy': {slot: sum(score['slot_correct'][slot] for score in scores) / count
                              if count else None for slot in METRIC_SLOTS},
            'severity_counts': {flag: severities[flag] for flag in ERROR_ORDER},
            'execution_status_counts': dict(statuses),
            'execution_failure_count': sum(row['status'] != 'ok' for row in rows),
            'fallback_count': fallback, 'fallback_rate': fallback / count if count else None,
            'conflict_counts': dict(sorted(conflicts.items())),
            'budget_skip_count': budget, 'budget_skip_rate': budget / count if count else None,
            'extra_model_calls': sum(row.get('extra_model_calls', 0) for row in rows),
            'latency_seconds': {'all': latency(rows),
                                'successful': latency([row for row in rows if row['status'] == 'ok'])}}


def _repeat_metrics(repeats):
    extractors = {'exact_accuracy': lambda item: item['exact_accuracy'],
                  'dangerous': lambda item: item['severity_counts']['dangerous'],
                  'dangerous_count': lambda item: item['severity_counts']['dangerous'],
                  'fallback_count': lambda item: item['fallback_count'],
                  'fallback_rate': lambda item: item['fallback_rate'],
                  'budget_skip_count': lambda item: item['budget_skip_count'],
                  'budget_skip_rate': lambda item: item['budget_skip_rate'],
                  'extra_model_calls': lambda item: item['extra_model_calls']}
    for population in ('all', 'successful'):
        for rank in ('p50', 'p95'):
            extractors[f'latency_{population}_{rank}'] = (
                lambda item, population=population, rank=rank:
                item['latency_seconds'][population][rank])
    for slot in METRIC_SLOTS:
        extractors[f'slot_{slot}_accuracy'] = lambda item, slot=slot: item['slot_accuracy'][slot]
    for flag in ERROR_ORDER[1:]:
        extractors[flag] = lambda item, flag=flag: item['severity_counts'][flag]
    extractors['execution_failure_count'] = lambda item: item['execution_failure_count']
    result = {}
    for name, extract in extractors.items():
        values = [extract(item) for item in repeats]
        measured = [value for value in values if value is not None]
        result[name] = {'mean': statistics.mean(measured) if measured else None,
                        'worst': (min(measured) if name.endswith('accuracy') else max(measured))
                        if measured else None,
                        'measured_repeats': len(measured), 'missing_repeats': len(values) - len(measured)}
    return result


def _amended(case_id):
    return case_id in ('ID021', 'IT021')


def summarize_results(rows, *, mode=None, repeat=None, split=None):
    repeats = [{**_aggregate([row for row in rows if row['repeat'] == index]), 'repeat': index}
               for index in range(1, (repeat or max((row['repeat'] for row in rows), default=0)) + 1)]
    summary = {'mode': mode, 'split': split, 'repeat': len(repeats),
               'aggregate': _aggregate(rows), 'repeats': repeats,
               'repeat_metrics': _repeat_metrics(repeats),
               'latency_method': 'nearest-rank ceil(p*n), wall-clock seconds',
               'execution_note': 'Failed/skipped/invalid model attempts remain in every planned denominator.'}
    affected = [row for row in rows if _amended(row['case_id'])]
    if split == 'dev' and affected:
        summary['amendment_id021'] = {
            'reference': 'docs/plans/SCORING_AMENDMENT_01.md',
            'ids': sorted({row['case_id'] for row in affected}),
            'all_dev_denominator_preserved': True, 'used_for_prompt_tuning': False,
            'affected': _aggregate(affected),
            'excluding_affected': _aggregate([row for row in rows if not _amended(row['case_id'])])}
    return summary


@contextmanager
def _observe_intent():
    """Evaluation-owned raw records; production privacy-safe trace is unchanged."""
    from agent.intent import llm_parser, resolve
    observed = {'raw_response': None, 'raw_proposal': None, 'validation': None}
    parse_response, parse_turn, validate = (llm_parser.parse_proposal,
                                             resolve.parse_turn_intent, resolve.validate_proposal)

    def response(message):
        observed['raw_response'] = {'message_type': type(message).__name__,
                                    'content': _json_value(getattr(message, 'content', message)),
                                    'tool_calls': _json_value(getattr(message, 'tool_calls', ())),
                                    'invalid_tool_calls': _json_value(getattr(message, 'invalid_tool_calls', ())),
                                    'additional_kwargs': _json_value(getattr(message, 'additional_kwargs', {})),
                                    'response_metadata': _json_value(getattr(message, 'response_metadata', {})),
                                    'usage_metadata': _json_value(getattr(message, 'usage_metadata', None))}
        return parse_response(message)

    def proposal(*args, **kwargs):
        value = parse_turn(*args, **kwargs)
        observed['raw_proposal'] = _json_value(value)
        return value

    def validation(*args, **kwargs):
        value = validate(*args, **kwargs)
        observed['validation'] = _json_value(value)
        return value

    with ExitStack() as stack:
        stack.enter_context(patch.object(llm_parser, 'parse_proposal', response))
        stack.enter_context(patch.object(resolve, 'parse_turn_intent', proposal))
        stack.enter_context(patch.object(resolve, 'validate_proposal', validation))
        yield observed


def _execution_status(trace):
    reason = trace.get('fallback_reason')
    if reason == 'model_timeout':
        return 'timeout'
    return 'error' if reason else 'ok'


def evaluate_case(case, records, mode, *, repeat_index=1, resolver=None):
    from agent.intent.resolve import resolve_turn_intent
    from agent.runtime import CallTimeout, DeadlineExceeded, RunContext
    row = {'id': f"{case['id']}::r{repeat_index:03d}", 'case_id': case['id'],
           'repeat': repeat_index, 'mode': mode, 'status': 'error',
           'raw_response': None, 'raw_proposal': None, 'validation': None,
           'validated_proposal': None, 'final_intent': None, 'prediction': None,
           'trace': {}, 'extra_model_calls': 0}
    started, run = time.perf_counter(), None
    try:
        inputs = build_case_inputs(case, records)
        row['input_context'] = {'known_fields': list(inputs['known_fields']),
                                'fallback_month': inputs['fallback_month'],
                                'today': inputs['today'].isoformat(),
                                'previous_intent': _json_value(inputs['previous_intent']),
                                'history_count': len(inputs['history_queries'])}
        run = RunContext()
        with _observe_intent() as observed:
            try:
                result = (resolver or resolve_turn_intent)(**inputs, mode=mode, run=run)
            finally:
                row.update(observed)
        row.update(trace=_json_value(result.trace), final_intent=_json_value(result.intent),
                   final_scope=result.final_scope,
                   final_excluded_fields=list(result.final_excluded_fields),
                   validated_proposal=(row.get('validation') or {}).get('proposal'),
                   merged_proposal=_json_value(result.proposal),
                   prediction=adapt_result(result, inputs['known_fields']))
        row['status'] = _execution_status(result.trace)
        row['execution_reason'] = result.trace.get('fallback_reason')
    except Exception as exc:
        row.update(status='timeout' if isinstance(exc, (CallTimeout, DeadlineExceeded)) else 'error',
                   error_type=type(exc).__name__)
        # Error messages from inference or malformed input may quote text.
        # Keep a type/code only; raw model output has its dedicated evidence.
    finally:
        row['wall_seconds'] = time.perf_counter() - started
        if run is not None:
            row['extra_model_calls'] = run.counts.get('model', 0)
            row['runtime'] = run.snapshot()
    row['score'] = score_case(row['prediction'], _case_gold(case), case.get('unknown_aliases', ()),
                              status=row['status'])
    return row


def _case_gold(case):
    """The frozen dataset may place the tenth order annotation beside gold."""
    gold = dict(case['gold'])
    if 'requested_field_order' not in gold:
        gold['requested_field_order'] = case['requested_field_order']
    return gold


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def _dump(path, value):
    Path(path).write_bytes(_json_bytes(value))


def _jsonl_bytes(rows):
    return ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode('utf-8')


def model_identity():
    import yaml
    config = yaml.safe_load((ROOT / 'config/rag.yml').read_text(encoding='utf-8'))
    name = config['chat_model_name']
    host = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434').rstrip('/')
    if not host.startswith(('http://', 'https://')):
        host = 'http://' + host
    with urllib.request.urlopen(host + '/api/tags', timeout=10) as response:
        available = json.load(response)['models']
    matches = [item for item in available if item['name'] in (name, name + ':latest')]
    if len(matches) != 1 or not matches[0].get('digest'):
        raise RuntimeError('Configured intent model is unavailable or ambiguous')
    return {'configured_name': name, 'name': matches[0]['name'],
            'digest': matches[0]['digest'], 'ollama_host': host}


def _snapshot_identity(dataset, records_path, planned):
    """No frozen dataset manifest is read; snapshots bind the allowed input."""
    code_paths = [ROOT / 'app.py', ROOT / 'requirements-lock.txt']
    for directory in ('agent', 'rag', 'utils', 'model', 'prompts', 'config'):
        code_paths.extend(path for path in (ROOT / directory).rglob('*')
                          if path.suffix in ('.py', '.txt', '.yml', '.json', '.gz')
                          and '__pycache__' not in path.parts)
    code = {path.relative_to(ROOT).as_posix(): _digest(path)
            for path in sorted(set(code_paths)) if path.is_file()}
    evaluation_paths = ['evaluation/intent_eval.py', 'evaluation/INTENT_EVAL.md',
                        'evaluation/run.py', 'scripts/seal_evaluation_run.py',
                        'scripts/prepare_evaluation_variant.py',
                        'docs/plans/SCORING_AMENDMENT_01.md']
    scoring = dataset.parent / 'SCORING.md'
    if scoring.is_file():
        evaluation_paths.append(scoring.relative_to(ROOT).as_posix())
    evaluation = {name: _digest(ROOT / name) for name in evaluation_paths}
    source = {records_path.relative_to(ROOT).as_posix(): _digest(records_path)}
    planned_hash = hashlib.sha256(_jsonl_bytes(planned)).hexdigest()
    derived = {'version': 1, 'description': 'Derived per-repeat execution plan; not the frozen gold manifest.',
               'case_count': len(planned), 'dataset_sha256': planned_hash,
               'input_dataset_sha256': _digest(dataset), 'files': source}
    return {'code_sha256': code, 'evaluation_sha256': evaluation, 'source_sha256': source,
            'dataset_sha256': planned_hash,
            'dataset_manifest_sha256': hashlib.sha256(_json_bytes(derived)).hexdigest(),
            'input_dataset_sha256': _digest(dataset),
            'prompt_sha256': {name: value for name, value in code.items() if name.startswith('prompts/')},
            'configuration_sha256': {name: value for name, value in code.items() if name.startswith('config/')}}, derived


def _assert_identity(identity, dataset, records_path):
    for field in ('code_sha256', 'evaluation_sha256', 'source_sha256'):
        if any(_digest(ROOT / name) != expected for name, expected in identity[field].items()):
            raise RuntimeError('Evaluation inputs changed during execution')
    if _digest(dataset) != identity['input_dataset_sha256']:
        raise RuntimeError('Input dataset changed during execution')
    if model_identity() != identity['model_identity']['intent']:
        raise RuntimeError('Intent model identity changed during execution')


def _summary_markdown(summary):
    aggregate = summary['aggregate']
    lines = [f"# Intent component evaluation: {summary['mode']} / {summary['split']}", '',
             f"Planned records: {aggregate['planned_count']}; repeats: {summary['repeat']}.", '',
             '| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    def percent(value):
        return f'{value:.2%}' if value is not None else 'missing'
    def seconds(value):
        return f'{value:.4f}' if value is not None else 'missing'
    for item in summary['repeats']:
        latency = item['latency_seconds']
        lines.append(f"| {item['repeat']} | {percent(item['exact_accuracy'])} | "
                     f"{item['severity_counts']['dangerous']} | {percent(item['fallback_rate'])} | "
                     f"{seconds(latency['all']['p50'])} | {seconds(latency['all']['p95'])} | "
                     f"{seconds(latency['successful']['p95'])} |")
    lines.extend(['', '| Metric | Mean | Worst repeat |', '| --- | ---: | ---: |'])
    for name, values in summary['repeat_metrics'].items():
        render = percent if name.endswith('accuracy') or name.endswith('rate') else seconds
        lines.append(f"| {name} | {render(values['mean'])} | {render(values['worst'])} |")
    lines.extend(['', 'All planned records remain in denominators. Slot rates measure final semantic '
                  'selectors; overall passes additionally require execution success.', '',
                  'Severity: ' + json.dumps(aggregate['severity_counts'], ensure_ascii=False), '',
                  'Execution states: ' + json.dumps(aggregate['execution_status_counts'], ensure_ascii=False), '',
                  'Conflict counts: ' + json.dumps(aggregate['conflict_counts'], ensure_ascii=False), '',
                  f"Budget skips: {aggregate['budget_skip_count']}; extra model attempts: {aggregate['extra_model_calls']}.", '',
                  'Latency: nearest-rank ceil(p*n), all states and successful execution states separately. '
                  'Missing latency observations: ' + str(aggregate['latency_seconds']['all']['missing_count']) + '.'])
    amended = summary.get('amendment_id021')
    if amended:
        lines.extend(['', 'SCORING_AMENDMENT_01: ' + ', '.join(amended['ids']) +
                      ' is retained in the full dev denominator and reported separately; it is not used to tune prompts.', '',
                      'Affected: ' + json.dumps(amended['affected'], ensure_ascii=False), '',
                      'Excluding affected (auxiliary): ' + json.dumps(amended['excluding_affected'], ensure_ascii=False)])
    return '\n'.join(lines) + '\n'


def run_evaluation(dataset, split, mode, repeat, run_dir, *, p3_approved=False):
    """Fresh archive, sequential cases, complete repeats, automatic sealing."""
    import yaml
    from agent.intent.llm_parser import load_intent_config
    from scripts.seal_evaluation_run import result_sha256, seal_run
    from utils.records import load_records

    dataset, run_dir = Path(dataset).resolve(), Path(run_dir).resolve()
    _check_dataset_access(dataset, split, p3_approved)
    if run_dir.exists():
        raise FileExistsError('Result directory already exists; choose a new --run')
    # Read exactly --dataset, never infer cases/test or read its frozen manifest.
    cases = [json.loads(line) for line in dataset.read_text(encoding='utf-8-sig').splitlines()
             if line.strip()]
    cases = [case for case in cases if case.get('split') == split]
    if not cases or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Selected split must contain unique nonempty cases')
    for case in cases:
        if not isinstance(case['id'], str) or not case['id']:
            raise ValueError('Case IDs must be nonempty strings')
        score_case(None, _case_gold(case), case.get('unknown_aliases', ()), status='error')
    agent_config = yaml.safe_load((ROOT / 'config/agent.yml').read_text(encoding='utf-8'))
    records_path = (ROOT / agent_config['external_data_path']).resolve()
    records = load_records(str(records_path))
    planned = [{'id': f"{case['id']}::r{index:03d}", 'case_id': case['id'], 'repeat': index}
               for index in range(1, repeat + 1) for case in cases]
    identity, derived = _snapshot_identity(dataset, records_path, planned)
    identity.update(identity_version=1, model_identity={'intent': model_identity()}, mode=mode,
                    split=split, repeat=repeat, inference_concurrency=1,
                    intent_configuration={**asdict(load_intent_config()), 'mode': mode},
                    input_dataset_path=str(dataset),
                    input_dataset_snapshot='snapshot/input_dataset.jsonl',
                    started_at=datetime.now(timezone.utc).isoformat(), python=sys.version,
                    platform=platform.platform(), temperature=0,
                    definition='Final selector component evaluation; semantic reviews are deterministic scoring, not human reviews.')
    try:
        identity['git_commit'] = subprocess.check_output(
            ['git', '-c', f'safe.directory={ROOT.as_posix()}', 'rev-parse', 'HEAD'],
            cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        identity['git_commit'] = None
    run_dir.mkdir(parents=True, exist_ok=False)
    snapshot = run_dir / 'snapshot'
    snapshot.mkdir()
    for field in ('code_sha256', 'evaluation_sha256', 'source_sha256'):
        for name in identity[field]:
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
    (snapshot / 'input_dataset.jsonl').write_bytes(dataset.read_bytes())
    _dump(snapshot / 'dataset_manifest.json', derived)
    (run_dir / 'cases.jsonl').write_bytes(_jsonl_bytes(planned))
    _dump(run_dir / 'manifest.json', identity)
    started, rows, changed = time.perf_counter(), [], False
    with (run_dir / 'results.jsonl').open('x', encoding='utf-8', newline='\n') as output:
        for index in range(1, repeat + 1):
            for case in cases:
                row = None
                try:
                    if changed:
                        raise RuntimeError('Evaluation inputs previously changed')
                    _assert_identity(identity, dataset, records_path)
                    row = evaluate_case(case, records, mode, repeat_index=index)
                    _assert_identity(identity, dataset, records_path)
                except Exception as exc:
                    changed = True
                    if row is None:
                        row = {'id': f"{case['id']}::r{index:03d}", 'case_id': case['id'],
                               'repeat': index, 'mode': mode, 'trace': {}, 'prediction': None,
                               'wall_seconds': None, 'extra_model_calls': 0,
                               'raw_response': None, 'raw_proposal': None, 'validation': None,
                               'validated_proposal': None, 'final_intent': None}
                    row.update(status='error', error_type=type(exc).__name__,
                               execution_reason='input_identity_check_failed')
                    row['score'] = score_case(row['prediction'], _case_gold(case),
                                               case.get('unknown_aliases', ()), status='error')
                rows.append(row)
                output.write(json.dumps(row, ensure_ascii=False) + '\n')
                output.flush()
                print(f"{mode} {row['id']} {row['status']} pass={row['score']['pass']}", flush=True)
    summary = summarize_results(rows, mode=mode, repeat=repeat, split=split)
    _dump(run_dir / 'summary.json', summary)
    (run_dir / 'summary.md').write_text(_summary_markdown(summary), encoding='utf-8')
    reviews = [{'id': row['id'], 'task_pass': row['score']['pass'],
                'review_kind': 'deterministic_component_scoring', 'result_sha256': result_sha256(row)}
               for row in rows]
    (run_dir / 'reviews.jsonl').write_bytes(_jsonl_bytes(reviews))
    identity.update(finished_at=datetime.now(timezone.utc).isoformat(),
                    wall_seconds=time.perf_counter() - started)
    _dump(run_dir / 'manifest.json', identity)
    if _digest(snapshot / 'input_dataset.jsonl') != identity['input_dataset_sha256']:
        raise RuntimeError('Original dataset snapshot differs from declared input SHA256')
    seal_run(run_dir)
    print(json.dumps({'run': str(run_dir), 'sealed': True,
                      'exact_accuracy': summary['aggregate']['exact_accuracy']}, ensure_ascii=False))
    return 0 if not summary['aggregate']['execution_failure_count'] else 1


def _check_dataset_access(dataset, split, p3_approved):
    if split == 'test' and not p3_approved:
        raise ValueError('--split test requires --p3-approved')
    # Protect against accidental --split dev --dataset test/cases access.
    # This check uses paths only and never inventories protected directories.
    for name in ('intent_v1', 'intent_v1_r1'):
        protected = (ROOT / 'evaluation' / name).resolve()
        try:
            Path(dataset).resolve().relative_to(protected)
        except ValueError:
            continue
        if Path(dataset).resolve() != protected / f'{split}.jsonl':
            raise ValueError('Protected intent datasets require the matching standalone split JSONL')
    for name in ('intent_agent_v1', 'intent_agent_v1_r1'):
        try:
            Path(dataset).resolve().relative_to((ROOT / 'evaluation' / name).resolve())
        except ValueError:
            continue
        raise ValueError('Agent datasets are not component evaluation inputs')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--split', required=True, choices=('dev', 'test'))
    parser.add_argument('--mode', required=True, choices=('rule', 'llm_only', 'hybrid'))
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--run', required=True)
    parser.add_argument('--p3-approved', action='store_true')
    args = parser.parse_args(argv)
    # Approval is checked before opening the dataset, loading inference code,
    # reading gold or reserving a result directory.
    if args.split == 'test' and not args.p3_approved:
        parser.error('--split test requires --p3-approved')
    if args.repeat < 1:
        parser.error('--repeat must be a positive integer')
    dataset, run_dir = Path(args.dataset), Path(args.run)
    dataset = dataset if dataset.is_absolute() else ROOT / dataset
    run_dir = run_dir if run_dir.is_absolute() else ROOT / run_dir
    if run_dir.exists():
        parser.error('Result directory already exists; choose a new --run')
    try:
        _check_dataset_access(dataset, args.split, args.p3_approved)
        return run_evaluation(dataset, args.split, args.mode, args.repeat, run_dir,
                              p3_approved=args.p3_approved)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Intent evaluation failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
