#!/usr/bin/env python3
"""Run the real shell functions and CLI against fake Hyprland and menu executables only."""
import copy
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / 'bin' / 'taskspaces'
BASH = shutil.which('bash')
REQUIRED = ('hyprctl', 'jq', 'python3', 'flock', 'omarchy-menu-select', 'omarchy-menu-input')
TOOLS = ('chmod', 'date', 'mkdir', 'mv', 'rm')
MOCKED = ('hyprctl', 'omarchy-menu-select', 'omarchy-menu-input', 'omarchy-notification-send', 'notify-send')

MOCK = r'''#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path
root = Path(os.environ['MOCK_ROOT'])
cfgpath = root / 'config.json'
cfg = json.loads(cfgpath.read_text())
cmd, args = Path(sys.argv[0]).name, sys.argv[1:]
with (root / 'events.jsonl').open('a') as out:
    out.write(json.dumps([cmd, args]) + '\n')
def save(): cfgpath.write_text(json.dumps(cfg))
if cmd == 'hyprctl':
    if args[0] in ('workspaces', 'clients', 'activewindow', 'activeworkspace'):
        if args[0] == 'clients' and 'polls_since_close' in cfg:
            cfg['polls_since_close'] += 1
            if cfg.get('close_after_polls') == cfg['polls_since_close']:
                cfg['clients'] = []
            save()
        print(json.dumps(cfg[args[0]]))
    elif args[0] == 'dispatch':
        dsp = args[1]
        if cfg.get('dispatch_error'):
            print('mock dispatcher failure')
            sys.exit(0)
        if dsp.startswith(('hl.dsp.window.move', 'hl.dsp.window.close')):
            addr = re.search(r'address:(0x[0-9a-f]+)', dsp)[1]
            if cfg.get('vanish_on_dispatch') == addr:
                cfg['clients'] = [w for w in cfg['clients'] if w['address'] != addr]
                save()
            if not any(w['address'] == addr for w in cfg['clients']):
                print('window not found')
                sys.exit(0)
        if dsp.startswith('hl.dsp.window.move'):
            dest = int(re.search(r'workspace = "([0-9]+)"', dsp)[1])
            if not any(w['id'] == dest for w in cfg['workspaces']):
                cfg['workspaces'].append({'id': dest, 'name': str(dest)})
            for w in cfg['clients']:
                if w['address'] == addr:
                    w['workspace'] = dict(next(workspace for workspace in cfg['workspaces'] if workspace['id'] == dest))
        if dsp.startswith('hl.dsp.workspace.rename'):
            workspace_id, name = map(json.loads, re.search(r'workspace = ("(?:\\.|[^"\\])*"), name = ("(?:\\.|[^"\\])*")', dsp).groups())
            for w in cfg['workspaces']:
                if w['id'] == int(workspace_id): w['name'] = name
        if dsp.startswith('hl.dsp.window.close'):
            cfg['polls_since_close'] = 0
        if dsp.startswith('hl.dsp.window.close') and not cfg.get('refuse_close'):
            addr = re.search(r'address:(0x[0-9a-f]+)', dsp)[1]
            cfg['clients'] = [w for w in cfg['clients'] if w['address'] != addr]
            if cfg.get('remove_empty_workspace'):
                cfg['workspaces'] = [w for w in cfg['workspaces'] if w['id'] != cfg['activeworkspace']['id']]
        save()
        print('ok')
    else: raise RuntimeError(args)
elif cmd == 'omarchy-menu-select':
    if cfg.get('select_cancel'): sys.exit(1)
    cfg.update(cfg.get('menu_updates', {}))
    for record in cfg.get('menu_records', []):
        (root / 'runtime' / 'taskspaces' / f'{record["id"]}.json').write_text(json.dumps(record))
    save()
    print(cfg.get('selection', 'Cancel'))
elif cmd == 'omarchy-menu-input':
    cfg.update(cfg.get('input_updates', {}))
    if cfg.get('input_state'):
        state = root / 'runtime' / 'taskspaces' / '2.json'
        state.write_text(json.dumps(cfg['input_state']))
    save()
    if cfg.get('input_cancel'): sys.exit(1)
    print(cfg.get('input', 'Planning'))
elif cmd not in ('omarchy-notification-send', 'notify-send'): raise RuntimeError(cmd)
'''


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='taskspaces-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir()
        self.state = self.runtime / 'taskspaces'
        self.state.mkdir()
        self.mock = self.root / 'mock'
        self.mock.write_text(MOCK)
        self.mock.chmod(0o755)
        bindir = self.root / 'bin'
        bindir.mkdir()
        for command in MOCKED:
            (bindir / command).symlink_to(self.mock)
        self.env = dict(os.environ, MOCK_ROOT=str(self.root), XDG_RUNTIME_DIR=str(self.runtime),
                        PATH=str(bindir) + os.pathsep + os.environ['PATH'])
        win = {'address': '0xabc', 'class': 'kitty', 'title': 'Planning', 'mapped': True,
               'workspace': {'id': 2, 'name': '2'}}
        self.cfg = {'workspaces': [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'}],
                    'activewindow': win, 'clients': [win], 'activeworkspace': {'id': 2, 'name': '2'},
                    'selection': 'Turn workspace 2 into a task…\twindows stay where they are'}
        self.write_cfg()

    def write_cfg(self):
        (self.root / 'config.json').write_text(json.dumps(self.cfg))

    def isolated_path(self, name, commands):
        """A PATH directory holding only `commands`: mocks for Hyprland and menus, real tools otherwise."""
        path = self.root / name
        path.mkdir()
        for command in commands:
            target = self.mock if command in MOCKED else shutil.which(command)
            (path / command).symlink_to(target)
        return str(path)

    def run_task(self, *args, env=None, code=None, expected=0):
        self.write_cfg()
        command = [BASH, str(SCRIPT), *args] if code is None else [BASH, '-c', code, '_', str(SCRIPT)]
        result = subprocess.run(command, env=env or self.env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.cfg = json.loads((self.root / 'config.json').read_text())
        return result

    def events(self, command=None):
        path = self.root / 'events.jsonl'
        events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [args for cmd, args in events if command is None or cmd == command]

    def dispatches(self):
        return [a[1] for a in self.events('hyprctl') if a[0] == 'dispatch']

    def menu(self):
        return self.events('omarchy-menu-select')[-1]

    def record(self, source=2, name='Planning', source_name=None):
        next(w for w in self.cfg['workspaces'] if w['id'] == 2)['name'] = name
        self.cfg['activeworkspace']['name'] = name
        record = {'id': 2, 'name': name, 'source': source, 'created': 123,
                  'source_name': source_name if source_name is not None else str(source)}
        (self.state / '2.json').write_text(json.dumps(record))
        return record

    def assert_no_effect(self):
        self.assertEqual(self.dispatches(), [])
        self.assertEqual(list(self.state.iterdir()), [])

    def test_menu_plain_position_before_tasks_and_workspaces(self):
        self.cfg['selection'] = 'Cancel'
        self.cfg['workspaces'].append({'id': 3, 'name': 'Other task'})
        (self.state / '3.json').write_text(json.dumps({'id': 3, 'name': 'Other task', 'source': 1}))
        self.run_task('send')
        rows = self.menu()[1:]
        self.assertEqual(rows[0], '󰐗\tStart task "Planning"\tname suggested from the window title')
        self.assertEqual(rows[1], '󰏫\tStart task with my own name…')
        self.assertEqual(rows[2], '󰉗\tTurn workspace 2 into a task…\twindows stay where they are')
        self.assertIn('Send to: Other task', rows[3])
        self.assertIn('Move to: 1', rows[4])

    def test_suggested_send_row_and_description_select_the_same_task(self):
        for cls in ('kitty', 'google-chrome'):
            with self.subTest(cls=cls):
                self.cfg['activewindow']['class'] = cls
                description = 'name suggested from the window title'
                if cls == 'google-chrome':
                    description += ' · whole window (all tabs)'
                self.cfg['selection'] = 'Start task "Planning"\t' + description
                self.run_task('send')
                self.assertEqual(self.menu()[1:4], [
                    '󰐗\tStart task "Planning"\t' + description,
                    '󰏫\tStart task with my own name…',
                    '󰉗\tTurn workspace 2 into a task…\twindows stay where they are',
                ])
                self.assertEqual(self.menu()[-3:], ['--', '--width', '600'])
                self.assertEqual(self.dispatches()[-2:], [
                    'hl.dsp.window.move({ window = "address:0xabc", workspace = "3", follow = true })',
                    'hl.dsp.workspace.rename({ workspace = "3", name = "Planning" })',
                ])
                self.assertEqual(json.loads((self.state / '3.json').read_text())['source'], 2)
                self.assertEqual(json.loads((self.state / '3.json').read_text())['source_name'], '2')
                self.cfg['workspaces'] = [w for w in self.cfg['workspaces'] if w['id'] != 3]
                (self.state / '3.json').unlink()

    def test_typed_send_name_with_quotes_is_sanitized(self):
        self.cfg.update(selection='Start task with my own name…', input='Plan "review"')
        self.run_task('send')
        self.assertEqual(self.events('omarchy-menu-input'), [['Task name']])
        self.assertEqual(self.dispatches(), [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "3", follow = true })',
            'hl.dsp.workspace.rename({ workspace = "3", name = "Plan review" })',
        ])
        self.assertEqual(json.loads((self.state / '3.json').read_text())['name'], 'Plan review')

    def test_fallback_class_is_sanitized_before_menu_and_prompt(self):
        self.cfg['activewindow'].update({'class': 'demo"app\\tool', 'title': 'Untitled'})
        name = 'Demoapptool task'
        self.cfg['selection'] = f'Start task "{name}"\tname suggested from the window title'
        self.run_task('send')
        self.assertIn('\U000f0417' + '\t' + self.cfg['selection'], self.menu())
        self.assertEqual(json.loads((self.state / '3.json').read_text())['name'], name)
        self.assertEqual(self.dispatches()[-1],
                         'hl.dsp.workspace.rename({ workspace = "3", name = "Demoapptool task" })')
        self.cfg['activeworkspace'] = {'id': 3, 'name': name}
        self.cfg['selection'] = 'Cancel'
        self.run_task('finish')
        self.assertEqual(self.menu()[0], f'Finish "{name}"?')
        self.assertIn('󰖭\tClose 1 window and finish\tDemoapptool', self.menu())

    def test_long_suggested_name_is_capped_without_changing_row_wording(self):
        self.cfg['activewindow']['title'] = 'Team ' * 7 + 'notes'
        name = 'Team ' * 6 + 'Team…'
        self.cfg['selection'] = f'Start task "{name}"\tname suggested from the window title'
        self.run_task('send')
        self.assertIn('\U000f0417' + '\t' + self.cfg['selection'], self.menu())
        self.assertLessEqual(len(self.menu()[1].split('\t')[1]), 50)
        self.assertEqual(json.loads((self.state / '3.json').read_text())['name'], name)
        self.assertEqual(len(name), 35)

    def test_finish_return_rows_counts_descriptions_and_actions(self):
        for count in (1, 2, 10):
            with self.subTest(count=count):
                self.record(source=10)
                self.cfg['workspaces'] = [{'id': 10, 'name': '10'}, {'id': 2, 'name': 'Planning'}]
                self.cfg['clients'] = [dict(self.cfg['activewindow'], address=f'0x{i:x}')
                                       for i in range(count)]
                noun = 'window' if count == 1 else 'windows'
                label = f'Keep {count} {noun} and finish'
                self.cfg['selection'] = label + '\treturns to workspace 10 · nothing is closed'
                (self.root / 'events.jsonl').unlink(missing_ok=True)
                self.run_task('finish')
                summary = 'Terminal' + (f' ×{count}' if count > 1 else '')
                self.assertEqual(self.menu()[1:-3], [
                    f'󰖭\tClose {count} {noun} and finish\t{summary}',
                    f'󰐃\t{label}\treturns to workspace 10 · nothing is closed', '󰁍\tCancel',
                ])
                self.assertEqual(self.menu()[-3:], ['--', '--width', '600'])
                self.assertTrue(all(len(row.split('\t')[1]) <= 50 for row in self.menu()[1:-3]))
                self.assertEqual(self.dispatches(), [
                    f'hl.dsp.window.move({{ window = "address:0x{i:x}", workspace = "10", follow = false }})'
                    for i in range(count)
                ] + ['hl.dsp.focus({ workspace = "10" })'])
                self.assertEqual(len(self.cfg['clients']), count)
                self.assertFalse((self.state / '2.json').exists())

    def test_finish_close_plural_row_closes_every_window(self):
        self.record(source=1)
        self.cfg['clients'].append(dict(self.cfg['activewindow'], address='0xdef'))
        self.cfg['selection'] = 'Close 2 windows and finish\tTerminal ×2'
        self.run_task('finish')
        self.assertEqual(self.dispatches(), [
            'hl.dsp.window.close({ window = "address:0xabc" })',
            'hl.dsp.window.close({ window = "address:0xdef" })',
            'hl.dsp.focus({ workspace = "1" })',
        ])
        self.assertEqual(self.cfg['clients'], [])
        self.assertFalse((self.state / '2.json').exists())

    def test_finish_keep_plural_row_keeps_all_windows(self):
        self.record()
        self.cfg['clients'].append(dict(self.cfg['activewindow'], address='0xdef'))
        before = copy.deepcopy(self.cfg['clients'])
        self.cfg['selection'] = 'Keep 2 windows and finish\tstays in workspace 2 · nothing is closed'
        self.run_task('finish')
        self.assertIn('󰐃\t' + self.cfg['selection'], self.menu())
        self.assertEqual(self.dispatches(), ['hl.dsp.workspace.rename({ workspace = "2", name = "2" })'])
        self.assertEqual(self.cfg['clients'], before)
        self.assertFalse((self.state / '2.json').exists())

    def test_existing_task_and_plain_workspace_icons_and_actions(self):
        for is_task in (True, False):
            with self.subTest(is_task=is_task):
                self.cfg['workspaces'] = [
                    {'id': 1, 'name': '1'}, {'id': 2, 'name': '2'}, {'id': 3, 'name': 'Notes'},
                ]
                task_file = self.state / '3.json'
                if is_task:
                    task_file.write_text(json.dumps({'id': 3, 'name': 'Notes', 'source': 1}))
                else:
                    task_file.unlink()
                action = 'Send to' if is_task else 'Move to'
                self.cfg['selection'] = f'{action}: Notes\tworkspace 3'
                (self.root / 'events.jsonl').unlink(missing_ok=True)
                self.run_task('send')
                self.assertIn('󰉒\t' + self.cfg['selection'], self.menu())
                self.assertEqual(self.dispatches(), [
                    'hl.dsp.window.move({ window = "address:0xabc", workspace = "3", follow = true })',
                ])
                self.assertFalse((self.state / '2.json').exists())

    def test_quoted_existing_task_row_matches_and_lua_string_escapes_quotes(self):
        name = 'Plan "review"'
        self.cfg['workspaces'].append({'id': 3, 'name': name})
        (self.state / '3.json').write_text(json.dumps({'id': 3, 'name': name, 'source': 1}))
        self.cfg['selection'] = f'Send to: {name}\tworkspace 3'
        self.run_task('send')
        self.assertIn('󰉒\t' + self.cfg['selection'], self.menu())
        self.assertEqual(self.dispatches(), [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "3", follow = true })',
        ])
        result = self.run_task(code='source "$1"; lua_string "$TEST_NAME"',
                               env=dict(self.env, TEST_NAME=name))
        self.assertEqual(result.stdout, r'"Plan \"review\""')

    def test_special_workspace_records_and_returns_to_workspace_one(self):
        for source in (-99, 0):
            with self.subTest(source=source):
                self.cfg['workspaces'] = [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'},
                                          {'id': source, 'name': 'special:scratch'}]
                self.cfg['activewindow']['workspace'] = {'id': source, 'name': 'special:scratch'}
                self.cfg['clients'] = [copy.deepcopy(self.cfg['activewindow'])]
                self.cfg['selection'] = 'Start task "Planning"\tname suggested from the window title'
                self.run_task('send')
                record = json.loads((self.state / '3.json').read_text())
                self.assertEqual((record['source'], record['source_name']), (1, '1'))
                self.assertFalse(any('Turn workspace' in row for row in self.menu()))
                self.cfg['activeworkspace'] = {'id': 3, 'name': 'Planning'}
                self.cfg['selection'] = 'Keep 1 window and finish'
                self.run_task('finish')
                self.assertIn('󰐃\tKeep 1 window and finish\treturns to workspace 1 · nothing is closed', self.menu())
                self.assertEqual(self.dispatches()[-2:], [
                    'hl.dsp.window.move({ window = "address:0xabc", workspace = "1", follow = false })',
                    'hl.dsp.focus({ workspace = "1" })',
                ])
                self.assertFalse((self.state / '3.json').exists())

    def test_finish_refreshes_windows_closed_or_opened_during_menu(self):
        for action in ('Keep', 'Close'):
            for new_window in (False, True):
                with self.subTest(action=action, new_window=new_window):
                    self.cfg['workspaces'] = [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'}]
                    self.record(source=1)
                    self.cfg['clients'] = [copy.deepcopy(self.cfg['activewindow'])]
                    replacement = dict(self.cfg['activewindow'], address='0xdef')
                    self.cfg['menu_updates'] = {'clients': [replacement] if new_window else []}
                    self.cfg['selection'] = f'{action} 1 window and finish'
                    (self.root / 'events.jsonl').unlink(missing_ok=True)
                    self.run_task('finish')
                    expected = []
                    if new_window:
                        expected = [
                            'hl.dsp.window.move({ window = "address:0xdef", workspace = "1", follow = false })'
                            if action == 'Keep' else 'hl.dsp.window.close({ window = "address:0xdef" })',
                        ]
                    self.assertEqual(self.dispatches(), expected + ['hl.dsp.focus({ workspace = "1" })'])
                    self.assertFalse((self.state / '2.json').exists())
                    self.assertTrue(any('Finished: Planning' in args for args in self.events('omarchy-notification-send')))

    def test_changed_missing_or_task_source_falls_back_to_workspace_one(self):
        for situation in ('missing', 'renamed', 'task', 'unchanged', 'legacy', 'legacy_numbered'):
            with self.subTest(situation=situation):
                self.cfg['workspaces'] = [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'},
                                          {'id': 3, 'name': 'Desk'}]
                record = self.record(source=3, source_name='Desk')
                self.cfg['clients'] = [copy.deepcopy(self.cfg['activewindow'])]
                (self.state / '3.json').unlink(missing_ok=True)
                if situation == 'missing':
                    self.cfg['workspaces'].pop()
                elif situation == 'renamed':
                    self.cfg['workspaces'][-1]['name'] = 'New desk'
                elif situation == 'task':
                    (self.state / '3.json').write_text(json.dumps({'id': 3, 'name': 'Desk', 'source': 1}))
                elif situation in ('legacy', 'legacy_numbered'):
                    if situation == 'legacy_numbered':
                        self.cfg['workspaces'][-1]['name'] = '3'
                    record.pop('source_name')
                    (self.state / '2.json').write_text(json.dumps(record))
                target = 3 if situation in ('unchanged', 'legacy_numbered') else 1
                self.cfg['selection'] = 'Keep 1 window and finish'
                (self.root / 'events.jsonl').unlink(missing_ok=True)
                self.run_task('finish')
                self.assertIn(f'󰐃\tKeep 1 window and finish\treturns to workspace {target} · nothing is closed', self.menu())
                self.assertEqual(self.dispatches(), [
                    f'hl.dsp.window.move({{ window = "address:0xabc", workspace = "{target}", follow = false }})',
                    f'hl.dsp.focus({{ workspace = "{target}" }})',
                ])
                self.assertEqual(self.cfg['clients'][0]['workspace']['id'], target)
                self.assertFalse((self.state / '2.json').exists())

    def test_source_is_rechecked_after_menu_before_returning_windows(self):
        self.cfg['workspaces'].append({'id': 3, 'name': 'Desk'})
        self.record(source=3, source_name='Desk')
        self.cfg['selection'] = 'Keep 1 window and finish'
        self.cfg['menu_records'] = [{'id': 3, 'name': 'Desk', 'source': 1}]
        self.run_task('finish')
        self.assertIn('󰐃\tKeep 1 window and finish\treturns to workspace 3 · nothing is closed', self.menu())
        self.assertEqual(self.dispatches(), [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "1", follow = false })',
            'hl.dsp.focus({ workspace = "1" })',
        ])
        self.assertTrue((self.state / '3.json').exists())

    def test_chained_task_records_source_identity_but_never_returns_into_task(self):
        parent = self.record(name='Parent')
        self.cfg['selection'] = 'Start task "Planning"\tname suggested from the window title'
        self.run_task('send')
        child = json.loads((self.state / '3.json').read_text())
        self.assertEqual((child['source'], child['source_name']), (2, 'Parent'))
        self.cfg['activeworkspace'] = {'id': 3, 'name': 'Planning'}
        self.cfg['selection'] = 'Keep 1 window and finish'
        self.run_task('finish')
        self.assertEqual(self.dispatches()[-2:], [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "1", follow = false })',
            'hl.dsp.focus({ workspace = "1" })',
        ])
        self.assertEqual(json.loads((self.state / '2.json').read_text()), parent)

    def test_fallback_never_moves_into_another_task_on_workspace_one(self):
        self.record(source=3)
        self.cfg['workspaces'][0]['name'] = 'Other task'
        (self.state / '1.json').write_text(json.dumps({'id': 1, 'name': 'Other task', 'source': 4}))
        self.cfg['selection'] = 'Keep 1 window and finish'
        self.run_task('finish')
        self.assertIn('󰐃\tKeep 1 window and finish\treturns to workspace 3 · nothing is closed', self.menu())
        self.assertEqual(self.dispatches(), [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "3", follow = false })',
            'hl.dsp.focus({ workspace = "3" })',
        ])

    def test_digit_only_names_are_prefixed_for_every_name_entry_path(self):
        for action in ('suggest', 'type', 'adopt', 'rename'):
            with self.subTest(action=action):
                for state in self.state.glob('*.json'):
                    state.unlink()
                self.cfg['workspaces'] = [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'}]
                self.cfg['clients'] = [copy.deepcopy(self.cfg['activewindow'])]
                self.cfg['activewindow']['title'] = '2'
                self.cfg['input'] = '2'
                self.cfg['selection'] = {
                    'suggest': 'Start task "Task 2"\tname suggested from the window title',
                    'type': 'Start task with my own name…',
                    'adopt': 'Turn workspace 2 into a task…\twindows stay where they are',
                    'rename': 'Rename this task…',
                }[action]
                if action == 'rename':
                    self.record()
                self.run_task('send')
                target = 3 if action in ('suggest', 'type') else 2
                self.assertEqual(json.loads((self.state / f'{target}.json').read_text())['name'], 'Task 2')

    def test_duplicate_check_compares_digit_names_with_workspace_ids(self):
        env = dict(self.env, TEST_WORKSPACES=json.dumps([{'id': 2, 'name': 'Named desk'}]))
        result = self.run_task(code='source "$1"; workspaces=$TEST_WORKSPACES; dedupe 2', env=env)
        self.assertEqual(result.stdout, '2 2\n')

    def test_duplicate_suggested_names_stay_within_thirty_five_characters(self):
        base = 'Team ' * 6 + 'Team…'
        self.cfg['activewindow']['title'] = 'Team ' * 7 + 'notes'
        self.cfg['workspaces'].append({'id': 3, 'name': base})
        expected = base[:33] + ' 2'
        self.cfg['selection'] = f'Start task "{expected}"\tname suggested from the window title'
        self.run_task('send')
        self.assertIn('󰐗\t' + self.cfg['selection'], self.menu())
        self.assertEqual(json.loads((self.state / '4.json').read_text())['name'], expected)
        self.assertLessEqual(len(expected), 35)

    def test_close_allows_saving_longer_than_five_seconds(self):
        self.record(source=1)
        self.cfg.update(selection='Close 1 window and finish', refuse_close=True, close_after_polls=5)
        self.run_task(code='source "$1"; sleep() { SECONDS=$((SECONDS + 2)); }; main finish')
        self.assertEqual(self.cfg['polls_since_close'], 5)
        self.assertFalse((self.state / '2.json').exists())
        self.assertEqual(self.dispatches()[-1], 'hl.dsp.focus({ workspace = "1" })')

    def test_close_dry_run_describes_ten_second_stall_limit(self):
        self.record()
        result = self.run_task('finish', '--dry-run')
        self.assertIn('30s cap; 10s stalled', result.stdout)

    def test_window_vanishing_after_refresh_is_ignored_without_failure_notice(self):
        for action in ('Keep', 'Close'):
            with self.subTest(action=action):
                self.record(source=1)
                self.cfg['clients'] = [copy.deepcopy(self.cfg['activewindow'])]
                self.cfg.update(selection=f'{action} 1 window and finish', vanish_on_dispatch='0xabc')
                (self.root / 'events.jsonl').unlink(missing_ok=True)
                self.run_task('finish')
                self.assertFalse((self.state / '2.json').exists())
                self.assertEqual(self.dispatches()[-1], 'hl.dsp.focus({ workspace = "1" })')
                notices = self.events('omarchy-notification-send')
                self.assertTrue(any('Finished: Planning' in args for args in notices))
                self.assertFalse(any('Dispatch failed:' in ' '.join(args) for args in notices))

    def test_real_finish_dispatch_failure_still_preserves_task(self):
        record = self.record(source=1)
        self.cfg.update(selection='Keep 1 window and finish', dispatch_error=True)
        self.run_task('finish', expected=1)
        self.assertEqual(json.loads((self.state / '2.json').read_text()), record)

    def test_closed_normal_workspace_gone_still_cleans_state_and_returns(self):
        self.record(source=1)
        self.cfg.update(selection='Close 1 window and finish', remove_empty_workspace=True)
        self.run_task('finish')
        self.assertFalse((self.state / '2.json').exists())
        self.assertEqual(self.dispatches(), [
            'hl.dsp.window.close({ window = "address:0xabc" })',
            'hl.dsp.focus({ workspace = "1" })',
        ])

    def test_adopt_cleans_deduplicates_and_never_moves_or_focuses(self):
        self.cfg['input'] = '  A<$`>  plan\n '
        self.cfg['workspaces'].append({'id': 3, 'name': 'A plan'})
        before = copy.deepcopy(self.cfg['clients'])
        self.run_task('send')
        record = json.loads((self.state / '2.json').read_text())
        self.assertEqual(record['name'], 'A plan 2')
        self.assertEqual(record['id'], record['source'])
        self.assertIsInstance(record['created'], int)
        self.assertEqual(self.dispatches(), ['hl.dsp.workspace.rename({ workspace = "2", name = "A plan 2" })'])
        self.assertEqual(self.cfg['clients'], before)
        self.assertEqual(list(self.state.glob('*.tmp')), [])

    def test_silent_address_uses_captured_workspace(self):
        self.cfg['activewindow'] = {'address': '0xdef', 'workspace': {'id': 1}, 'class': 'kitty', 'title': ''}
        self.run_task('send', '--silent', '--address', '0xabc')
        self.assertEqual(self.dispatches(), ['hl.dsp.workspace.rename({ workspace = "2", name = "Planning" })'])

    def test_empty_whitespace_sanitized_empty_and_cancel_input(self):
        for text, cancel in [('', False), (' \t\n ', False), ('<$`[]>', False), ('Planning', True)]:
            with self.subTest(text=text, cancel=cancel):
                self.cfg.update(input=text, input_cancel=cancel)
                self.run_task('send')
                self.assert_no_effect()

    def test_menu_cancel(self):
        self.cfg['select_cancel'] = True
        self.run_task('send')
        self.assert_no_effect()

    def test_no_adopt_for_named_or_special_workspace(self):
        for wsid, name in [(2, 'Named without state'), (-99, 'special:scratch')]:
            with self.subTest(wsid=wsid):
                self.cfg['workspaces'][1] = {'id': wsid, 'name': name}
                self.cfg['activewindow']['workspace']['id'] = wsid
                self.run_task('send')
                self.assertFalse(any('Turn workspace' in row for row in self.menu()))
                self.assert_no_effect()

    def test_existing_task_has_rename_only(self):
        self.record(source=1)
        self.run_task('send')
        self.assertIn('󰏫\tRename this task…', self.menu())
        self.assertFalse(any('Turn workspace' in row for row in self.menu()))
        self.assertEqual(self.dispatches(), [])

    def test_plain_workspace_with_valid_state_cannot_adopt(self):
        (self.state / '2.json').write_text(json.dumps({'id': 2, 'name': '2', 'source': 1}))
        self.run_task('send')
        self.assertFalse(any('Turn workspace' in row for row in self.menu()))
        self.assertEqual(self.dispatches(), [])

    def test_recheck_vanished_or_renamed_workspace(self):
        for workspaces in [[{'id': 1, 'name': '1'}], [{'id': 2, 'name': 'Taken'}]]:
            with self.subTest(workspaces=workspaces):
                self.cfg['workspaces'] = [{'id': 2, 'name': '2'}]
                self.cfg['input_updates'] = {'workspaces': workspaces}
                self.run_task('send')
                self.assert_no_effect()

    def test_recheck_state_created_during_input(self):
        record = {'id': 2, 'name': '2', 'source': 1}
        self.cfg['input_state'] = record
        self.run_task('send')
        self.assertEqual(self.dispatches(), [])
        self.assertEqual(json.loads((self.state / '2.json').read_text()), record)

    def test_dedupe_rechecks_workspace_names_after_input(self):
        self.cfg['input_updates'] = {'workspaces': self.cfg['workspaces'] + [{'id': 3, 'name': 'Planning'}]}
        self.run_task('send')
        self.assertEqual(json.loads((self.state / '2.json').read_text())['name'], 'Planning 2')

    def test_adopt_dispatch_failure_leaves_no_state(self):
        self.cfg['dispatch_error'] = True
        self.run_task('send', expected=1)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_keep_in_place_restores_number_removes_state_and_keeps_focus(self):
        self.record()
        before = copy.deepcopy(self.cfg['clients'])
        self.cfg['selection'] = 'Keep 1 window and finish'
        self.run_task('finish')
        self.assertIn('󰐃\tKeep 1 window and finish\tstays in workspace 2 · nothing is closed', self.menu())
        self.assertIn('󰖭\tClose 1 window and finish\tTerminal', self.menu())
        self.assertIn('󰁍\tCancel', self.menu())
        self.assertFalse(any('back to workspace' in row for row in self.menu()))
        self.assertEqual(self.dispatches(), ['hl.dsp.workspace.rename({ workspace = "2", name = "2" })'])
        self.assertEqual(self.cfg['clients'], before)
        self.assertEqual(self.cfg['workspaces'][1]['name'], '2')
        self.assertFalse((self.state / '2.json').exists())

    def test_close_in_place_resets_number_without_focus_dispatch(self):
        self.record()
        self.cfg['selection'] = 'Close 1 window and finish\tTerminal'
        self.run_task('finish')
        self.assertEqual(self.dispatches(), ['hl.dsp.window.close({ window = "address:0xabc" })',
                                             'hl.dsp.workspace.rename({ workspace = "2", name = "2" })'])
        self.assertEqual(self.cfg['clients'], [])
        self.assertFalse((self.state / '2.json').exists())

    def test_closed_workspace_gone_needs_no_rename_or_focus(self):
        self.record()
        self.cfg.update(selection='Close 1 window and finish', remove_empty_workspace=True)
        self.run_task('finish')
        self.assertEqual(self.dispatches(), ['hl.dsp.window.close({ window = "address:0xabc" })'])
        self.assertFalse((self.state / '2.json').exists())

    def test_refused_close_retains_task_and_does_not_reset_or_focus(self):
        record = self.record()
        self.cfg.update(selection='Close 1 window and finish', refuse_close=True)
        self.run_task('finish')
        self.assertEqual(self.dispatches(), ['hl.dsp.window.close({ window = "address:0xabc" })'])
        self.assertEqual(json.loads((self.state / '2.json').read_text()), record)
        self.assertTrue(any('Not finished:' in ' '.join(args) for args in self.events('omarchy-notification-send')))

    def test_empty_in_place_task_finishes_without_menu_or_focus(self):
        self.record()
        self.cfg['clients'] = []
        self.run_task('finish')
        self.assertEqual(self.events('omarchy-menu-select'), [])
        self.assertEqual(self.dispatches(), ['hl.dsp.workspace.rename({ workspace = "2", name = "2" })'])
        self.assertFalse((self.state / '2.json').exists())

    def test_failed_reset_preserves_task_state(self):
        record = self.record()
        self.cfg.update(selection='Keep 1 window and finish', dispatch_error=True)
        self.run_task('finish', expected=1)
        self.assertEqual(json.loads((self.state / '2.json').read_text()), record)

    def test_finish_cancel_retains_state_and_windows(self):
        record = self.record()
        self.cfg['selection'] = 'Cancel'
        self.run_task('finish')
        self.assertEqual(self.dispatches(), [])
        self.assertEqual(json.loads((self.state / '2.json').read_text()), record)

    def test_renaming_adopted_task_preserves_in_place_marker(self):
        self.record()
        self.cfg.update(selection='Rename this task…', input='Revised')
        self.run_task('send')
        record = json.loads((self.state / '2.json').read_text())
        self.assertEqual((record['name'], record['source'], record['id']), ('Revised', 2, 2))

    def test_adopted_task_appears_in_other_workspace_send_menu(self):
        self.run_task('send')
        self.cfg['activewindow']['workspace']['id'] = 1
        self.cfg['selection'] = 'Cancel'
        self.run_task('send')
        self.assertIn('󰉒\tSend to: Planning\tworkspace 2', self.menu())

    def test_lock_contention_changes_nothing(self):
        with (self.runtime / 'taskspaces.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.run_task('send')
        self.assertEqual(self.events(), [])
        self.assert_no_effect()

    def test_finish_dispatches_for_move_close_empty_and_fallback(self):
        move = 'hl.dsp.window.move({ window = "address:0xabc", workspace = "1", follow = false })'
        close = 'hl.dsp.window.close({ window = "address:0xabc" })'
        focus = 'hl.dsp.focus({ workspace = "1" })'
        scenarios = {
            'move': ('Keep 1 window and finish', [move, focus]),
            'close': ('Close 1 window and finish', [close, focus]),
            'empty': ('Cancel', [focus]),
            'fallback': ('Keep 1 window and finish', [move, focus]),
        }
        for scenario, (selection, expected) in scenarios.items():
            with self.subTest(scenario=scenario):
                self.record(source=1)
                self.cfg['selection'] = selection
                self.cfg['clients'] = [] if scenario == 'empty' else [copy.deepcopy(self.cfg['activewindow'])]
                self.cfg['workspaces'] = [{'id': 2, 'name': 'Planning'}] if scenario == 'fallback' else [
                    {'id': 1, 'name': '1'}, {'id': 2, 'name': 'Planning'}]
                (self.root / 'events.jsonl').unlink(missing_ok=True)
                self.run_task('finish')
                self.assertEqual(self.dispatches(), expected)
                self.assertFalse((self.state / '2.json').exists())

    def test_cli_dry_run_has_no_menus_dispatches_or_state_writes(self):
        self.state.rmdir()
        result = self.run_task('send', '--dry-run')
        self.assertIn('hyprctl dispatch hl.dsp.window.move', result.stdout)
        self.assertEqual(self.dispatches(), [])
        self.assertFalse(self.state.exists())
        self.assertFalse((self.runtime / 'taskspaces.lock').exists())
        self.assertEqual(self.events('omarchy-menu-select'), [])
        self.assertEqual(self.events('omarchy-menu-input'), [])
        self.assertEqual(self.events('omarchy-notification-send'), [])

    def test_in_place_finish_dry_run_preserves_state_and_prints_no_focus(self):
        record = self.record()
        result = self.run_task('finish', '--dry-run')
        self.assertIn('workspace.rename', result.stdout)
        self.assertNotIn('hl.dsp.focus', result.stdout)
        self.assertEqual(self.dispatches(), [])
        self.assertEqual(json.loads((self.state / '2.json').read_text()), record)
        self.assertFalse((self.runtime / 'taskspaces.lock').exists())
        self.assertEqual(self.events('omarchy-menu-select'), [])

    def test_adopt_helper_dry_run_prints_rename_without_writing_state(self):
        result = self.run_task(code='source "$1"; dry=true; state_dir="$XDG_RUNTIME_DIR/taskspaces"; make_workspace_task 2 kitty')
        self.assertIn('workspace.rename', result.stdout)
        self.assertNotIn('window.move', result.stdout)
        self.assert_no_effect()

    def test_version_prints_version(self):
        result = self.run_task('--version')
        self.assertEqual(result.stdout, '0.1.0\n')
        self.assertEqual(result.stderr, '')

    def test_help_lists_commands_and_exits_zero(self):
        result = self.run_task('--help')
        for text in ('Usage: taskspaces send', 'taskspaces finish', '--silent', '--version'):
            self.assertIn(text, result.stdout)
        self.assertEqual(result.stderr, '')

    def test_help_and_version_need_no_dependencies(self):
        env = dict(self.env, PATH=self.isolated_path('no-tools', []))
        self.assertEqual(self.run_task('--version', env=env).stdout, '0.1.0\n')
        self.assertIn('Usage: taskspaces', self.run_task('--help', env=env).stdout)

    def test_missing_dependency_is_named_in_one_line(self):
        for missing in REQUIRED:
            with self.subTest(missing=missing):
                commands = [command for command in REQUIRED if command != missing]
                env = dict(self.env, PATH=self.isolated_path(f'without-{missing}', commands))
                result = self.run_task('send', env=env, expected=1)
                self.assertEqual(result.stderr, f'taskspaces: Missing required command: {missing}\n')
                self.assertEqual(result.stdout, '')
                self.assertEqual(self.events(), [])

    def test_dispatch_failure_sends_notification(self):
        self.cfg['dispatch_error'] = True
        self.run_task('send', expected=1)
        self.assertTrue(any('Dispatch failed: mock dispatcher failure' in ' '.join(args)
                            for args in self.events('omarchy-notification-send')))

    def test_dispatch_failure_without_notifiers_falls_back_to_stderr(self):
        self.cfg['dispatch_error'] = True
        env = dict(self.env, PATH=self.isolated_path('no-notifier', REQUIRED + TOOLS))
        result = self.run_task('send', env=env, expected=1)
        self.assertIn('taskspaces: Dispatch failed: mock dispatcher failure\n', result.stderr)

    def test_notify_send_is_used_when_omarchy_helper_is_missing(self):
        env = dict(self.env, PATH=self.isolated_path('notify-send-only', REQUIRED + TOOLS + ('notify-send',)))
        self.run_task('send', env=env)
        self.assertEqual(self.events('omarchy-notification-send'), [])
        sent = self.events('notify-send')
        self.assertEqual(sent[-1][0], 'taskspaces')
        self.assertIn('workspace 2', sent[-1][1])

    def test_notifications_use_taskspaces_title(self):
        self.run_task('send')
        self.assertEqual(self.events('omarchy-notification-send')[-1][:3], ['-g', '󰌨', 'taskspaces'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
