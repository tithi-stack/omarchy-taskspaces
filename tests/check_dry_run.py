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
    print('CLI: taskspaces go --dry-run (mock compositor, no tasks)')
    result = case.run_task('go', '--dry-run')
    print(result.stdout)
    assert not case.state.exists()
    assert not (case.runtime / 'taskspaces.lock').exists()
    assert case.dispatches() == []
    assert case.events('omarchy-menu-select') == []
    case.state.mkdir()
    print('CLI: taskspaces send --dry-run with parked tasks (mock compositor)')
    case.parked()
    before = {p.name: p.read_bytes() for p in case.state.iterdir()}
    result = case.run_task('send', '--dry-run')
    print(result.stdout)
    assert 'name: Planning;' in result.stdout
    assert 'Started task "Planning"' in result.stdout
    assert before == {p.name: p.read_bytes() for p in case.state.iterdir()}
    assert case.dispatches() == []
    assert case.events('omarchy-menu-select') == []
    assert not (case.runtime / 'taskspaces.lock').exists()
    for path in case.state.iterdir():
        path.unlink()
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
    print('CLI: taskspaces send --dry-run (mock empty task)')
    case.empty_workspace()
    case.record()
    before = (case.state / '2.json').read_bytes()
    result = case.run_task('send', '--dry-run')
    print(result.stdout)
    assert 'Rename this task…' in result.stdout
    assert before == (case.state / '2.json').read_bytes()
    (case.state / '2.json').unlink()
    case.empty_workspace()
    print('CLI: taskspaces send --dry-run (mock empty numbered workspace)')
    result = case.run_task('send', '--dry-run')
    print(result.stdout)
    assert 'Turn this workspace into a task…' in result.stdout
    assert case.dispatches() == []
    assert case.events('omarchy-menu-select') == []
    # The earlier helper check uses mock input; the CLI must add no input calls.
    assert len(case.events('omarchy-menu-input')) == 1
    assert not (case.runtime / 'taskspaces.lock').exists()
    case.assert_no_effect()
    print('PASS: no real compositor called; dry paths dispatched nothing and wrote no task state or lock.')
finally:
    case.doCleanups()

from test_setup import SetupTests

case = SetupTests()
case.setUp()
try:
    print('CLI: taskspaces setup --dry-run with two keys (mock consent and compositor)')
    case.support_browser()
    case.cfg['choices'] = ['Yes']
    result = case.run_setup('--dry-run')
    print(result.stdout)
    assert ' send")' in result.stdout
    assert ' finish")' in result.stdout
    assert ' go")' not in result.stdout
    assert ' browser")' not in result.stdout
    assert 'send --silent' not in result.stdout
    case.unchanged()
    assert not (case.root / 'state').exists()
    print('PASS: consented setup preview wrote no bindings, backups or state and did not reload.')
    print('CLI: taskspaces setup --dry-run preserves existing block (mock compositor)')
    case.cfg['choices'] = ['Yes']
    case.run_setup()
    core = case.bindings.read_text()
    for backup in case.backups():
        backup.unlink()
    (case.root / 'events.jsonl').unlink()
    result = case.run_setup('--dry-run')
    print(result.stdout)
    assert 'Already set up' in result.stderr
    case.unchanged(core)
    print('PASS: re-running setup changed no bindings, wrote no backups and did not reload.')
finally:
    case.doCleanups()
