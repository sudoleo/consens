"""Exercise audit guards with in-memory counterexamples; never rewrite evidence.

Run explicitly: python docs/test-coverage/product/probes/checker-self-check.py
This is an audit-tool check, not a product regression or coverage measurement.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_product_audit as checker
import render_product_audit as renderer
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import check_inventory as inventory_checker


def rejected(filename, change, diagnostic):
    original_read = checker.read
    modified = deepcopy(original_read(filename))
    change(modified)

    def read(name):
        return modified if name == filename else original_read(name)

    output = StringIO()
    with patch.object(checker, 'read', read), redirect_stdout(output):
        result = checker.main()
    if result != 1 or diagnostic not in output.getvalue():
        raise AssertionError(f'Counterexample was not rejected as expected: {diagnostic}\n{output.getvalue()}')
    print(f'OK: rejected {diagnostic}')


def remove_missing_line(data):
    file = next(f for f in data['files'].values() if f['missing_lines'])
    file['missing_lines'].pop()


def alter_probe_count(data):
    next(p for p in data['probes'] if p['id'] == 'M-01')['result']['passed'] += 1


def duplicate_route_id(data):
    data[1]['id'] = data[0]['id']


def move_assertion_anchor(data):
    evidence = next(c['representative_evidence'][0] for c in data['contracts'] if c['representative_evidence'])
    evidence['assertions'][0]['line'] -= 1


def main():
    if checker.main() != 0:
        raise AssertionError('Baseline audit must pass before testing counterexamples')
    rejected('python-coverage.json', remove_missing_line, 'Coverage detail/count mismatch:')
    rejected('execution.json', alter_probe_count, 'Probe result differs from JUnit: M-01')
    rejected('routes.json', duplicate_route_id, 'Duplicate route IDs')
    rejected('audit.json', move_assertion_anchor, 'Assertion starts on a different line:')
    rejected('audit.json', lambda data: data['contracts'][0]['representative_evidence'][0].update(end_line=1), 'Evidence definition end differs:')
    rejected('execution.json', lambda data: data['independent_review']['focused_result'].update(passed=1), 'Independent focused result differs from JUnit')

    # The earlier checker accepted internally plausible yet false test names,
    # ranges and assertion positions. Preserve concrete negative controls.
    if inventory_checker.main() != 0:
        raise AssertionError('Baseline inventory must pass')
    for name, change, diagnostic in (
        ('invented definition', lambda d: d.update(name='test_not_in_source'), 'Definition identity/location differs'),
        ('shortened definition', lambda d: d.update(end_line=d['end_line']-1), 'Definition identity/location differs'),
        ('moved assertion', lambda d: d['assertion_evidence'][0].update(line=d['line']), 'Assertion anchors differ'),
        ('omitted assertion', lambda d: d['assertion_evidence'].pop(), 'Assertion anchors differ'),
    ):
        modified = deepcopy(inventory_checker.read_inventory())
        change(modified['files'][0]['definitions'][0])
        output = StringIO()
        with patch.object(inventory_checker, 'read_inventory', lambda: modified), redirect_stdout(output):
            result = inventory_checker.main()
        if result != 1 or diagnostic not in output.getvalue():
            raise AssertionError(f'Inventory accepted {name}: {output.getvalue()}')
        print(f'OK: inventory rejects {name}')

    original_read = renderer.read
    modified = deepcopy(original_read('audit.json'))
    for package in modified['work_packages']:
        package['status'] = 'planned'
    modified['work_packages'][0]['status'] = 'blocked'
    with patch.object(renderer, 'read', lambda name: modified if name == 'audit.json' else original_read(name)):
        page = renderer.render()['work-packages.md']
    summary = f'{len(modified["work_packages"])-1} geplant, 1 blockiert'
    if summary not in page or 'Alle **30 Pakete sind geplant**' in page:
        raise AssertionError('Package summary must follow canonical status')
    print(f'OK: renderer reflects {summary} without writing files')


if __name__ == '__main__':
    main()
