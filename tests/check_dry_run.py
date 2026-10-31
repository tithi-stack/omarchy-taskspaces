#!/usr/bin/env python3
"""Show dry-run evidence using the same isolated fake compositor as the tests."""
from test_taskspaces import TaskTests

case = TaskTests()
case.setUp()
try:
    print('CLI: taskspaces send --dry-run (mock compositor)')
    case.state.rmdir()
    result = case.run_task('send', '--dry-run')
    print(result.stdout)
    assert not case.state.exists()
    assert not (case.runtime / 'taskspaces.lock').exists()
    assert case.dispatches() == []
    assert case.events('omarchy-menu-select') == []
    assert case.events('omarchy-menu-input') == []
    case.state.mkdir()
    print('In-place creation helper with dry=true (mock input and compositor)')
    result = case.run_task(code='source "$1"; dry=true; state_dir="$XDG_RUNTIME_DIR/taskspaces"; make_workspace_task 2 kitty')
    print(result.stdout)
    case.assert_no_effect()
    print('CLI: taskspaces finish --dry-run (mock in-place task)')
    record = case.record()
    before = (case.state / '2.json').read_bytes()
    result = case.run_task('finish', '--dry-run')
    print(result.stdout)
    assert case.dispatches() == []
    assert before == (case.state / '2.json').read_bytes()
    assert not (case.runtime / 'taskspaces.lock').exists()
    assert 'hl.dsp.focus' not in result.stdout
    print('PASS: no real compositor called; dry paths dispatched nothing and wrote no task state or lock.')
finally:
    case.doCleanups()

from test_setup import SetupTests

case = SetupTests()
case.setUp()
try:
    print('CLI: taskspaces setup --dry-run (mock consent and compositor)')
    result = case.run_setup('--dry-run')
    print(result.stdout)
    case.unchanged()
    assert not (case.root / 'state').exists()
    print('PASS: consented setup preview wrote no bindings, backups or state and did not reload.')
finally:
    case.doCleanups()
