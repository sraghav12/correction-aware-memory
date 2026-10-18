"""Offline evidence verification. No API access, credentials, or cam policy imports."""
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, 'Duplicate JSON key'
        result[key] = value
    return result


def normalized(value, key=None):
    if key in {'effective_at', 'effective_until'} and value is not None:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        assert date.utcoffset() == timedelta(0), 'Non-UTC timestamp'
        return date.isoformat(timespec='microseconds')
    if isinstance(value, dict):
        return {k: normalized(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return sorted(value) if key == 'source_ids' else [normalized(v) for v in value]
    return value


def same(actual, expected, key=None):
    return type(actual) is type(expected) and normalized(actual, key) == normalized(expected, key)


def verify_run(name, cases):
    directory = HERE / name
    requests = [json.loads(line) for line in (directory/'requests.jsonl').read_text().splitlines()]
    assert len(requests) == len(cases) == 50
    assert {r['observation_id'] for r in requests} == set(cases)
    registration = json.loads((directory/'registration.json').read_text())
    assert hashlib.sha256((directory/'requests.jsonl').read_bytes()).hexdigest() == registration['requests_sha256']
    policy_hash = json.loads((HERE/'anthropic-initial/registration.json').read_text())['system_prompt_sha256']
    for request in requests:
        body = request['body']
        if name == 'gemini-fallback':
            assert set(body) == {'model', 'max_tokens', 'messages', 'reasoning', 'response_format'}
            assert [m['role'] for m in body['messages']] == ['system', 'user']
            policy = body['messages'][0]['content']
        else:
            expected_keys = {'model', 'max_tokens', 'messages', 'system'}
            if name == 'anthropic-thinking-off':
                expected_keys |= {'thinking', 'output_config'}
            assert set(body) == expected_keys
            assert [m['role'] for m in body['messages']] == ['user']
            policy = body['system']
        assert all(set(m) == {'role', 'content'} for m in body['messages'])
        assert hashlib.sha256(policy.encode()).hexdigest() == policy_hash
        user = json.loads(body['messages'][-1]['content'])
        gold = cases[request['observation_id']]
        assert set(user) == {'observation', 'prior_versions', 'queries'}
        assert user['observation'] == gold['observation'] and user['prior_versions'] == gold['prior_versions']
        assert user['queries'] == [{k: cp[k] for k in ('effective_as_of', 'known_at')} for cp in gold['expected_checkpoints']]
    if name == 'anthropic-thinking-off':
        preflight = json.loads((directory/'token-preflight.json').read_text())
        assert len(preflight) == 50 and all(r.get('http_status') == 400 for r in preflight)
        assert {r['observation_id'] for r in preflight} == set(cases)
        assert all('credit balance is too low' in json.loads(r['error'])['error']['message'].lower() for r in preflight)
        assert not (directory/'responses.jsonl').exists()
        print(name + ': 50 credit-blocked token preflights; zero inference responses')
        return
    responses = [json.loads(line) for line in (directory/'responses.jsonl').read_text().splitlines()]
    assert len(responses) == 50 and {r['observation_id'] for r in responses} == set(cases)
    saved_rows = list(map(json.loads, (directory/'comparisons.jsonl').read_text().splitlines()))
    saved = {r['observation_id']: r for r in saved_rows}
    assert len(saved_rows) == len(saved) == 50 and set(saved) == set(cases)
    counts = Counter()
    action_matches = proposal_matches = checkpoint_matches = complete = 0
    for row in responses:
        oid = row['observation_id']
        gold = cases[oid]
        status = 'unresolved'
        result = None
        try:
            assert row.get('http_status') == 200
            data = row['response']
            if 'choices' in data:
                assert data['choices'][0]['finish_reason'] == 'stop'
                text = data['choices'][0]['message']['content']
            else:
                assert data['stop_reason'] == 'end_turn'
                text = ''.join(b['text'] for b in data['content'] if b['type'] == 'text')
            prediction = json.loads(text, object_pairs_hook=strict_object)
            assert set(prediction) == {'proposal', 'states', 'evidence_assessment', 'rationale', 'concerns'}
            assert set(prediction['proposal']) == set(gold['expected_proposal'])
            assert isinstance(prediction['concerns'], list) and isinstance(prediction['rationale'], str)
            assert prediction['evidence_assessment'] in {'consistent', 'inconsistent', 'uncertain'}
            states = prediction['states']
            assert len(states) == len(gold['expected_checkpoints'])
            for i, item in enumerate(states):
                assert set(item) == {'query_index', 'state'} and type(item['query_index']) is int and item['query_index'] == i
                assert set(item['state']) == set(gold['expected_checkpoints'][i]['expected'])
            action_match = prediction['proposal']['action'] == gold['expected_proposal']['action']
            proposal_match = all(same(prediction['proposal'][k], v, k) for k, v in gold['expected_proposal'].items())
            state_matches = [all(same(item['state'][k], v, k) for k, v in cp['expected'].items()) for item, cp in zip(states, gold['expected_checkpoints'])]
            status = 'mismatch' if not proposal_match or not all(state_matches) else ('unresolved' if prediction['concerns'] or prediction['evidence_assessment'] != 'consistent' else 'matched')
            result = (prediction, action_match, proposal_match, sum(state_matches))
        except (AssertionError, ValueError, KeyError, TypeError):
            pass
        if result is not None:
            prediction, action_match, proposal_match, matched = result
            assert prediction == saved[oid]['prediction'], 'Saved prediction differs from provider text'
            complete += 1
            action_matches += action_match
            proposal_matches += proposal_match
            checkpoint_matches += matched
        assert status == saved[oid]['comparison_status'], oid
        counts[status] += 1
    summary = json.loads((directory/'summary.json').read_text())
    assert dict(counts) == summary['comparison_counts']
    assert action_matches == summary['action_matches'] and proposal_matches == summary['full_proposal_matches']
    assert checkpoint_matches == summary['matched_checkpoints']
    assert complete == (18 if name == 'anthropic-initial' else 50)
    usages = [r['response']['usage'] for r in responses if r.get('http_status') == 200]
    assert sum(u.get('input_tokens', u.get('prompt_tokens', 0)) for u in usages) == summary['input_tokens']
    assert sum(u.get('output_tokens', u.get('completion_tokens', 0)) for u in usages) == summary['output_tokens']
    if name == 'gemini-fallback':
        assert sum(u.get('completion_tokens_details', {}).get('reasoning_tokens', 0) for u in usages) == 0
        assert abs(sum(u['cost'] for u in usages) - summary['provider_reported_cost_usd']) < 1e-12
    print(f'{name}: {complete}/50 complete; {action_matches}/50 actions; {proposal_matches}/50 proposals; {checkpoint_matches}/114 checkpoints; {dict(counts)}')


def main():
    manifest = json.loads((HERE/'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == expected, name
    packet = ROOT/'audits/pilot-seed11'
    assert hashlib.sha256((packet/'manifest.json').read_bytes()).hexdigest() == manifest['original_packet_manifest_sha256']
    original = json.loads((packet/'manifest.json').read_text())
    for name, expected in original['files'].items():
        assert hashlib.sha256((packet/name).read_bytes()).hexdigest() == expected, name
    cases = {r['observation']['observation_id']: r for r in map(json.loads, (packet/'events.jsonl').read_text().splitlines())}
    assert len(cases) == 50 and sum(len(c['expected_checkpoints']) for c in cases.values()) == 114
    for name in ('anthropic-initial', 'anthropic-thinking-off', 'gemini-fallback'):
        verify_run(name, cases)
    print(f'Verified {len(manifest["files"])} artifact hashes; original packet unchanged.')


if __name__ == '__main__':
    main()
