#!/usr/bin/env python3
"""Run the real shell functions and CLI against fake Hyprland and menu executables only."""
import copy
import fcntl
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

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
def refresh_rules():
    if 'monitors' not in cfg: return
    for rule in cfg.get('workspacerules', []):
        if rule.get('enabled') is False or not rule.get('persistent') or not rule['workspaceString'].isdigit(): continue
        owner = rule.get('monitor') or next(m for m in cfg['monitors'] if m.get('focused'))['name']
        if not any(m['name'] == owner for m in cfg['monitors']): continue
        wid = int(rule['workspaceString'])
        ws = next((w for w in cfg['workspaces'] if w['id'] == wid), None)
        if ws is None and not cfg.get('no_persistent_creation'):
            name = str(wid) if cfg.get('numeric_first') else rule.get('defaultName', str(wid))
            ws = {'id': wid, 'name': name, 'monitor': owner, 'windows': 0, 'ispersistent': True}
            cfg['workspaces'].append(ws)
        if ws is not None: ws['monitor'] = owner
    for mon in cfg['monitors']:
        ws = next((w for w in cfg['workspaces'] if w['id'] == mon['activeWorkspace']['id']), None)
        if ws: mon['activeWorkspace'] = dict(ws)
def save():
    refresh_rules()
    cfgpath.write_text(json.dumps(cfg))
def lua_text(value):
    # The mock parses string literals; it does not execute compositor Lua.
    return json.loads(re.sub(r'\\([0-9]{1,3})', lambda m: chr(int(m[1])), value))
if cmd == 'hyprctl':
    request = ' '.join(args)
    # Real hyprctl selects these routes by substring before dispatching Lua.
    for route in ('/--batch', '/hyprpaper', '/hyprsunset', '/instances'):
        if route in request:
            print('unexpected hyprctl request route: ' + route)
            sys.exit(2)
    if args[0] in ('eval', 'dispatch') and args[1].startswith('-'):
        print('usage: hyprctl [flags] [args...|--help]')
        sys.exit(2)
    if args[0] in ('workspaces', 'clients', 'activewindow', 'activeworkspace', 'monitors', 'workspacerules'):
        save()
        if args[0] == 'clients' and 'polls_since_close' in cfg:
            cfg['polls_since_close'] += 1
            if cfg.get('close_after_polls') == cfg['polls_since_close']:
                cfg['clients'] = []
            save()
        if args[0] == 'monitors':
            print(json.dumps(cfg.get('monitors', [{'id': 0, 'name': 'eDP-1', 'focused': True, 'activeWorkspace': cfg['activeworkspace']}])))
        else: print(json.dumps(cfg.get(args[0], [])))
    elif args[0] == 'eval':
        code = args[1]
        if cfg.get('eval_error'):
            print('mock rule failure'); sys.exit(0)
        cfg.setdefault('workspacerules', [])
        cfg.setdefault('owned_rules', {})
        if code.startswith('local live = {'):
            live = {int(n) for n in re.findall(r'\[([0-9]+)\]', code.split('local stale')[0])}
            stale = {int(n) for n in re.findall(r'\[([0-9]+)\]', code.split('local stale')[1].split('for key')[0])}
            for key in list(cfg['owned_rules']):
                if int(key) not in live or int(key) in stale:
                    cfg['owned_rules'].pop(key)
                    for rule in cfg['workspacerules']:
                        if rule['workspaceString'] == key: rule['enabled'] = False
            save(); print('ok'); sys.exit(0)
        key = re.search(r'taskspaces:([0-9]+)', code)[1]
        if 'hl.workspace_rule' in code and (key in cfg['owned_rules'] or '; else ' in code):
            wid = int(key)
            name = lua_text('"' + re.search(r'default_name = "([^"]+)"', code)[1] + '"')
            cfg['owned_rules'][key] = name
            rule = next((r for r in cfg['workspacerules'] if r['workspaceString'] == key and r.get('enabled') is not False), None)
            if rule is None:
                rule = {'workspaceString': key}
                cfg['workspacerules'].append(rule)
            rule.update(enabled=True, persistent=True, defaultName=name)
            binding = re.search(r'monitor = "([^"]+)"', code)
            if binding: rule['monitor'] = lua_text('"' + binding[1] + '"')
            if not cfg.get('no_persistent_creation') and not any(w['id'] == wid for w in cfg['workspaces']):
                binding = re.search(r'monitor = "([^"]+)"', code)
                owner = binding[1] if binding and not cfg.get('ignore_rule_monitor') else next(m for m in cfg['monitors'] if m.get('focused'))['name']
                cfg['workspaces'].append({'id': wid, 'name': str(wid) if cfg.get('numeric_first') else name, 'monitor': owner, 'windows': 0, 'ispersistent': True})
        if 'r:set_enabled(false)' in code and key in cfg['owned_rules']:
            cfg['owned_rules'].pop(key)
            for rule in cfg['workspacerules']:
                if rule['workspaceString'] == key: rule['enabled'] = False
        save(); print('ok')
    elif args[0] == 'dispatch':
        dsp = args[1]
        cfg['dispatch_count'] = cfg.get('dispatch_count', 0) + 1
        if cfg.get('ignore_moves') and dsp.startswith('hl.dsp.window.move'):
            print('ok'); sys.exit(0)
        if cfg.get('dispatch_error') or cfg.get('fail_dispatch_at') == cfg['dispatch_count'] or (cfg.get('fail_matching') and cfg['fail_matching'] in dsp):
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
        if 'monitors' in cfg and dsp.startswith('hl.dsp.focus'):
            match = re.search(r'workspace = "([0-9]+)"', dsp)
            if match:
                dest = int(match[1])
                ws = next((w for w in cfg['workspaces'] if w['id'] == dest), None)
                if ws is None:
                    owner = next(m for m in cfg['monitors'] if m.get('focused'))['name']
                    ws = {'id': dest, 'name': str(dest), 'monitor': owner, 'windows': 0}
                    cfg['workspaces'].append(ws)
                for m in cfg['monitors']:
                    m['focused'] = m['name'] == ws['monitor']
                    if m['focused']: m['activeWorkspace'] = dict(ws)
                cfg['activeworkspace'] = dict(ws)
            else:
                owner = re.search(r'monitor = "([^"]+)"', dsp)[1]
                for m in cfg['monitors']: m['focused'] = m['name'] == owner
        if dsp.startswith('hl.dsp.workspace.move'):
            selected = re.search(r'workspace = "([0-9]+)"', dsp)
            if selected and cfg.get('ignore_targeted_workspace_move'):
                save(); print('ok'); sys.exit(0)
            dest = int(selected[1]) if selected else next(m for m in cfg['monitors'] if m.get('focused'))['activeWorkspace']['id']
            owner = re.search(r'monitor = "([^"]+)"', dsp)[1]
            for w in cfg['workspaces']:
                if w['id'] == dest: w['monitor'] = owner
            if selected is None:
                for m in cfg['monitors']:
                    m['focused'] = m['name'] == owner
                    if m['focused']: m['activeWorkspace'] = dict(next(w for w in cfg['workspaces'] if w['id'] == dest))
        if dsp.startswith('hl.dsp.window.move'):
            dest = int(re.search(r'workspace = "([0-9]+)"', dsp)[1])
            if not any(w['id'] == dest for w in cfg['workspaces']):
                cfg['workspaces'].append({'id': dest, 'name': str(dest), **({'monitor': next(m for m in cfg['monitors'] if m.get('focused'))['name']} if 'monitors' in cfg else {})})
            for w in cfg['clients']:
                if w['address'] == addr:
                    w['workspace'] = dict(next(workspace for workspace in cfg['workspaces'] if workspace['id'] == dest))
        if dsp.startswith('hl.dsp.workspace.rename'):
            workspace_id, name = map(lua_text, re.search(r'workspace = ("(?:\\.|[^"\\])*"), name = ("(?:\\.|[^"\\])*")', dsp).groups())
            for w in cfg['workspaces']:
                if w['id'] == int(workspace_id): w['name'] = name
        if dsp.startswith('hl.dsp.window.close'):
            cfg['polls_since_close'] = 0
        if dsp.startswith('hl.dsp.window.close') and not cfg.get('refuse_close'):
            addr = re.search(r'address:(0x[0-9a-f]+)', dsp)[1]
            cfg['clients'] = [w for w in cfg['clients'] if w['address'] != addr]
            if cfg.get('remove_empty_workspace'):
                cfg['workspaces'] = [w for w in cfg['workspaces'] if w['id'] != cfg['activeworkspace']['id']]
        if 'monitors' in cfg:
            for ws in cfg['workspaces']:
                ws['windows'] = sum(w['workspace']['id'] == ws['id'] for w in cfg['clients'])
            for m in cfg['monitors']:
                active = next((w for w in cfg['workspaces'] if w['id'] == m['activeWorkspace']['id']), None)
                if active: m['activeWorkspace'] = dict(active)
            if cfg.get('destroy_empty'):
                active_ids = {m['activeWorkspace']['id'] for m in cfg['monitors']}
                cfg['workspaces'] = [w for w in cfg['workspaces'] if w.get('windows') or w['id'] in active_ids or w.get('ispersistent')]
        save()
        print('ok')
    else: raise RuntimeError(args)
elif cmd == 'omarchy-menu-select':
    if cfg.get('select_cancel'): sys.exit(1)
    cfg.update(cfg.pop('menu_updates', {}))
    for record in cfg.get('menu_records', []):
        (root / 'runtime' / 'taskspaces' / f'{record["id"]}.json').write_text(json.dumps(record))
    save()
    if cfg.get('select_first'):
        print(args[1].split('\t', 1)[1])
    else:
        selection = cfg['selections'].pop(0) if cfg.get('selections') else cfg.get('selection', 'Cancel')
        if selection is None:
            save(); sys.exit(1)  # Escape/close can cancel a particular submenu.
        print(selection)
    save()
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


def real_window(address, cls, title, workspace_id, workspace_name):
    """A client with every field `hyprctl clients -j` reports on Hyprland 0.56 (synthetic values)."""
    return {'address': address, 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True,
            'at': [10, 10], 'size': [800, 600], 'workspace': {'id': workspace_id, 'name': workspace_name},
            'floating': False, 'monitor': 0, 'class': cls, 'title': title, 'initialClass': cls,
            'initialTitle': title, 'pid': 4242, 'xwayland': False, 'pinned': False, 'pinFullscreened': False,
            'fullscreen': 0, 'fullscreenClient': 0, 'fullscreenHandler': 'scrolling',
            'allowedOverFullscreen': False, 'grouped': [], 'tags': [], 'swallowing': '0x0',
            'focusHistoryID': 0, 'inhibitingIdle': False, 'xdgTag': '', 'xdgDescription': '',
            'contentType': 'none', 'tearingHint': False, 'stableId': '18000000'}


def real_workspace(workspace_id, name, windows=1):
    """A workspace with every field `hyprctl workspaces -j` reports on Hyprland 0.56."""
    return {'id': workspace_id, 'name': name, 'monitor': 'eDP-1', 'monitorID': 0, 'windows': windows,
            'hasfullscreen': False, 'lastwindow': '0x0', 'lastwindowtitle': '', 'ispersistent': False,
            'tiledLayout': 'scrolling'}


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
        self.env = dict(os.environ, HOME=str(self.root), MOCK_ROOT=str(self.root), XDG_RUNTIME_DIR=str(self.runtime),
                        XDG_CONFIG_HOME=str(self.root / 'config'),
                        PATH=str(bindir) + os.pathsep + os.environ['PATH'])
        win = {'address': '0xabc', 'class': 'kitty', 'title': 'Planning', 'mapped': True,
               'workspace': {'id': 2, 'name': '2'}}
        self.cfg = {'workspaces': [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'}],
                    'activewindow': win, 'clients': [win], 'activeworkspace': {'id': 2, 'name': '2'},
                    'selection': 'Turn this workspace into a task…\tname this workspace · windows stay here'}
        # Existing behavior tests deliberately exercise legacy numbering.
        self.set_settings()
        self.write_cfg()

    def set_settings(self, first=1, two_screen=False, section='center'):
        path = self.root / 'config/omarchy/shell.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'version': 1, 'bar': {'layout': {section: [
            {'id': 'tithi-stack.taskspaces', 'firstTaskWorkspace': first,
             'experimentalTwoScreenTasks': two_screen}]}}}))

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
        lookup = subprocess.run([BASH, '-c', 'command -v hyprctl'],
                                env=env or self.env, text=True, capture_output=True)
        if lookup.returncode == 0:
            self.assertEqual(Path(lookup.stdout.strip()).resolve(), self.mock.resolve())
        else:
            # Dependency/help tests deliberately remove hyprctl from PATH.
            self.assertEqual(lookup.stdout, '')
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

    def use_real_shapes(self, windows):
        self.cfg['clients'] = windows
        self.cfg['activewindow'] = copy.deepcopy(windows[0])
        self.cfg['workspaces'] = [real_workspace(1, '1'), real_workspace(2, '2', 0)]
        self.cfg['activeworkspace'] = real_workspace(windows[0]['workspace']['id'], windows[0]['workspace']['name'])

    def test_real_hyprland_shapes_work_for_send_and_finish(self):
        self.use_real_shapes([real_window('0xabc', 'com.mitchellh.ghostty', 'Fix login bug', 1, '1'),
                              real_window('0xdef', 'google-chrome', 'Docs - Google Chrome', -98, 'special:scratchpad')])
        self.cfg['selection'] = 'Start task "Fix login bug"\tsuggested from window title · moves this window'
        self.run_task('send')
        self.assertEqual(self.dispatches()[-2:], [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "3", follow = true })',
            'hl.dsp.workspace.rename({ workspace = "3", name = "Fix login bug" })'])
        self.cfg['clients'][0]['workspace'] = {'id': 3, 'name': 'Fix login bug'}
        self.cfg['workspaces'] += [real_workspace(3, 'Fix login bug')]
        self.cfg['activeworkspace'] = real_workspace(3, 'Fix login bug')
        self.cfg['selection'] = 'Keep 1 window and finish'
        self.run_task('finish')
        self.assertIn('󰐃\tKeep 1 window and finish\treturns to workspace 1 · nothing is closed', self.menu())
        self.assertEqual(self.dispatches()[-2:], [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "1", follow = false })',
            'hl.dsp.focus({ workspace = "1" })'])
        self.assertFalse((self.state / '3.json').exists())

    def test_real_hyprland_window_on_special_workspace_is_sent_and_returns_to_one(self):
        self.use_real_shapes([real_window('0xabc', 'kitty', 'Scratch', -98, 'special:scratchpad')])
        self.cfg['workspaces'].append(real_workspace(-98, 'special:scratchpad'))
        self.cfg['selection'] = 'Start task "Scratch"\tsuggested from window title · moves this window'
        self.run_task('send')
        record = json.loads((self.state / '3.json').read_text())
        self.assertEqual((record['source'], record['source_name']), (1, '1'))
        self.assertFalse(any('Turn this workspace' in row for row in self.menu()))

    def test_empty_active_window_reports_no_tasks(self):
        # With no window open, `hyprctl activewindow -j` prints an empty object.
        self.cfg['activewindow'] = {}
        self.run_task('send')
        self.assert_no_effect()
        self.assertEqual(self.events('omarchy-menu-select'), [])
        self.assertTrue(any('No tasks yet' in ' '.join(args) for args in self.events('omarchy-notification-send')))

    def test_forget_single_task_leaves_every_window_in_place(self):
        self.record()
        self.cfg['workspacerules'] = [{'workspaceString': '2', 'enabled': True,
                                       'persistent': True, 'defaultName': 'Planning'}]
        self.cfg['owned_rules'] = {'2': 'Planning'}
        before = copy.deepcopy(self.cfg['clients'])
        self.run_task('forget')
        self.assertEqual(self.cfg['clients'], before)
        self.assertFalse((self.state / '2.json').exists())
        self.assertEqual(self.cfg['owned_rules'], {})
        self.assertFalse(self.cfg['workspacerules'][0]['enabled'])
        self.assertEqual(next(w['name'] for w in self.cfg['workspaces'] if w['id'] == 2), '2')
        self.assertTrue(all(c.startswith('hl.dsp.workspace.rename') for c in self.dispatches()))

    def test_forget_by_id_handles_changed_name_and_dry_run(self):
        self.record()
        self.cfg['workspaces'][1]['name'] = 'Changed by hand'
        self.cfg['activeworkspace'] = real_workspace(1, '1')
        before = copy.deepcopy(self.cfg)
        self.run_task('forget', '--task-id', '2', '--dry-run')
        self.assertTrue((self.state / '2.json').exists())
        self.assertEqual(self.cfg, before)
        self.assertEqual(self.dispatches(), [])
        self.run_task('forget', '--task-id', '2')
        self.assertFalse((self.state / '2.json').exists())
        self.assertEqual(self.cfg['clients'], before['clients'])

    def empty_workspace(self):
        self.cfg['activewindow'] = {}
        self.cfg['clients'] = []
        workspace = real_workspace(2, '2', 0)
        self.cfg['activeworkspace'] = copy.deepcopy(workspace)
        self.cfg['workspaces'] = [real_workspace(1, '1', 0), workspace]

    def test_empty_plain_workspace_can_be_named_without_moving(self):
        self.empty_workspace()
        self.cfg['selection'] = 'Turn this workspace into a task…\tname this empty workspace'
        self.run_task('send')
        self.assertEqual(self.menu(), [
            'Task', '󰉗\tTurn this workspace into a task…\tname this empty workspace',
            '--', '--width', '600'])
        self.assertEqual(self.events('omarchy-menu-input'), [['Task name']])
        self.assertEqual(self.dispatches(), ['hl.dsp.workspace.rename({ workspace = "2", name = "Planning" })'])
        record = json.loads((self.state / '2.json').read_text())
        self.assertEqual((record['name'], record['source']), ('Planning', 2))
        self.assertIn('open a window before leaving or this name will be lost',
                      self.events('omarchy-notification-send')[-1][-1])

    def test_empty_plain_workspace_offers_go_when_tasks_exist(self):
        self.empty_workspace()
        self.parked()
        self.cfg['selections'] = ['Go to a task…\tswitch to another task', 'Field Job Posting\tFiles']
        self.run_task('send')
        self.assertEqual(self.events('omarchy-menu-select')[0], [
            'Task', '󰉗\tTurn this workspace into a task…\tname this empty workspace',
            '󰉒\tGo to a task…\tswitch to another task', '--', '--width', '600'])
        self.assertEqual(self.dispatches(), ['hl.dsp.focus({ workspace = "3" })'])

    def test_empty_task_can_be_renamed_with_optional_go(self):
        for others in (False, True):
            with self.subTest(others=others):
                self.empty_workspace()
                self.record(source=1)
                if others:
                    self.parked()
                self.cfg.update(selection='Rename this task…\tchange this empty task name', input='Revised')
                self.run_task('send')
                rows = ['Task', '󰏫\tRename this task…\tchange this empty task name']
                if others:
                    rows += ['󰉒\tGo to a task…\tswitch to another task']
                self.assertEqual(self.menu(), rows + ['--', '--width', '600'])
                record = json.loads((self.state / '2.json').read_text())
                self.assertEqual((record['name'], record['source'], record['created']), ('Revised', 1, 123))
                self.assertIn('open a window before leaving or this name will be lost',
                              self.events('omarchy-notification-send')[-1][-1])

    def test_existing_requested_window_keeps_focused_window_menu(self):
        # An explicit live target still gets the old window menu, even when the
        # currently focused workspace is empty.
        self.cfg['activewindow'] = {}
        self.cfg['activeworkspace'] = real_workspace(1, '1', 0)
        self.cfg['selection'] = 'Cancel'
        self.run_task('send', '--address', '0xabc')
        self.assertEqual(self.menu(), [
            'Task',
            '󰐗\tStart task "Planning"\tsuggested from window title · moves this window',
            '󰏫\tStart task with my own name…\ttype a custom name · moves this window',
            '󰉗\tTurn this workspace into a task…\tname this workspace · windows stay here',
            '--', '--width', '600'])
        self.assertFalse(any(args[0] == 'activeworkspace' for args in self.events('hyprctl')))
        self.assert_no_effect()

    def test_missing_requested_window_uses_empty_focused_workspace(self):
        self.empty_workspace()
        self.cfg['selection'] = 'Turn this workspace into a task…\tname this empty workspace'
        self.run_task('send', '--address', '0xdead')
        self.assertEqual(self.dispatches(), ['hl.dsp.workspace.rename({ workspace = "2", name = "Planning" })'])

    def test_empty_workspace_fallthrough_for_special_named_or_invalid(self):
        for workspace in (real_workspace(-99, 'special:scratch', 0), real_workspace(0, '0', 0),
                          real_workspace(2, 'Custom', 0), {}, real_workspace(2, '2', 1)):
            with self.subTest(workspace=workspace):
                self.empty_workspace()
                self.cfg['activeworkspace'] = workspace
                self.cfg['workspaces'] = [workspace] if workspace else []
                self.run_task('send')
                self.assertEqual(self.events('omarchy-menu-select'), [])
                self.assertEqual(self.events('omarchy-notification-send')[-1][-1], 'No tasks yet')
                self.assert_no_effect()

    def test_empty_workspace_name_rechecks_after_input(self):
        for rename in (False, True):
            for replacement in ([], [real_workspace(2, 'Taken', 0)]):
                with self.subTest(rename=rename, replacement=replacement):
                    self.empty_workspace()
                    if rename:
                        self.record()
                    self.cfg['selection'] = ('Rename this task…\tchange this empty task name' if rename else
                                             'Turn this workspace into a task…\tname this empty workspace')
                    self.cfg['input_updates'] = {'workspaces': replacement}
                    self.run_task('send')
                    self.assertEqual(self.dispatches(), [])
                    (self.state / '2.json').unlink(missing_ok=True)

    def test_empty_workspace_warning_only_when_name_is_ephemeral(self):
        for persistent, windows in ((True, 0), (False, 1)):
            with self.subTest(persistent=persistent, windows=windows):
                self.empty_workspace()
                updated = real_workspace(2, '2', windows)
                updated['ispersistent'] = persistent
                self.cfg.update(selection='Turn this workspace into a task…\tname this empty workspace',
                                input_updates={'workspaces': [updated]})
                self.run_task('send')
                self.assertEqual(self.events('omarchy-notification-send')[-1][-1], 'Started task "Planning"')
                (self.state / '2.json').unlink()

    def test_leaving_empty_named_workspace_prunes_record_when_workspace_disappears(self):
        self.empty_workspace()
        self.cfg['selection'] = 'Turn this workspace into a task…\tname this empty workspace'
        self.run_task('send')
        self.assertTrue((self.state / '2.json').exists())
        # Model Hyprland dropping the empty workspace after the user leaves it.
        self.cfg['workspaces'] = [real_workspace(1, '1', 0)]
        self.run_task('go')
        self.assertFalse((self.state / '2.json').exists())
        self.assertEqual(self.events('omarchy-notification-send')[-1][-1], 'No tasks yet')

    def test_empty_workspace_dry_run_prints_choices_without_input_or_state(self):
        self.empty_workspace()
        self.state.rmdir()
        result = self.run_task('send', '--dry-run')
        self.assertIn('Turn this workspace into a task…', result.stdout)
        self.assertEqual(self.events('omarchy-menu-select'), [])
        self.assertEqual(self.events('omarchy-menu-input'), [])
        self.assertEqual(self.events('omarchy-notification-send'), [])
        self.assertEqual(self.dispatches(), [])
        self.assertFalse(self.state.exists())
        self.assertFalse((self.runtime / 'taskspaces.lock').exists())

    def parked(self, used=True):
        for wsid, name, stamp in ((3, 'Field Job Posting', 200), (4, 'Quarterly budget', 100)):
            self.cfg['workspaces'].append({'id': wsid, 'name': name})
            record = {'id': wsid, 'name': name, 'source': 1}
            if used:
                record['used'] = stamp
            (self.state / f'{wsid}.json').write_text(json.dumps(record))
        self.cfg['clients'] += [real_window('0xdef', 'org.gnome.Nautilus', 'Job description', 3, 'Field Job Posting'),
                                real_window('0xa1', 'kitty', 'Notes', 4, 'Quarterly budget'),
                                real_window('0xa2', 'kitty', 'Budget', 4, 'Quarterly budget')]

    def test_named_menu_order_summaries_and_recent_use(self):
        self.parked()
        self.cfg['selection'] = 'Cancel'
        self.run_task('send')
        self.assertEqual(self.menu()[1:-3], [
            '󰐗\tStart task "Planning"\tsuggested from window title · moves this window',
            '󰏫\tStart task with my own name…\ttype a custom name · moves this window',
            '󰁌\tSend to "Field Job Posting"\tFiles · moves this window',
            '󰁌\tSend to "Quarterly budget"\tTerminal ×2 · moves this window',
            '󰉒\tGo to a task…\tswitch tasks · leaves this window here',
            '󰉗\tTurn this workspace into a task…\tname this workspace · windows stay here'])
        self.assert_no_moves()

    def test_menu_situation_1_plain_workspace_without_tasks(self):
        self.cfg['selection'] = 'Cancel'
        self.run_task('send')
        self.assertEqual(self.menu(), [
            'Task',
            '󰐗\tStart task "Planning"\tsuggested from window title · moves this window',
            '󰏫\tStart task with my own name…\ttype a custom name · moves this window',
            '󰉗\tTurn this workspace into a task…\tname this workspace · windows stay here',
            '--', '--width', '600'])
        self.assert_no_effect()

    def test_menu_situation_2_browser_on_plain_workspace_with_parked_task(self):
        self.parked()
        (self.state / '4.json').unlink()
        self.cfg['activewindow']['class'] = 'google-chrome'
        self.cfg['selection'] = 'Cancel'
        self.run_task('send')
        self.assertEqual(self.menu(), [
            'Task',
            '󰐗\tStart task "Planning"\tsuggested from window title · whole window (all tabs) · moves this window',
            '󰏫\tStart task with my own name…\ttype a custom name · moves this window',
            '󰁌\tSend to "Field Job Posting"\tFiles · moves this window',
            '󰉒\tGo to a task…\tswitch tasks · leaves this window here',
            '󰉗\tTurn this workspace into a task…\tname this workspace · windows stay here',
            '--', '--width', '600'])
        self.assert_no_moves()

    def test_menu_situation_3_window_in_active_task(self):
        self.parked()
        self.record(name='Current task')
        self.cfg['selection'] = 'Cancel'
        self.run_task('send')
        self.assertEqual(self.menu(), [
            'Task',
            '󰐗\tStart task "Planning"\tsuggested from window title · moves this window',
            '󰏫\tStart task with my own name…\ttype a custom name · moves this window',
            '󰁌\tSend to "Field Job Posting"\tFiles · moves this window',
            '󰁌\tSend to "Quarterly budget"\tTerminal ×2 · moves this window',
            '󰉒\tGo to a task…\tswitch tasks · leaves this window here',
            '󰏫\tRename this task…\tchange task name · windows stay here',
            '--', '--width', '600'])
        self.assert_no_moves()

    def test_menu_situation_4_named_plain_workspace(self):
        self.parked()
        self.cfg['workspaces'][1]['name'] = 'Desk'
        self.cfg['selection'] = 'Cancel'
        self.run_task('send')
        self.assertEqual(self.menu(), [
            'Task',
            '󰐗\tStart task "Planning"\tsuggested from window title · moves this window',
            '󰏫\tStart task with my own name…\ttype a custom name · moves this window',
            '󰁌\tSend to "Field Job Posting"\tFiles · moves this window',
            '󰁌\tSend to "Quarterly budget"\tTerminal ×2 · moves this window',
            '󰉒\tGo to a task…\tswitch tasks · leaves this window here',
            '--', '--width', '600'])
        self.assert_no_moves()

    def test_menu_situation_5_no_focused_window_keeps_go_list(self):
        self.parked()
        self.cfg['activewindow'] = {}
        self.cfg['selection'] = 'Cancel'
        self.run_task('send')
        self.assertEqual(self.menu(), [
            'Go to task',
            '󰉒\tField Job Posting\tFiles',
            '󰉒\tQuarterly budget\tTerminal ×2',
            '--', '--width', '600'])
        self.assert_no_moves()

    def test_default_first_row_starts_suggested_task_with_parked_tasks(self):
        self.parked()
        self.cfg['select_first'] = True
        self.run_task('send')
        self.assertEqual(self.menu()[1],
                         '󰐗\tStart task "Planning"\tsuggested from window title · moves this window')
        self.assertEqual(self.menu()[-3:], ['--', '--width', '600'])
        self.assertEqual(json.loads((self.state / '5.json').read_text())['name'], 'Planning')
        self.assertEqual(self.dispatches()[-1],
                         'hl.dsp.workspace.rename({ workspace = "5", name = "Planning" })')

    def test_send_task_named_like_action_row_and_empty_summary(self):
        for name in ('Go to a task…',
                     'Start task with my own name…', 'Rename this task…',
                     'Turn this workspace into a task…'):
            with self.subTest(name=name):
                self.cfg['workspaces'] = [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'},
                                          {'id': 3, 'name': name}]
                (self.state / '3.json').write_text(json.dumps({'id': 3, 'name': name, 'source': 1}))
                self.cfg['selection'] = f'Send to "{name}"\tno windows yet · moves this window'
                self.run_task('send')
                self.assertEqual(self.dispatches()[-1],
                                 'hl.dsp.window.move({ window = "address:0xabc", workspace = "3", follow = true })')
                self.assertEqual(self.events('omarchy-menu-input'), [])
                self.assertEqual(self.events('omarchy-notification-send')[-1][-1], f'Sent to "{name}"')
                # The focused window moves back only in the mock fixture for the next case.
                self.cfg['clients'] = [copy.deepcopy(self.cfg['activewindow'])]

    def assert_no_moves(self):
        self.assertFalse(any('window.move' in call for call in self.dispatches()))

    def test_go_focuses_by_full_row_and_updates_use_without_moving(self):
        self.parked(used=False)
        self.cfg['selection'] = 'Quarterly budget\tTerminal ×2'
        before = copy.deepcopy(self.cfg['clients'])
        self.run_task('go')
        self.assertEqual(self.menu()[0], 'Go to task')
        self.assertEqual(self.dispatches(), ['hl.dsp.focus({ workspace = "4" })'])
        self.assertEqual(self.cfg['clients'], before)
        self.assertIsInstance(json.loads((self.state / '4.json').read_text())['used'], int)
        self.cfg['selection'] = 'Cancel'
        self.run_task('go')
        self.assertIn('Quarterly budget', self.menu()[1])
        self.assertIn('Field Job Posting', self.menu()[2])

    def test_send_empty_and_go_row_open_same_go_list(self):
        self.parked()
        self.cfg['selections'] = ['Go to a task…\tswitch tasks · leaves this window here', 'Field Job Posting\tFiles']
        self.run_task('send', '--silent')
        self.assertEqual(self.dispatches(), ['hl.dsp.focus({ workspace = "3" })'])
        self.cfg['activewindow'] = {}
        self.cfg['selection'] = 'Quarterly budget\tTerminal ×2'
        self.run_task('send')
        self.assertEqual(self.menu()[0], 'Go to task')
        self.assert_no_moves()

    def test_go_back_reopens_both_parent_menus_repeatedly_without_changes(self):
        original = copy.deepcopy(self.cfg)
        for empty in (False, True):
            with self.subTest(empty=empty):
                self.cfg = copy.deepcopy(original)
                if empty:
                    self.empty_workspace()
                self.parked()
                (self.root / 'events.jsonl').write_text('')
                go = 'Go to a task…\t' + ('switch to another task' if empty else
                                         'switch tasks · leaves this window here')
                back = 'Back\treturn to the task menu'
                self.cfg['selections'] = [go, back, go, back, go, back, 'Cancel']
                before = {p.name: p.read_bytes() for p in self.state.glob('*.json')}
                windows = copy.deepcopy(self.cfg['clients'])
                workspaces = copy.deepcopy(self.cfg['workspaces'])
                self.run_task('send')
                menus = self.events('omarchy-menu-select')
                self.assertEqual([m[0] for m in menus], ['Task', 'Go to task'] * 3 + ['Task'])
                for menu in menus[::2]:
                    self.assertEqual(menu, menus[0])
                for menu in menus[1::2]:
                    self.assertEqual(menu[-4], '󰁍\t' + back)
                self.assertEqual(self.dispatches(), [])
                self.assertFalse(any(a[0] == 'eval' for a in self.events('hyprctl')))
                self.assertEqual({p.name: p.read_bytes() for p in self.state.glob('*.json')}, before)
                self.assertEqual(self.cfg['clients'], windows)
                self.assertEqual(self.cfg['workspaces'], workspaces)

    def test_direct_go_has_no_back_row(self):
        self.parked()
        self.cfg['selection'] = 'Back\treturn to the task menu'
        self.run_task('go')
        self.assertFalse(any(row.startswith('󰁍\tBack\t') for row in self.menu()))
        self.assertEqual(len(self.events('omarchy-menu-select')), 1)
        self.assertEqual(self.dispatches(), [])

    def test_task_named_back_is_distinct_from_back_navigation(self):
        self.cfg['workspaces'].append(real_workspace(3, 'Back'))
        self.cfg['clients'].append(real_window('0xdef', 'kitty', 'Notes', 3, 'Back'))
        (self.state / '3.json').write_text(json.dumps({'id': 3, 'name': 'Back', 'source': 1}))
        self.cfg['selections'] = ['Go to a task…\tswitch tasks · leaves this window here', 'Back\tTerminal']
        self.run_task('send')
        self.assertIn('󰉒\tBack\tTerminal', self.menu())
        self.assertEqual(self.menu()[-4], '󰁍\tBack\treturn to the task menu')
        self.assertEqual(self.dispatches(), ['hl.dsp.focus({ workspace = "3" })'])

    def test_escape_in_go_list_exits_both_parent_menus(self):
        original = copy.deepcopy(self.cfg)
        for empty in (False, True):
            with self.subTest(empty=empty):
                self.cfg = copy.deepcopy(original)
                if empty:
                    self.empty_workspace()
                self.parked()
                (self.root / 'events.jsonl').write_text('')
                go = 'Go to a task…\t' + ('switch to another task' if empty else
                                         'switch tasks · leaves this window here')
                self.cfg['selections'] = [go, None]
                before = {p.name: p.read_bytes() for p in self.state.glob('*.json')}
                self.run_task('send')
                self.assertEqual([m[0] for m in self.events('omarchy-menu-select')], ['Task', 'Go to task'])
                self.assertEqual(self.dispatches(), [])
                self.assertFalse(any(a[0] == 'eval' for a in self.events('hyprctl')))
                self.assertEqual({p.name: p.read_bytes() for p in self.state.glob('*.json')}, before)

    def test_back_preserves_original_window_when_focus_changes(self):
        self.parked()
        self.cfg['menu_updates'] = {'activewindow': copy.deepcopy(self.cfg['clients'][1])}
        self.cfg['selections'] = ['Go to a task…\tswitch tasks · leaves this window here',
                                  'Back\treturn to the task menu',
                                  'Send to "Quarterly budget"\tTerminal ×2 · moves this window']
        self.run_task('send')
        self.assertEqual(self.dispatches(), [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "4", follow = true })'])
        self.assertEqual(next(w['workspace']['id'] for w in self.cfg['clients'] if w['address'] == '0xdef'), 3)

    def test_back_preserves_original_empty_workspace_when_focus_changes(self):
        self.empty_workspace()
        self.parked()
        self.cfg['menu_updates'] = {'activeworkspace': real_workspace(1, '1', 0)}
        self.cfg['selections'] = ['Go to a task…\tswitch to another task',
                                  'Back\treturn to the task menu',
                                  'Turn this workspace into a task…\tname this empty workspace']
        self.run_task('send')
        self.assertEqual(self.dispatches(), ['hl.dsp.workspace.rename({ workspace = "2", name = "Planning" })'])
        self.assertEqual(self.cfg['activeworkspace']['id'], 1)
        self.assertEqual(json.loads((self.state / '2.json').read_text())['source'], 2)

    def test_send_named_task_shared_suggestion_and_silent(self):
        self.parked()
        self.cfg['activewindow']['title'] = 'Field technician job description.pdf'
        self.cfg['selection'] = 'Send to "Field Job Posting"\tFiles · moves this window'
        self.run_task('send', '--silent')
        self.assertEqual(self.dispatches(), [
            'hl.dsp.window.move({ window = "address:0xabc", workspace = "3", follow = false })'])
        self.assertGreater(json.loads((self.state / '3.json').read_text())['used'], 200)
        self.assertEqual(self.events('omarchy-notification-send')[-1][-1], 'Sent to "Field Job Posting"')

    def test_task_selection_requires_complete_row(self):
        self.parked()
        for selection in ('Field Job Posting', 'Field Job Posting\twrong', 'hl.dsp.focus({})',
                          'Send to "Field Job Posting"',
                          'Send to "Field Job Posting"\twrong'):
            self.cfg['selection'] = selection
            self.run_task('send')
            self.run_task('go')
        self.assertEqual(self.dispatches(), [])
        self.assertEqual(self.events('omarchy-notification-send'), [])

    def test_used_on_suggested_typed_and_in_place_start(self):
        for label in ('Start task "Planning"\tsuggested from window title · moves this window',
                      'Start task with my own name…\ttype a custom name · moves this window',
                      'Turn this workspace into a task…\tname this workspace · windows stay here'):
            with self.subTest(label=label):
                for file in self.state.glob('*.json'):
                    file.unlink()
                self.cfg['workspaces'] = [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'}]
                self.cfg['selection'] = label
                self.run_task('send')
                record = json.loads(next(self.state.glob('*.json')).read_text())
                self.assertEqual(record['used'], record['created'])
                self.assertEqual(self.events('omarchy-notification-send')[-1][-1], 'Started task "Planning"')

    def test_go_empty_and_dry_run_have_no_side_effects(self):
        self.run_task('go')
        self.assertEqual(self.events('omarchy-notification-send')[-1][-1], 'No tasks yet')
        self.parked()
        before = {p.name: p.read_bytes() for p in self.state.iterdir()}
        (self.runtime / 'taskspaces.lock').unlink()
        (self.root / 'events.jsonl').unlink()
        result = self.run_task('go', '--dry-run')
        self.assertIn('hl.dsp.focus', result.stdout)
        self.assertEqual(self.events('omarchy-menu-select'), [])
        self.assertEqual(self.dispatches(), [])
        self.assertFalse((self.runtime / 'taskspaces.lock').exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.state.iterdir()})

    def test_parked_task_acceptance_walkthrough(self):
        # Start a named browser task, then a suggested terminal task elsewhere.
        self.cfg['activewindow']['class'] = 'google-chrome'
        self.cfg.update(selection='Start task with my own name…\ttype a custom name · moves this window', input='Field Job Posting')
        self.run_task('send')
        self.assertEqual(next(w for w in self.cfg['workspaces'] if w['id'] == 3)['name'], 'Field Job Posting')
        terminal = real_window('0xdef', 'kitty', 'Quarterly budget', 2, '2')
        self.cfg['clients'].append(terminal)
        self.cfg['activewindow'] = copy.deepcopy(terminal)
        self.cfg['selection'] = 'Start task "Quarterly budget"\tsuggested from window title · moves this window'
        self.run_task('send')
        self.assertEqual(next(w for w in self.cfg['workspaces'] if w['id'] == 4)['name'], 'Quarterly budget')
        for address, silent in (('0xa1', False), ('0xa2', True)):
            window = real_window(address, 'org.gnome.Nautilus', 'Field technician job description.pdf', 2, '2')
            self.cfg['clients'].append(window)
            self.cfg['activewindow'] = copy.deepcopy(window)
            # The full row for the parked task is distinct from the suggested name.
            summary = 'Chrome' if not silent else 'Chrome, Files'
            self.cfg['selection'] = 'Send to "Field Job Posting"\t' + summary + ' · moves this window'
            self.run_task('send', *(['--silent'] if silent else []))
            self.assertEqual(self.dispatches()[-1],
                             f'hl.dsp.window.move({{ window = "address:{address}", workspace = "3", follow = {str(not silent).lower()} }})')
            self.assertEqual(self.events('omarchy-notification-send')[-1][-1], 'Sent to "Field Job Posting"')
        for command in ('go', 'send'):
            self.cfg['activewindow'] = {}
            self.cfg['selection'] = 'Field Job Posting\tChrome, Files ×2'
            before = copy.deepcopy(self.cfg['clients'])
            self.run_task(command)
            self.assertEqual(self.menu()[0], 'Go to task')
            self.assertEqual(self.dispatches()[-1], 'hl.dsp.focus({ workspace = "3" })')
            self.assertEqual(self.cfg['clients'], before)
        self.cfg['activeworkspace'] = {'id': 3, 'name': 'Field Job Posting'}
        self.cfg['selection'] = 'Cancel'
        self.run_task('finish')
        self.assertIn('󰖭\tClose 3 windows and finish\tChrome, Files ×2', self.menu())
        self.assertTrue(any('Keep 3 windows and finish' in row for row in self.menu()))

    def test_go_cancel_stale_workspace_and_dispatch_failure_preserve_use(self):
        self.parked()
        before = (self.state / '3.json').read_bytes()
        self.cfg['selection'] = 'Cancel'
        self.run_task('go')
        self.assertEqual(self.dispatches(), [])
        self.cfg['selection'] = 'Field Job Posting\tFiles'
        self.cfg['dispatch_error'] = True
        self.run_task('go', expected=1)
        self.assertEqual((self.state / '3.json').read_bytes(), before)
        self.cfg.pop('dispatch_error')
        self.cfg['menu_updates'] = {'workspaces': [{'id': 3, 'name': 'Another task'}]}
        (self.root / 'events.jsonl').unlink()
        self.run_task('go')
        self.assertEqual(self.dispatches(), [])
        self.assertEqual((self.state / '3.json').read_bytes(), before)

    def test_suggested_send_row_and_description_select_the_same_task(self):
        for cls in ('kitty', 'google-chrome'):
            with self.subTest(cls=cls):
                self.cfg['activewindow']['class'] = cls
                description = 'suggested from window title'
                if cls == 'google-chrome':
                    description += ' · whole window (all tabs)'
                description += ' · moves this window'
                self.cfg['selection'] = 'Start task "Planning"\t' + description
                self.run_task('send')
                self.assertEqual(self.menu()[1:-3], [
                    '󰐗\tStart task "Planning"\t' + description,
                    '󰏫\tStart task with my own name…\ttype a custom name · moves this window',
                    '󰉗\tTurn this workspace into a task…\tname this workspace · windows stay here',
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
        self.cfg.update(selection='Start task with my own name…\ttype a custom name · moves this window', input='Plan "review"')
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
        self.cfg['selection'] = f'Start task "{name}"\tsuggested from window title · moves this window'
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
        self.cfg['selection'] = f'Start task "{name}"\tsuggested from window title · moves this window'
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

    def test_quoted_existing_task_row_matches_and_lua_string_escapes_quotes(self):
        name = 'Plan "review"'
        self.cfg['workspaces'].append({'id': 3, 'name': name})
        (self.state / '3.json').write_text(json.dumps({'id': 3, 'name': name, 'source': 1}))
        self.cfg['selection'] = f'Send to "{name}"\tno windows yet · moves this window'
        self.run_task('send')
        self.assertIn('󰁌\t' + self.cfg['selection'], self.menu())
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
                self.cfg['selection'] = 'Start task "Planning"\tsuggested from window title · moves this window'
                self.run_task('send')
                record = json.loads((self.state / '3.json').read_text())
                self.assertEqual((record['source'], record['source_name']), (1, '1'))
                self.assertFalse(any('Turn this workspace' in row for row in self.menu()))
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
        self.cfg['selection'] = 'Start task "Planning"\tsuggested from window title · moves this window'
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
                    'suggest': 'Start task "Task 2"\tsuggested from window title · moves this window',
                    'type': 'Start task with my own name…\ttype a custom name · moves this window',
                    'adopt': 'Turn this workspace into a task…\tname this workspace · windows stay here',
                    'rename': 'Rename this task…\tchange task name · windows stay here',
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
        self.cfg['selection'] = f'Start task "{expected}"\tsuggested from window title · moves this window'
        self.run_task('send')
        self.assertIn('󰐗\t' + self.cfg['selection'], self.menu())
        self.assertEqual(json.loads((self.state / '4.json').read_text())['name'], expected)
        self.assertLessEqual(len(expected), 35)

    def test_close_allows_saving_longer_than_five_seconds(self):
        self.record(source=1)
        self.cfg.update(selection='Close 1 window and finish', refuse_close=True, close_after_polls=5)
        self.run_task(code='source "$1"; sleep() { SECONDS=$((SECONDS + 2)); }; main finish')
        self.assertGreaterEqual(self.cfg['polls_since_close'], 5)
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
                self.assertFalse(any('Turn this workspace' in row for row in self.menu()))
                self.assert_no_effect()

    def test_existing_task_has_rename_only(self):
        self.record(source=1)
        self.run_task('send')
        self.assertIn('󰏫\tRename this task…\tchange task name · windows stay here', self.menu())
        self.assertFalse(any('Turn this workspace' in row for row in self.menu()))
        self.assertEqual(self.dispatches(), [])

    def test_plain_workspace_with_valid_state_cannot_adopt(self):
        (self.state / '2.json').write_text(json.dumps({'id': 2, 'name': '2', 'source': 1}))
        self.run_task('send')
        self.assertFalse(any('Turn this workspace' in row for row in self.menu()))
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
        self.cfg['clients'][0]['class'] = 'foot'
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
        self.cfg.update(selection='Rename this task…\tchange task name · windows stay here', input='Revised')
        self.run_task('send')
        record = json.loads((self.state / '2.json').read_text())
        self.assertEqual((record['name'], record['source'], record['id']), ('Revised', 2, 2))

    def test_adopted_task_appears_in_other_workspace_send_menu(self):
        self.run_task('send')
        self.cfg['activewindow']['workspace']['id'] = 1
        self.cfg['selection'] = 'Cancel'
        self.run_task('send')
        self.assertEqual(self.menu()[1:-3], [
            '󰐗\tStart task "Planning 2"\tsuggested from window title · moves this window',
            '󰏫\tStart task with my own name…\ttype a custom name · moves this window',
            '󰁌\tSend to "Planning"\tTerminal · moves this window',
            '󰉒\tGo to a task…\tswitch tasks · leaves this window here',
            '󰉗\tTurn this workspace into a task…\tname this workspace · windows stay here'])

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
        self.assertEqual(sent[-1][1], 'Started task "Planning"')

    def test_notifications_use_taskspaces_title(self):
        self.run_task('send')
        self.assertEqual(self.events('omarchy-notification-send')[-1][:3], ['-g', '󰌨', 'taskspaces'])

class MultiMonitorTests(unittest.TestCase):
    """Run actual commands with explicit workspace owners and output activation."""
    setUp = TaskTests.setUp
    set_settings = TaskTests.set_settings
    write_cfg = TaskTests.write_cfg
    run_task = TaskTests.run_task
    events = TaskTests.events
    dispatches = TaskTests.dispatches
    menu = TaskTests.menu

    def screens(self):
        self.two_screen_setting(True)
        self.cfg['workspaces'] = [real_workspace(1, '1'), real_workspace(2, '2')]
        self.cfg['workspaces'][0]['monitor'] = 'HDMI-A-1'
        self.cfg['monitors'] = [dict(id=0, name='eDP-1', focused=True, activeWorkspace={'id': 2, 'name': '2'}),
                                dict(id=1, name='HDMI-A-1', focused=False, activeWorkspace={'id': 1, 'name': '1'})]
        self.cfg['clients'] = [real_window('0xabc', 'kitty', 'Planning', 2, '2')]
        self.cfg['activewindow'] = copy.deepcopy(self.cfg['clients'][0])
        self.cfg['select_first'] = True

    def two_screen_setting(self, value):
        self.set_settings(two_screen=value)

    def test_two_screen_creation_requires_explicit_boolean_setting(self):
        for value in (None, False, 'true', 1):
            with self.subTest(value=value):
                self.screens()
                self.two_screen_setting(value)
                self.run_task('send')
                rec = json.loads((self.state / '3.json').read_text())
                self.assertNotIn('members', rec)
                self.assertEqual(self.active()['HDMI-A-1'], 1)
                self.assertFalse(any(a[0] == 'eval' for a in self.events('hyprctl')))
                (self.state / '3.json').unlink()

    def test_missing_setting_and_empty_workspace_stay_single_screen(self):
        self.screens()
        (self.root / 'config/omarchy/shell.json').unlink()
        self.cfg['activewindow'] = {}
        self.cfg['clients'] = []
        self.cfg['workspaces'][1]['windows'] = 0
        self.cfg['activeworkspace'] = copy.deepcopy(self.cfg['workspaces'][1])
        self.run_task('send')
        rec = json.loads((self.state / '2.json').read_text())
        self.assertNotIn('members', rec)
        self.assertEqual(self.active()['HDMI-A-1'], 1)

    def test_existing_pair_go_send_and_finish_work_with_setting_off(self):
        self.start()
        self.two_screen_setting(False)
        self.run_task('go')
        self.assertEqual(set(self.active().values()), {3, 4})
        incoming = real_window('0x111', 'kitty', 'Extra', 2, '2')
        self.cfg['clients'].append(incoming)
        self.cfg['activewindow'] = copy.deepcopy(incoming)
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Send to "Planning"\tTerminal · moves this window'
        self.run_task('send')
        self.assertEqual(next(w for w in self.cfg['clients'] if w['address'] == '0x111')['workspace']['id'], 3)
        self.finish_here(3, 'Keep 2 windows and finish')
        self.assertEqual({w['workspace']['id'] for w in self.cfg['clients']}, {2})
        self.assertFalse((self.state / '3.json').exists())

    def test_forget_pair_releases_rules_without_touching_windows(self):
        self.start()
        self.two_screen_setting(False)
        before = copy.deepcopy(self.cfg['clients'])
        active = self.active()
        (self.root / 'events.jsonl').write_text('')
        self.run_task('forget', '--task-id', '3')
        self.assertEqual(self.cfg['clients'], before)
        self.assertEqual(self.active(), active)
        self.assertFalse((self.state / '3.json').exists())
        self.assertEqual(self.cfg['owned_rules'], {})
        self.assertTrue(all(r.get('enabled') is False for r in self.cfg['workspacerules']))
        self.assertEqual({w['id']: w['name'] for w in self.cfg['workspaces'] if w['id'] in (3, 4)}, {3: '3', 4: '4'})
        self.assertTrue(all(c.startswith('hl.dsp.workspace.rename') for c in self.dispatches()))

    def test_forget_cleanup_failure_keeps_pair_and_every_window(self):
        self.start()
        before = copy.deepcopy(self.cfg['clients'])
        self.cfg['eval_error'] = True
        (self.root / 'events.jsonl').write_text('')
        self.run_task('forget', '--task-id', '3', expected=1)
        self.assertTrue((self.state / '3.json').exists())
        self.assertEqual(self.cfg['clients'], before)
        self.assertEqual(self.dispatches(), [])

    def test_stuck_go_and_finish_offer_forget_or_cancel(self):
        for action, choice in (('go', 'Cancel'), ('go', 'Forget this task'), ('finish', 'Forget this task')):
            with self.subTest(action=action, choice=choice):
                self.screens()
                record = self.pair()
                self.cfg['workspaces'][-1]['name'] = 'Changed by hand'
                self.cfg['activeworkspace'] = copy.deepcopy(self.cfg['workspaces'][-1])
                self.cfg['select_first'] = False
                self.cfg['selections'] = (['Planning\tTerminal, Chrome', choice] if action == 'go' else [choice])
                before = copy.deepcopy(self.cfg['clients'])
                result = self.run_task(action, expected=1 if choice == 'Cancel' else 0)
                self.assertIn('Press Super+D to forget it; your windows stay where they are.', result.stderr)
                self.assertNotIn('retained', result.stderr)
                self.assertIn('Forget this task', ' '.join(self.menu()))
                self.assertEqual(self.cfg['clients'], before)
                self.assertEqual((self.state / '3.json').exists(), choice == 'Cancel')

    def start(self, *args):
        self.screens()
        self.run_task('send', *args)
        return json.loads((self.state / '3.json').read_text())

    def pair(self, empty_other=False):
        self.screens()
        record = dict(id=3, name='Planning', source=2, source_name='2', created=100, used=100,
                      members=[dict(id=3, name='taskspaces-3-1', output='eDP-1', source=2, source_name='2'),
                               dict(id=4, name='taskspaces-3-2', output='HDMI-A-1', source=1, source_name='1')])
        for m in record['members']:
            ws = real_workspace(m['id'], m['name'], 0)
            ws['monitor'] = m['output']
            self.cfg['workspaces'].append(ws)
        self.cfg['clients'] = [real_window('0xabc', 'kitty', 'Planning', 3, 'taskspaces-3-1')]
        if not empty_other:
            win = real_window('0xdef', 'google-chrome', 'Reference', 4, 'taskspaces-3-2')
            win['monitor'] = 1
            self.cfg['clients'].append(win)
        (self.state / '3.json').write_text(json.dumps(record))
        return record

    def saved(self):
        return json.loads((self.state / '3.json').read_text())

    def labels(self):
        # Same arguments as the bar helper; no shell CLI lock is held here.
        return self.run_task(code='source "$1"; dry=true; state_dir="$XDG_RUNTIME_DIR/taskspaces"; member_tool labels')

    def closed_all(self):
        """Post-close-all snapshot, not a simulation of real workspace destruction."""
        record = self.pair()
        record['members'][1]['id'] = 5
        record['members'][0]['name'] = 'Planning'
        record['members'][1]['name'] = 'Planning ·'
        (self.state / '3.json').write_text(json.dumps(record))
        (self.state / '7.json').write_text(json.dumps(dict(id=7, name='Single', source=1)))
        self.cfg['clients'] = []
        self.cfg['activewindow'] = {}
        self.cfg['activeworkspace'] = real_workspace(1, '1', 0)
        leftover = real_workspace(6, 'taskspaces-99-2', 0)
        leftover['monitor'] = 'HDMI-A-1'
        self.cfg['workspaces'] = [real_workspace(1, '1', 0), leftover]
        self.cfg['monitors'][0]['activeWorkspace'] = {'id': 1, 'name': '1'}
        self.cfg['monitors'][1]['activeWorkspace'] = {'id': 6, 'name': leftover['name']}
        self.cfg['no_persistent_creation'] = True
        names = {3: 'Planning', 5: 'Planning ·', 7: 'Single', 6: leftover['name']}
        self.cfg['workspacerules'] = [dict(workspaceString=str(i), enabled=True,
                                          persistent=True, defaultName=name) for i, name in names.items()]
        self.cfg['owned_rules'] = {str(i): name for i, name in names.items()}

    def test_close_all_prunes_records_on_bar_then_rules_on_next_cli(self):
        self.closed_all()
        self.assertEqual(json.loads(self.labels().stdout), {})
        self.assertEqual(list(self.state.glob('*.json')), [])
        self.assertEqual(self.dispatches(), [])
        self.assertFalse(any(a[0] == 'eval' for a in self.events('hyprctl')))
        self.run_task('go')
        self.assertEqual(self.cfg['clients'], [])
        self.assertEqual(self.cfg['owned_rules'], {})
        self.assertTrue(all(r.get('enabled') is False for r in self.cfg['workspacerules']))
        self.assertEqual({w['id']: w['name'] for w in self.cfg['workspaces']}, {1: '1', 6: '6'})
        self.assertTrue(all(d.startswith('hl.dsp.workspace.rename') for d in self.dispatches()))
        (self.root / 'events.jsonl').write_text('')
        self.labels()
        self.run_task('go')
        self.assertEqual(self.dispatches(), [])
        self.assertFalse(any(a[0] == 'eval' for a in self.events('hyprctl')))

    def test_close_all_next_start_reuses_lowest_stock_workspace_numbers(self):
        self.closed_all()
        self.labels()
        incoming = real_window('0x777', 'kitty', 'New work', 1, '1')
        self.cfg['clients'] = [incoming]
        self.cfg['activewindow'] = copy.deepcopy(incoming)
        self.cfg['select_first'] = True
        self.run_task('send')
        task = json.loads((self.state / '2.json').read_text())
        self.assertEqual([m['id'] for m in task['members']], [2, 3])
        self.assertFalse((self.state / '3.json').exists())
        self.assertFalse((self.state / '7.json').exists())

    def test_close_all_cli_retires_without_bar_refresh(self):
        self.closed_all()
        self.run_task('go')
        self.assertEqual(list(self.state.glob('*.json')), [])
        self.assertEqual(list(self.state.glob('*.cleanup')), [])
        self.assertEqual(self.cfg['owned_rules'], {})
        self.assertEqual(self.cfg['clients'], [])
        self.assertTrue(all(d.startswith('hl.dsp.workspace.rename') for d in self.dispatches()))

    def test_close_all_single_record_with_window_survives_even_a_name_change(self):
        self.closed_all()
        self.cfg['workspaces'].append(real_workspace(7, 'Changed by hand', 1))
        window = real_window('0x777', 'kitty', 'Keep me', 7, 'Changed by hand')
        self.cfg['clients'] = [window]
        before = (self.state / '7.json').read_bytes()
        self.labels()
        self.run_task('go')
        self.assertEqual((self.state / '7.json').read_bytes(), before)
        self.assertEqual(self.cfg['clients'], [window])
        self.assertFalse(any('window.' in d for d in self.dispatches()))

    def test_close_all_live_member_windows_protect_records(self):
        for half_gone, inconsistent in ((False, False), (True, False), (True, True)):
            with self.subTest(half_gone=half_gone, inconsistent=inconsistent):
                self.pair(empty_other=True)
                if half_gone:
                    self.cfg['workspaces'] = [w for w in self.cfg['workspaces'] if w['id'] != 4]
                if inconsistent:
                    self.cfg['workspaces'] = self.cfg['workspaces'][:2]
                before = (self.state / '3.json').read_bytes()
                windows = copy.deepcopy(self.cfg['clients'])
                self.labels()
                self.assertEqual((self.state / '3.json').read_bytes(), before)
                self.assertEqual(self.cfg['clients'], windows)
                self.assertEqual(self.dispatches(), [])
                self.assertFalse(any(a[0] == 'eval' for a in self.events('hyprctl')))

    def test_close_all_existing_empty_task_and_half_pair_are_kept(self):
        self.pair(empty_other=True)
        self.cfg['clients'] = []
        self.cfg['workspaces'] = [w for w in self.cfg['workspaces'] if w['id'] != 4]
        single = real_workspace(7, 'Blank task', 0)
        self.cfg['workspaces'].append(single)
        (self.state / '7.json').write_text(json.dumps(dict(id=7, name='Blank task', source=7)))
        before = {p.name: p.read_bytes() for p in self.state.glob('*.json')}
        self.labels()
        self.assertEqual({p.name: p.read_bytes() for p in self.state.glob('*.json')}, before)
        self.assertEqual(self.dispatches(), [])

    def test_close_all_bar_respects_cli_lock_and_dry_run_preserves_records(self):
        self.closed_all()
        before = {p.name: p.read_bytes() for p in self.state.glob('*.json')}
        with (self.runtime / 'taskspaces.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.labels()
            self.assertEqual({p.name: p.read_bytes() for p in self.state.glob('*.json')}, before)
        self.run_task('go', '--dry-run')
        self.assertEqual({p.name: p.read_bytes() for p in self.state.glob('*.json')}, before)
        self.assertEqual(list(self.state.glob('*.cleanup')), [])
        self.labels()
        self.assertEqual(list(self.state.glob('*.json')), [])

    def test_close_all_pending_cleanup_restores_readable_names_without_window_moves(self):
        self.closed_all()
        self.labels()
        self.cfg['workspaces'].append(real_workspace(3, 'Planning', 0))
        self.cfg['select_cancel'] = True
        self.run_task('go')
        self.assertEqual(next(w['name'] for w in self.cfg['workspaces'] if w['id'] == 3), '3')
        self.assertTrue(all(d.startswith('hl.dsp.workspace.rename') for d in self.dispatches()))
        self.assertEqual(self.cfg['clients'], [])

    def owners(self):
        return {w['id']: w['monitor'] for w in self.cfg['workspaces']}

    def active(self):
        return {m['name']: m['activeWorkspace']['id'] for m in self.cfg['monitors']}

    def unplug(self, output='eDP-1'):
        self.cfg['monitors'] = [m for m in self.cfg['monitors'] if m['name'] == output]
        self.cfg['monitors'][0]['focused'] = True
        for ws in self.cfg['workspaces']: ws['monitor'] = output

    def reconnect(self):
        self.cfg['monitors'].append(dict(id=1, name='HDMI-A-1', focused=False, activeWorkspace={'id': 1, 'name': '1'}))

    def finish_here(self, member=4, choice='Close 2 windows and finish'):
        self.cfg['activeworkspace'] = next(w for w in self.cfg['workspaces'] if w['id'] == member)
        self.cfg['select_first'] = False
        self.cfg['selection'] = choice
        return self.run_task('finish')

    def test_new_task_owns_two_outputs_with_one_window(self):
        rec = self.start()
        self.assertEqual([m['id'] for m in rec['members']], [3, 4])
        self.assertEqual(len(self.cfg['clients']), 1)
        self.assertEqual(self.cfg['clients'][0]['workspace']['id'], 3)
        self.assertEqual(self.active(), {'eDP-1': 3, 'HDMI-A-1': 4})
        self.assertEqual(self.owners()[4], 'HDMI-A-1')
        self.assertEqual(len({m['name'] for m in rec['members']}), 2)
        self.assertTrue(self.cfg['monitors'][0]['focused'])

    def test_start_from_external_keeps_window_there(self):
        self.screens()
        for m in self.cfg['monitors']: m['focused'] = m['name'] == 'HDMI-A-1'
        self.cfg['clients'][0]['monitor'] = 1
        self.cfg['activewindow'] = copy.deepcopy(self.cfg['clients'][0])
        self.run_task('send')
        self.assertEqual(self.saved()['members'][0]['output'], 'HDMI-A-1')
        self.assertEqual(self.owners()[3], 'HDMI-A-1')
        self.assertTrue(self.cfg['monitors'][1]['focused'])

    def test_start_silent_leaves_both_views(self):
        self.screens()
        before = self.active()
        self.run_task('send', '--silent')
        self.assertEqual(self.active(), before)
        self.assertFalse(any('hl.dsp.focus' in d for d in self.dispatches()))
        self.assertEqual(self.cfg['clients'][0]['workspace']['id'], 3)

    def test_empty_workspace_naming_adds_empty_companion(self):
        self.screens()
        self.cfg['clients'] = []
        self.cfg['activewindow'] = {}
        self.cfg['workspaces'][1]['windows'] = 0
        self.run_task('send')
        record = json.loads((self.state / '2.json').read_text())
        self.assertEqual([m['id'] for m in record['members']], [2, 3])
        self.assertEqual(self.cfg['clients'], [])
        self.assertEqual(self.active(), {'eDP-1': 2, 'HDMI-A-1': 3})

    def test_go_selects_one_row_for_two_members(self):
        self.pair()
        self.run_task('go')
        rows = [r for r in self.menu() if r.startswith('󰉒')]
        self.assertEqual(len(rows), 1)
        self.assertIn('Terminal, Chrome', rows[0])
        self.assertNotIn('taskspaces-3', ''.join(self.menu()))
        self.assertEqual(self.active(), {'eDP-1': 3, 'HDMI-A-1': 4})

    def test_go_restores_missing_empty_member_and_reserved_id(self):
        self.pair(empty_other=True)
        self.cfg['workspaces'] = [w for w in self.cfg['workspaces'] if w['id'] != 4]
        self.run_task('go')
        self.assertEqual(self.active()['HDMI-A-1'], 4)
        self.assertEqual(self.owners()[4], 'HDMI-A-1')
        self.assertEqual(len(self.saved()['members']), 2)

    def test_go_recovers_without_persistent_creation(self):
        self.pair(empty_other=True)
        self.cfg['workspaces'] = [w for w in self.cfg['workspaces'] if w['id'] != 4]
        self.cfg['no_persistent_creation'] = True
        self.run_task('go')
        self.assertEqual(self.active()['HDMI-A-1'], 4)
        self.assertEqual(next(w for w in self.cfg['workspaces'] if w['id'] == 4)['name'], 'Planning ·')

    def test_prune_retires_pair_when_both_members_missing_without_windows(self):
        self.pair(empty_other=True)
        self.cfg['clients'] = []
        self.cfg['workspaces'] = self.cfg['workspaces'][:2]
        self.run_task('go')
        self.assertFalse((self.state / '3.json').exists())
        self.assertEqual(self.active(), {'eDP-1': 2, 'HDMI-A-1': 1})
        self.assertEqual(self.dispatches(), [])

    def test_new_task_does_not_reuse_absent_reserved_member(self):
        self.pair(empty_other=True)
        self.cfg['workspaces'] = [w for w in self.cfg['workspaces'] if w['id'] != 4]
        self.cfg['activewindow'] = real_window('0x111', 'kitty', 'Other', 2, '2')
        self.cfg['clients'].append(self.cfg['activewindow'])
        self.run_task('send')
        other = json.loads((self.state / '5.json').read_text())
        self.assertEqual([m['id'] for m in other['members']], [5, 6])

    def test_go_refuses_live_member_name_collision(self):
        self.pair()
        next(w for w in self.cfg['workspaces'] if w['id'] == 4)['name'] = 'Unrelated'
        self.run_task('go', expected=1)
        self.assertEqual(self.dispatches(), [])
        self.assertTrue((self.state / '3.json').exists())

    def test_go_partial_dispatch_failure_retains_record(self):
        self.pair()
        self.cfg['fail_dispatch_at'] = 2
        self.run_task('go', expected=1)
        self.assertEqual(self.saved()['used'], 100)

    def test_rule_failure_retains_task(self):
        self.pair()
        self.cfg['eval_error'] = True
        self.run_task('go', expected=1)
        self.assertEqual(self.saved()['used'], 100)

    def test_existing_rule_is_never_replaced(self):
        self.pair()
        self.cfg['workspacerules'] = [{'workspaceString': '3', 'enabled': True}]
        self.run_task('go')
        calls = [a[1] for a in self.events('hyprctl') if a[0] == 'eval' and 'taskspaces:3' in a[1]]
        self.assertTrue(calls)
        self.assertTrue(all('; else ' not in c for c in calls))
        self.assertNotIn('3', self.cfg['owned_rules'])
        self.assertEqual(self.cfg['workspacerules'][0], {'workspaceString': '3', 'enabled': True})

    def test_send_routes_address_to_matching_screen_silently(self):
        self.pair()
        win = real_window('0x111', 'kitty', 'Incoming', 1, '1')
        win['monitor'] = 1
        self.cfg['clients'].append(win)
        self.cfg['activewindow'] = copy.deepcopy(self.cfg['clients'][0])
        before = self.active()
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Send to "Planning"\tTerminal, Chrome · moves this window'
        self.run_task('send', '--silent', '--address', '0x111')
        self.assertEqual(next(w for w in self.cfg['clients'] if w['address'] == '0x111')['workspace']['id'], 4)
        self.assertEqual(self.active(), before)
        self.assertEqual(len(self.dispatches()), 1)

    def test_send_follow_activates_pair(self):
        self.pair()
        win = real_window('0x111', 'kitty', 'Incoming', 2, '2')
        self.cfg['clients'].append(win)
        self.cfg['activewindow'] = win
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Send to "Planning"\tTerminal, Chrome · moves this window'
        self.run_task('send')
        self.assertEqual(self.active(), {'eDP-1': 3, 'HDMI-A-1': 4})
        self.assertEqual(next(w for w in self.cfg['clients'] if w['address'] == '0x111')['workspace']['id'], 3)

    def test_same_task_send_row_hidden_from_secondary(self):
        self.pair()
        self.cfg['activewindow'] = self.cfg['clients'][1]
        self.cfg['select_cancel'] = True
        self.run_task('send')
        # A cancelled menu is still recorded, without its current task row.
        self.assertFalse(any(r.startswith('󰁌\tSend to "Planning"') for r in self.menu()))

    def test_finish_from_secondary_closes_union(self):
        self.pair()
        self.finish_here()
        self.assertEqual(self.cfg['clients'], [])
        self.assertFalse((self.state / '3.json').exists())
        self.assertIn('(2 screens)', self.menu()[0])
        self.assertEqual(sum('window.close' in d for d in self.dispatches()), 2)

    def test_finish_keep_returns_each_side_to_its_source(self):
        self.pair()
        self.finish_here(choice='Keep 2 windows and finish')
        self.assertEqual({w['address']: w['workspace']['id'] for w in self.cfg['clients']}, {'0xabc': 2, '0xdef': 1})
        self.assertFalse((self.state / '3.json').exists())

    def test_finish_cancel_changes_nothing(self):
        self.pair()
        self.finish_here(choice='Cancel')
        self.assertEqual(self.dispatches(), [])
        self.assertTrue((self.state / '3.json').exists())

    def test_finish_does_not_close_unreviewed_window(self):
        self.pair()
        extra = real_window('0x999', 'kitty', 'New dialog', 4, 'taskspaces-3-2')
        self.cfg['menu_updates'] = {'clients': copy.deepcopy(self.cfg['clients']) + [extra]}
        self.cfg['activeworkspace'] = self.cfg['workspaces'][-1]
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Close 2 windows and finish'
        self.run_task('finish', expected=1)
        self.assertEqual([w['address'] for w in self.cfg['clients']], ['0x999'])
        self.assertTrue((self.state / '3.json').exists())

    def test_finish_refused_close_retains_pair(self):
        self.pair()
        self.cfg['refuse_close'] = True
        self.cfg['activeworkspace'] = self.cfg['workspaces'][-1]
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Close 2 windows and finish'
        self.run_task('finish', expected=1)
        self.assertEqual(len(self.cfg['clients']), 2)
        self.assertTrue((self.state / '3.json').exists())

    def test_unplug_go_merges_and_records_original_member(self):
        self.pair()
        self.unplug()
        self.run_task('go')
        self.assertEqual({w['workspace']['id'] for w in self.cfg['clients']}, {3})
        self.assertEqual(self.saved()['merged_windows'][0]['member'], 4)
        self.assertEqual(self.saved()['merged_windows'][0]['address'], '0xdef')

    def test_unplug_external_only_uses_external_member(self):
        self.pair()
        self.unplug('HDMI-A-1')
        self.run_task('go')
        self.assertEqual({w['workspace']['id'] for w in self.cfg['clients']}, {4})
        self.assertEqual(self.saved()['merged_windows'][0]['member'], 3)

    def test_replug_go_splits_recorded_windows(self):
        self.pair()
        self.unplug()
        self.run_task('go')
        self.reconnect()
        self.run_task('go')
        self.assertEqual({w['address']: w['workspace']['id'] for w in self.cfg['clients']}, {'0xabc': 3, '0xdef': 4})
        self.assertEqual(self.saved()['merged_windows'], [])
        self.assertEqual(self.active(), {'eDP-1': 3, 'HDMI-A-1': 4})

    def test_partial_merge_failure_keeps_recovery_intent_and_retry(self):
        self.pair()
        self.unplug()
        self.cfg['fail_matching'] = 'address:0xdef'
        self.run_task('go', expected=1)
        self.assertEqual(self.saved()['merged_windows'][0]['member'], 4)
        self.cfg.pop('fail_matching')
        self.run_task('go')
        self.assertEqual({w['workspace']['id'] for w in self.cfg['clients']}, {3})

    def test_acknowledged_but_ineffective_merge_retains_recovery(self):
        self.pair()
        self.unplug()
        self.cfg['ignore_moves'] = True
        self.run_task('go', expected=1)
        self.assertEqual(self.saved()['merged_windows'][0]['member'], 4)
        self.assertEqual(self.cfg['clients'][1]['workspace']['id'], 4)

    def test_partial_split_failure_retains_recovery_then_retries(self):
        self.pair()
        self.unplug()
        self.run_task('go')
        self.reconnect()
        self.cfg['fail_matching'] = 'address:0xdef'
        self.run_task('go', expected=1)
        self.assertEqual(len(self.saved()['merged_windows']), 1)
        self.cfg.pop('fail_matching')
        self.run_task('go')
        self.assertEqual(self.saved()['merged_windows'], [])

    def test_split_does_not_fetch_window_moved_to_unrelated_workspace(self):
        self.pair()
        self.unplug()
        self.run_task('go')
        self.cfg['clients'][1]['workspace'] = {'id': 2, 'name': '2'}
        self.reconnect()
        self.run_task('go')
        self.assertEqual(self.cfg['clients'][1]['workspace']['id'], 2)
        self.assertEqual(self.saved()['merged_windows'], [])

    def test_closed_merged_window_is_not_resurrected(self):
        self.pair()
        self.unplug()
        self.run_task('go')
        self.cfg['clients'].pop()
        self.reconnect()
        self.run_task('go')
        self.assertEqual(len(self.cfg['clients']), 1)
        self.assertEqual(self.saved()['merged_windows'], [])

    def test_finish_merged_keep_uses_original_sources(self):
        self.pair()
        self.unplug()
        self.run_task('go')
        self.finish_here(3, 'Keep 2 windows and finish')
        self.assertEqual({w['address']: w['workspace']['id'] for w in self.cfg['clients']}, {'0xabc': 2, '0xdef': 1})
        self.assertFalse((self.state / '3.json').exists())

    def test_paired_dry_run_never_writes_or_dispatches(self):
        self.pair()
        before = (self.state / '3.json').read_bytes()
        self.run_task('go', '--dry-run')
        self.assertEqual((self.state / '3.json').read_bytes(), before)
        self.assertEqual(self.dispatches(), [])
        self.assertFalse(any(a[0] == 'eval' for a in self.events('hyprctl')))
        self.assertFalse((self.runtime / 'taskspaces.lock').exists())

    def test_partial_finish_cleanup_can_retry(self):
        self.pair()
        self.cfg['activeworkspace'] = self.cfg['workspaces'][-1]
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Close 2 windows and finish'
        self.cfg['fail_matching'] = 'hl.dsp.focus'
        self.run_task('finish', expected=1)
        self.assertTrue((self.state / '3.json').exists())
        self.cfg.pop('fail_matching')
        self.cfg['activeworkspace'] = next(w for w in self.cfg['workspaces'] if w['id'] == 4)
        self.run_task('finish')
        self.assertFalse((self.state / '3.json').exists())

    def test_reused_window_address_does_not_receive_split(self):
        self.pair()
        self.unplug()
        self.run_task('go')
        self.cfg['clients'][1]['stableId'] = 'different-window'
        self.reconnect()
        self.run_task('go')
        self.assertEqual(self.saved()['merged_windows'], [])
        self.assertEqual(self.cfg['clients'][1]['workspace']['id'], 3)

    def test_documented_command_symlink_finds_companion_helper(self):
        self.pair()
        self.write_cfg()
        link = self.root / 'linked-taskspaces'
        link.symlink_to(SCRIPT)
        before = (self.state / '3.json').read_bytes()
        result = subprocess.run([BASH, str(link), 'go', '--dry-run'], env=self.env,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.state / '3.json').read_bytes(), before)
        self.assertEqual(self.dispatches(), [])

    def test_wrong_screen_creation_with_ignored_targeted_move_is_repaired(self):
        self.screens()
        self.cfg['ignore_targeted_workspace_move'] = True
        self.run_task('send')
        self.assertEqual(self.active(), {'eDP-1': 3, 'HDMI-A-1': 4})
        self.assertEqual(self.owners()[4], 'HDMI-A-1')
        self.assertTrue(any(a[0] == 'eval' and 'hl.exec_scheduled_prop_refresh_immediately()' in a[1] for a in self.events('hyprctl')))
        self.assertTrue(any(r.get('monitor') == 'HDMI-A-1' and r.get('persistent') for r in self.cfg['workspacerules']))

    def test_go_repairs_reported_half_built_task_without_stale_bar_jargon(self):
        self.screens()
        task = dict(id=1, name='Planning', source=2, source_name='2', created=100,
                    members=[dict(id=1, name='taskspaces-1-1', output='eDP-1', source=2, source_name='2'),
                             dict(id=3, name='taskspaces-1-2', output='HDMI-A-1', source=2, source_name='2')])
        (self.state / '1.json').write_text(json.dumps(task))
        self.cfg['workspaces'] = [real_workspace(1, 'taskspaces-1-1'), real_workspace(2, '2', 0), real_workspace(3, 'taskspaces-1-2', 0)]
        self.cfg['workspaces'][1]['monitor'] = 'HDMI-A-1'
        self.cfg['monitors'][0]['activeWorkspace'] = {'id': 1, 'name': 'taskspaces-1-1'}
        self.cfg['monitors'][1]['activeWorkspace'] = {'id': 2, 'name': '2'}
        self.cfg['clients'] = [real_window('0xabc', 'kitty', 'Planning', 1, 'taskspaces-1-1')]
        self.cfg['ignore_targeted_workspace_move'] = True
        self.cfg['workspacerules'] = [{'workspaceString': '1', 'enabled': True}, {'workspaceString': '3', 'enabled': True}]
        self.cfg['owned_rules'] = {'3': 'taskspaces-1-2'}
        self.run_task('go')
        self.assertEqual(self.active(), {'eDP-1': 1, 'HDMI-A-1': 3})
        self.assertEqual(self.owners()[3], 'HDMI-A-1')
        record = json.loads((self.state / '1.json').read_text())
        self.assertEqual([m['name'] for m in record['members']], ['Planning', 'Planning ·'])
        # An OLD widget displays the raw workspace name: those names must also
        # be readable, while the current widget resolves both to the shared name.
        for screen in self.cfg['monitors']:
            self.assertIn(screen['activeWorkspace']['name'], ['Planning', 'Planning ·'])
        self.assertNotIn('taskspaces-1-', str(self.events('omarchy-notification-send')))

    def test_new_member_names_are_readable_by_old_bar_and_rules_bind_outputs(self):
        rec = self.start()
        self.assertEqual([m['name'] for m in rec['members']], ['Planning', 'Planning ·'])
        for screen in self.cfg['monitors']:
            self.assertIn(screen['activeWorkspace']['name'], ['Planning', 'Planning ·'])
        self.assertNotIn('taskspaces-3-', str(self.events('omarchy-notification-send')))
        rules = [a[1] for a in self.events('hyprctl') if a[0] == 'eval' and 'hl.workspace_rule' in a[1]]
        self.assertTrue(any('monitor = "HDMI-A-1"' in code and 'default_name = "Planning ·"' in code for code in rules))
        self.assertTrue(any('monitor = "eDP-1"' in code and 'default_name = "Planning"' in code for code in rules))

    def test_readable_companion_name_avoids_existing_workspace_names(self):
        self.screens()
        other = real_workspace(5, 'Planning ·')
        other['monitor'] = 'HDMI-A-1'
        self.cfg['workspaces'].append(other)
        self.run_task('send')
        self.assertEqual([m['name'] for m in self.saved()['members']], ['Planning', 'Planning · ·'])
        self.assertEqual(next(w['name'] for w in self.cfg['workspaces'] if w['id'] == 5), 'Planning ·')

    def test_follow_send_prepares_visible_destination_before_moving_window(self):
        self.pair()
        win = real_window('0x111', 'kitty', 'Incoming', 2, '2')
        self.cfg['clients'].append(win)
        self.cfg['activewindow'] = win
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Send to "Planning"\tTerminal, Chrome · moves this window'
        self.cfg['fail_matching'] = 'hl.dsp.focus'
        self.run_task('send', expected=1)
        self.assertEqual(next(w['workspace']['id'] for w in self.cfg['clients'] if w['address'] == '0x111'), 2)
        self.assertFalse(any('window.move' in d for d in self.dispatches()))

    def test_follow_send_window_is_on_the_visible_member_of_its_screen(self):
        self.pair()
        win = real_window('0x111', 'kitty', 'Incoming', 1, '1')
        win['monitor'] = 1
        self.cfg['clients'].append(win)
        self.cfg['activewindow'] = win
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Send to "Planning"\tTerminal, Chrome · moves this window'
        self.run_task('send')
        sent = next(w for w in self.cfg['clients'] if w['address'] == '0x111')
        self.assertEqual(sent['workspace']['id'], self.active()['HDMI-A-1'])
        self.assertEqual(self.cfg['activeworkspace']['id'], 4)

    def test_prune_releases_orphan_owned_rule_and_preserves_windows(self):
        self.screens()
        self.cfg['workspaces'].append(real_workspace(5, 'taskspaces-99-2'))
        self.cfg['clients'].append(real_window('0x999', 'kitty', 'Keep me', 5, 'taskspaces-99-2'))
        self.cfg['workspacerules'] = [{'workspaceString': '5', 'enabled': True, 'persistent': True, 'defaultName': 'taskspaces-99-2'},
                                    {'workspaceString': '2', 'enabled': True}]
        self.cfg['owned_rules'] = {'5': 'taskspaces-99-2'}
        self.run_task('go')
        self.assertFalse(self.cfg['workspacerules'][0]['enabled'])
        self.assertEqual(self.cfg['owned_rules'], {})
        self.assertEqual(next(w['name'] for w in self.cfg['workspaces'] if w['id'] == 5), '5')
        self.assertEqual(len(self.cfg['clients']), 2)
        self.assertEqual(self.cfg['workspacerules'][1], {'workspaceString': '2', 'enabled': True})

    def test_go_repairs_reused_member_named_by_dead_task_and_missing_primary(self):
        self.screens()
        def task(tid, name, mids, outputs):
            return dict(id=tid, name=name, source=2, source_name='2', created=100, used=tid,
                        members=[dict(id=wid, name=f'taskspaces-{tid}-{i}', output=output, source=2, source_name='2')
                                 for i, (wid, output) in enumerate(zip(mids, outputs), 1)])
        one = task(1, 'First task', [1, 3], ['eDP-1', 'HDMI-A-1'])
        four = task(4, 'Second task', [4, 5], ['HDMI-A-1', 'eDP-1'])
        for record in [one, four]:
            (self.state / f'{record["id"]}.json').write_text(json.dumps(record))
        self.cfg['workspaces'] = [real_workspace(1, 'taskspaces-1-1'), real_workspace(2, '2'),
                                  real_workspace(3, 'taskspaces-1-2'), real_workspace(5, 'taskspaces-2-2')]
        for ws in self.cfg['workspaces'][1:]: ws['monitor'] = 'HDMI-A-1'
        self.cfg['clients'] = [real_window(hex(i + 100), 'kitty', f'Window {i}', ws['id'], ws['name'])
                               for i, ws in enumerate(self.cfg['workspaces'])]
        self.cfg['monitors'][0]['activeWorkspace'] = {'id': 1, 'name': 'taskspaces-1-1'}
        self.cfg['monitors'][1]['activeWorkspace'] = {'id': 5, 'name': 'taskspaces-2-2'}
        self.cfg['workspacerules'] = [{'workspaceString': str(w), 'enabled': True} for w in [1, 2, 4]]
        self.cfg['workspacerules'] += [dict(workspaceString='3', enabled=True, persistent=True, defaultName='taskspaces-1-2'),
                                      dict(workspaceString='5', enabled=True, persistent=True, defaultName='taskspaces-2-2')]
        self.cfg['owned_rules'] = {'3': 'taskspaces-1-2', '5': 'taskspaces-2-2'}
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Second task\tTerminal'
        self.cfg['ignore_targeted_workspace_move'] = True
        self.run_task('go')
        self.assertEqual(self.active(), {'eDP-1': 5, 'HDMI-A-1': 4})
        self.assertEqual(len(self.cfg['clients']), 4)
        self.assertEqual(next(w['name'] for w in self.cfg['workspaces'] if w['id'] == 5), 'Second task ·')
        self.assertFalse((self.state / '2.json').exists())
        self.assertFalse(any(r.get('enabled') is not False and r.get('defaultName') == 'taskspaces-2-2' for r in self.cfg['workspacerules']))
        self.assertTrue(any(r.get('enabled') and r.get('defaultName') == 'taskspaces-1-2' for r in self.cfg['workspacerules']))
        rule_count = len(self.cfg['workspacerules'])
        self.run_task('go')
        self.assertEqual(len(self.cfg['workspacerules']), rule_count)
        self.assertEqual(self.active(), {'eDP-1': 5, 'HDMI-A-1': 4})

    def test_finish_disables_every_owned_member_rule_and_drops_handles(self):
        self.start()
        self.finish_here(4, 'Close 1 window and finish')
        self.assertEqual(self.cfg['owned_rules'], {})
        self.assertFalse(any(r.get('enabled') is not False for r in self.cfg['workspacerules']))
        self.assertFalse((self.state / '3.json').exists())

    def test_pair_allocation_reuses_empty_inactive_slots_after_orphan_release(self):
        self.screens()
        self.cfg['workspaces'].extend([real_workspace(3, '3', 0), real_workspace(4, '4'), real_workspace(5, 'taskspaces-99-2', 0)])
        self.cfg['clients'].append(real_window('0x444', 'kitty', 'Occupied', 4, '4'))
        self.cfg['workspacerules'] = [dict(workspaceString='5', enabled=True, persistent=True, defaultName='taskspaces-99-2')]
        self.cfg['owned_rules'] = {'5': 'taskspaces-99-2'}
        self.run_task('send')
        self.assertEqual([m['id'] for m in self.saved()['members']], [3, 5])
        self.assertEqual(next(w['workspace']['id'] for w in self.cfg['clients'] if w['address'] == '0x444'), 4)

    def test_numeric_name_is_accepted_while_owned_workspace_is_created(self):
        self.screens()
        self.cfg['numeric_first'] = True
        self.run_task('send')
        self.assertEqual(self.active(), {'eDP-1': 3, 'HDMI-A-1': 4})
        self.assertEqual([m['name'] for m in self.saved()['members']], ['Planning', 'Planning ·'])

    def test_unbound_rule_snap_back_is_repaired_by_bound_refresh(self):
        self.pair(empty_other=True)
        self.cfg['workspacerules'] = [dict(workspaceString='4', enabled=True, persistent=True, defaultName='taskspaces-3-2')]
        self.cfg['owned_rules'] = {'4': 'taskspaces-3-2'}
        self.write_cfg()
        subprocess.run([str(self.root / 'bin/hyprctl'), 'workspaces', '-j'], env=self.env,
                       text=True, capture_output=True, check=True)
        self.cfg = json.loads((self.root / 'config.json').read_text())
        self.assertEqual(self.owners()[4], 'eDP-1')
        self.run_task('go')
        self.assertEqual(self.owners()[4], 'HDMI-A-1')
        rule = next(r for r in self.cfg['workspacerules'] if r['workspaceString'] == '4' and r.get('enabled'))
        self.assertEqual(rule['monitor'], 'HDMI-A-1')
        self.assertEqual(self.active(), {'eDP-1': 3, 'HDMI-A-1': 4})

    def test_finish_keep_fallback_stays_on_the_member_output(self):
        record = self.pair()
        record['members'][1]['source'] = 88
        record['members'][1]['source_name'] = '88'
        (self.state / '3.json').write_text(json.dumps(record))
        self.cfg['workspaces'][0]['monitor'] = 'eDP-1'
        self.cfg['monitors'][1]['activeWorkspace'] = {'id': 4, 'name': 'taskspaces-3-2'}
        self.finish_here(4, 'Keep 2 windows and finish')
        external = next(w for w in self.cfg['clients'] if w['address'] == '0xdef')
        self.assertNotEqual(external['workspace']['id'], 1)
        self.assertEqual(self.owners()[external['workspace']['id']], 'HDMI-A-1')
        self.assertEqual(self.active()['HDMI-A-1'], external['workspace']['id'])

    def test_split_skips_changed_window_and_restores_other_windows(self):
        self.pair()
        extra = real_window('0xaaa', 'kitty', 'Another reference', 4, 'taskspaces-3-2')
        extra['monitor'] = 1
        self.cfg['clients'].append(extra)
        self.unplug()
        self.run_task('go')
        self.cfg['clients'][1]['stableId'] = 'different-window'
        self.reconnect()
        self.run_task('go')
        positions = {w['address']: w['workspace']['id'] for w in self.cfg['clients']}
        self.assertEqual(positions['0xdef'], 3)
        self.assertEqual(positions['0xaaa'], 4)
        self.assertEqual(self.saved()['merged_windows'], [])


class AllocationBaseTests(unittest.TestCase):
    """New numbering defaults, with fake compositor data only."""
    setUp = TaskTests.setUp
    set_settings = TaskTests.set_settings
    write_cfg = TaskTests.write_cfg
    run_task = TaskTests.run_task
    events = TaskTests.events
    dispatches = TaskTests.dispatches
    menu = TaskTests.menu
    screens = MultiMonitorTests.screens
    two_screen_setting = MultiMonitorTests.two_screen_setting
    active = MultiMonitorTests.active
    pair = MultiMonitorTests.pair
    labels = MultiMonitorTests.labels
    finish_here = MultiMonitorTests.finish_here

    def paired(self, first=6):
        self.screens()
        self.set_settings(first=first, two_screen=True)

    def new_pair(self, primary):
        self.run_task('send')
        return json.loads((self.state / f'{primary}.json').read_text())

    def assert_pair_ids(self, record, expected):
        self.assertEqual([m['id'] for m in record['members']], expected)

    def first_workspace(self):
        reader = runpy.run_path(str(SCRIPT.with_name('taskspaces-members')))['first_task_workspace']
        with patch.dict(os.environ, self.env):
            return reader()

    def test_setting_reader_accepts_integer_bounds_in_each_bar_section(self):
        for section in ('left', 'center', 'right'):
            for value in (1, 6, 17, 50):
                with self.subTest(section=section, value=value):
                    self.set_settings(first=value, section=section)
                    self.assertEqual(self.first_workspace(), value)

    def test_invalid_setting_values_default_to_six(self):
        for value in (None, True, False, 0, -1, '6', 6.0, 6.5, [], {}, 51, 1001, 10**18):
            with self.subTest(value=value):
                self.set_settings(first=value)
                self.assertEqual(self.first_workspace(), 6)

    def test_missing_or_malformed_config_defaults_to_six(self):
        path = self.root / 'config/omarchy/shell.json'
        path.unlink()
        self.assertEqual(self.first_workspace(), 6)
        for data in ('{', 'null', '[]', '{}', '{"version":2,"bar":{"layout":{}}}',
                     '{"version":1,"bar":null}', '{"version":1,"bar":{"layout":{"left":null}}}',
                     '{"version":1,"bar":{"layout":{"center":[{"id":"tithi-stack.taskspaces"}]}}}',
                     '{"version":1,"bar":{"layout":{"center":[{"id":"other.widget","firstTaskWorkspace":1}]}}}'):
            with self.subTest(data=data):
                path.write_text(data)
                self.assertEqual(self.first_workspace(), 6)

    def test_setting_reader_uses_home_when_xdg_config_is_empty(self):
        self.set_settings(first=12)
        source = self.root / 'config/omarchy/shell.json'
        target = self.root / '.config/omarchy/shell.json'
        target.parent.mkdir(parents=True)
        target.write_text(source.read_text())
        self.env['XDG_CONFIG_HOME'] = ''
        self.assertEqual(self.first_workspace(), 12)

    def test_shell_reads_setting_through_member_tool(self):
        self.set_settings(first=9)
        result = self.run_task(code='source "$1"; dry=true; state_dir="$XDG_RUNTIME_DIR/taskspaces"; member_tool first-workspace')
        self.assertEqual(result.stdout, '9\n')
        self.assertEqual(self.events(), [])

    def test_setting_schema_matches_reader_bounds_and_default(self):
        widget = json.loads((SCRIPT.parent.parent / 'manifest.json').read_text())['barWidget']
        field = next(f for f in widget['schema'] if f['key'] == 'firstTaskWorkspace')
        self.assertEqual((field['type'], field['min'], field['max'], field['step'], field['defaultValue']),
                         ('integer', 1, 50, 1, 6))
        self.assertEqual(widget['defaults']['firstTaskWorkspace'], 6)

    def test_no_shell_config_allocates_single_screen_task_at_six(self):
        (self.root / 'config/omarchy/shell.json').unlink()
        self.cfg['select_first'] = True
        self.run_task('send')
        self.assertEqual(json.loads((self.state / '6.json').read_text())['id'], 6)
        self.assertEqual(self.cfg['clients'][0]['workspace']['id'], 6)

    def test_single_screen_allocation_respects_custom_base_and_existing_workspace(self):
        self.set_settings(first=12)
        self.cfg['select_first'] = True
        self.cfg['workspaces'].append(real_workspace(12, '12', 0))
        self.run_task('send')
        self.assertTrue((self.state / '13.json').exists())
        self.assertEqual(next(w for w in self.cfg['workspaces'] if w['id'] == 12)['name'], '12')

    def test_free_numbers_below_base_are_never_allocated(self):
        self.set_settings(first=6)
        scratch = real_workspace(-98, 'special:scratchpad')
        self.cfg['workspaces'] = [scratch]
        self.cfg['activeworkspace'] = copy.deepcopy(scratch)
        win = real_window('0xabc', 'kitty', 'Scratch', -98, 'special:scratchpad')
        self.cfg['clients'] = [win]
        self.cfg['activewindow'] = copy.deepcopy(win)
        self.cfg['select_first'] = True
        self.run_task('send')
        self.assertTrue((self.state / '6.json').exists())
        self.assertEqual({w['id'] for w in self.cfg['workspaces']}, {-98, 6})

    def test_finish_fallback_still_uses_low_desktop_slots(self):
        self.set_settings(first=6)
        self.cfg['workspaces'] = [real_workspace(1, 'Other task', 0), real_workspace(2, 'Planning')]
        self.cfg['activeworkspace'] = copy.deepcopy(self.cfg['workspaces'][1])
        self.cfg['selection'] = 'Keep 1 window and finish'
        (self.state / '1.json').write_text(json.dumps(dict(id=1, name='Other task', source=4)))
        (self.state / '2.json').write_text(json.dumps(dict(id=2, name='Planning', source=9)))
        self.run_task('finish')
        self.assertEqual(self.cfg['clients'][0]['workspace']['id'], 3)
        self.assertFalse((self.state / '2.json').exists())
        self.assertTrue((self.state / '1.json').exists())

    def test_adopt_workspace_three_and_keep_preserve_its_number(self):
        self.set_settings(first=6)
        ws = real_workspace(3, '3')
        self.cfg['workspaces'].append(ws)
        self.cfg['activeworkspace'] = copy.deepcopy(ws)
        self.cfg['activewindow']['workspace'] = {'id': 3, 'name': '3'}
        self.cfg['clients'] = [copy.deepcopy(self.cfg['activewindow'])]
        self.run_task('send')
        record = json.loads((self.state / '3.json').read_text())
        self.assertNotIn('members', record)
        self.assertEqual(self.cfg['clients'][0]['workspace']['id'], 3)
        self.cfg['activeworkspace'] = {'id': 3, 'name': 'Planning'}
        self.cfg['selection'] = 'Keep 1 window and finish'
        self.run_task('finish')
        self.assertFalse((self.state / '3.json').exists())
        self.assertEqual(next(w['name'] for w in self.cfg['workspaces'] if w['id'] == 3), '3')
        self.assertEqual(self.cfg['clients'][0]['workspace']['id'], 3)

    def test_layout_only_rules_below_default_give_six_and_seven_then_eight_and_nine(self):
        self.paired()
        path = self.root / 'config/omarchy/shell.json'
        config = json.loads(path.read_text())
        del config['bar']['layout']['center'][0]['firstTaskWorkspace']
        path.write_text(json.dumps(config))
        rules = [dict(workspaceString=str(i), enabled=True) for i in (1, 2, 4)]
        self.cfg['workspacerules'] = copy.deepcopy(rules)
        self.assert_pair_ids(self.new_pair(6), [6, 7])
        self.assertEqual(self.active(), {'eDP-1': 6, 'HDMI-A-1': 7})
        incoming = real_window('0x111', 'kitty', 'Next task', 2, '2')
        self.cfg['clients'].append(incoming)
        self.cfg['activewindow'] = copy.deepcopy(incoming)
        self.assert_pair_ids(self.new_pair(8), [8, 9])
        self.assertEqual(self.cfg['workspacerules'][:3], rules)

    def test_base_one_restores_three_and_five_with_same_layout_only_rules(self):
        self.paired(first=1)
        self.cfg['workspacerules'] = [dict(workspaceString=str(i), enabled=True) for i in (1, 2, 4)]
        self.assert_pair_ids(self.new_pair(3), [3, 5])

    def test_client_on_six_moves_pair_to_eight_and_nine(self):
        self.paired()
        self.cfg['workspaces'].append(real_workspace(6, '6'))
        self.cfg['clients'].append(real_window('0x666', 'kitty', 'Own window', 6, '6'))
        self.assert_pair_ids(self.new_pair(8), [8, 9])
        self.assertEqual(next(w for w in self.cfg['clients'] if w['address'] == '0x666')['workspace']['id'], 6)

    def test_rule_on_six_moves_pair_to_eight_and_nine(self):
        self.paired()
        rule = dict(workspaceString='6', enabled=True)
        self.cfg['workspacerules'] = [copy.deepcopy(rule)]
        self.assert_pair_ids(self.new_pair(8), [8, 9])
        self.assertEqual(self.cfg['workspacerules'][0], rule)

    def test_gap_on_seven_moves_pair_to_next_block(self):
        self.paired()
        self.cfg['workspacerules'] = [dict(workspaceString='7', enabled=True)]
        self.assert_pair_ids(self.new_pair(8), [8, 9])

    def test_disabled_and_special_rules_do_not_block_allocation(self):
        self.paired()
        self.cfg['workspacerules'] = [dict(workspaceString=str(i), enabled=False) for i in (6, 7)]
        self.cfg['workspacerules'].append(dict(workspaceString='special:scratchpad', enabled=True))
        self.cfg['workspaces'].append(real_workspace(-98, 'special:scratchpad'))
        self.cfg['clients'].append(real_window('0x999', 'kitty', 'Scratch', -98, 'special:scratchpad'))
        self.assert_pair_ids(self.new_pair(6), [6, 7])

    def test_active_workspaces_are_reserved_above_base(self):
        self.paired()
        for mon, wid in zip(self.cfg['monitors'], (7, 8)):
            ws = dict(real_workspace(wid, str(wid), 0), monitor=mon['name'])
            self.cfg['workspaces'].append(ws)
            mon['activeWorkspace'] = dict(ws)
        self.assert_pair_ids(self.new_pair(10), [10, 11])

    def test_named_and_persistent_workspaces_reserve_their_blocks(self):
        self.paired()
        self.cfg['workspaces'].extend([real_workspace(6, 'Personal project', 0),
                                       dict(real_workspace(8, '8', 0), ispersistent=True)])
        self.assert_pair_ids(self.new_pair(10), [10, 11])
        self.assertEqual(next(w['name'] for w in self.cfg['workspaces'] if w['id'] == 6), 'Personal project')

    def test_absent_task_member_still_reserves_its_block(self):
        self.pair(empty_other=True)
        record = json.loads((self.state / '3.json').read_text())
        record['members'][1]['id'] = 7
        record['members'][1]['name'] = 'Planning ·'
        (self.state / '3.json').write_text(json.dumps(record))
        self.cfg['workspaces'] = [w for w in self.cfg['workspaces'] if w['id'] != 4]
        incoming = real_window('0x111', 'kitty', 'Next', 2, '2')
        self.cfg['clients'].append(incoming)
        self.cfg['activewindow'] = copy.deepcopy(incoming)
        self.set_settings(first=6, two_screen=True)
        self.assert_pair_ids(self.new_pair(8), [8, 9])

    def test_adopt_workspace_three_claims_companion_from_base(self):
        self.paired()
        ws = real_workspace(3, '3')
        self.cfg['workspaces'].append(ws)
        self.cfg['activeworkspace'] = copy.deepcopy(ws)
        self.cfg['monitors'][0]['activeWorkspace'] = copy.deepcopy(ws)
        self.cfg['activewindow']['workspace'] = {'id': 3, 'name': '3'}
        self.cfg['clients'] = [copy.deepcopy(self.cfg['activewindow'])]
        self.cfg['select_first'] = False
        self.cfg['selection'] = 'Turn this workspace into a task…\tname this workspace · windows stay here'
        self.assert_pair_ids(self.new_pair(3), [3, 6])
        self.assertEqual(self.cfg['clients'][0]['workspace']['id'], 3)

    def test_adopt_empty_low_workspace_claims_companion_from_base(self):
        self.paired()
        self.cfg['clients'] = []
        self.cfg['activewindow'] = {}
        self.cfg['workspaces'][1]['windows'] = 0
        self.assert_pair_ids(self.new_pair(2), [2, 6])

    def test_existing_low_pair_keeps_ids_after_base_changes(self):
        self.pair()
        self.set_settings(first=50, two_screen=True)
        self.run_task('go')
        record = json.loads((self.state / '3.json').read_text())
        self.assert_pair_ids(record, [3, 4])
        self.assertEqual(set(self.active().values()), {3, 4})
        incoming = real_window('0x111', 'kitty', 'Next', 2, '2')
        self.cfg['clients'].append(incoming)
        self.cfg['activewindow'] = copy.deepcopy(incoming)
        self.assert_pair_ids(self.new_pair(50), [50, 51])
        self.assert_pair_ids(json.loads((self.state / '3.json').read_text()), [3, 4])

    def test_allocation_above_ten_and_labels_have_no_workspace_cap(self):
        self.paired(first=11)
        self.assert_pair_ids(self.new_pair(11), [11, 12])
        labels = json.loads(self.labels().stdout)
        self.assertEqual({i: entry['name'] for i, entry in labels.items()}, {'11': 'Planning', '12': 'Planning'})

    def test_primary_stays_on_the_starting_screen(self):
        self.paired(first=7)
        for mon in self.cfg['monitors']:
            mon['focused'] = mon['name'] == 'HDMI-A-1'
        self.cfg['clients'][0]['monitor'] = 1
        self.cfg['activewindow'] = copy.deepcopy(self.cfg['clients'][0])
        record = self.new_pair(7)
        self.assert_pair_ids(record, [7, 8])
        self.assertEqual([m['output'] for m in record['members']], ['HDMI-A-1', 'eDP-1'])

    def test_three_screens_use_single_workspace_at_base(self):
        self.paired()
        self.cfg['monitors'].append(dict(id=2, name='DP-2', focused=False, activeWorkspace={'id': 5, 'name': '5'}))
        self.run_task('send')
        record = json.loads((self.state / '6.json').read_text())
        self.assertNotIn('members', record)
        self.assertFalse(any(a[0] == 'eval' for a in self.events('hyprctl')))

    def test_finished_block_can_be_reused_after_workspaces_disappear(self):
        self.paired()
        self.new_pair(6)
        self.finish_here(6, 'Keep 1 window and finish')
        self.assertFalse((self.state / '6.json').exists())
        # A post-finish snapshot where Hyprland has dropped the empty slots.
        self.cfg['workspaces'] = [w for w in self.cfg['workspaces'] if w['id'] < 6]
        for mon, wid in zip(self.cfg['monitors'], (2, 1)):
            mon['activeWorkspace'] = {'id': wid, 'name': str(wid)}
        self.cfg['activewindow'] = copy.deepcopy(self.cfg['clients'][0])
        self.cfg['select_first'] = True
        self.assert_pair_ids(self.new_pair(6), [6, 7])

    def test_reserved_numbers_listing_explains_each_reason_and_free_low_numbers(self):
        self.paired()
        self.cfg['workspacerules'] = [dict(workspaceString=str(i), enabled=True) for i in (4, 6)]
        self.cfg['workspacerules'].append(dict(workspaceString='13', enabled=False))
        self.cfg['clients'].append(real_window('0x777', 'kitty', 'Own window', 7, '7'))
        self.cfg['workspaces'].extend([real_workspace(7, '7'), real_workspace(9, 'Kept task', 0),
                                       dict(real_workspace(10, '10', 0), ispersistent=True),
                                       real_workspace(11, 'Personal project', 0)])
        record = dict(id=9, name='Kept task', source=2,
                      members=[dict(id=9, name='Kept task', output='eDP-1', source=2, source_name='2'),
                               dict(id=12, name='Kept task ·', output='HDMI-A-1', source=1, source_name='1')])
        (self.state / '9.json').write_text(json.dumps(record))
        result = self.run_task('setup', '--check')
        lines = result.stdout.splitlines()
        self.assertIn('  First task workspace: 6', lines)
        self.assertIn('  Two-screen tasks: enabled (2 connected screens)', lines)
        self.assertIn('  1: reserved (active on HDMI-A-1)', lines)
        self.assertIn('  2: reserved (active on eDP-1; window present: kitty)', lines)
        self.assertIn('  3: kept for you (below first task workspace: 6)', lines)
        self.assertIn('  4: reserved (existing Hyprland rule)', lines)
        self.assertIn('  6: reserved (existing Hyprland rule)', lines)
        self.assertIn('  7: reserved (window present: kitty)', lines)
        self.assertIn('  8: available', lines)
        self.assertIn('  9: reserved (task member: "Kept task"; renamed workspace: "Kept task")', lines)
        self.assertIn('  10: reserved (persistent workspace)', lines)
        self.assertIn('  11: reserved (renamed workspace: "Personal project")', lines)
        self.assertIn('  12: reserved (task member: "Kept task")', lines)
        self.assertIn('  13: available', lines)
        self.assertNotIn('layout rule', result.stdout)
        self.assertNotIn('Shortcuts:', result.stdout)

    def test_check_does_not_prune_reconcile_or_write_runtime_or_bindings(self):
        self.paired()
        self.cfg['workspaces'].append(real_workspace(17, 'taskspaces-99-2', 0))
        self.cfg['workspacerules'] = [dict(workspaceString='17', enabled=True,
                                          persistent=True, defaultName='taskspaces-99-2')]
        (self.state / '99.json').write_text(json.dumps(dict(id=99, name='Gone', source=1)))
        (self.state / '24.cleanup').write_text('{"id":24}')
        (self.state / 'broken.json').write_text('{')
        before = {p.name: p.read_bytes() for p in self.state.iterdir()}
        shell = self.root / 'config/omarchy/shell.json'
        config_before = shell.read_bytes()
        # Interactive setup cannot read a bindings file from this directory.
        bindings = self.root / 'bindings-not-a-file'
        bindings.mkdir()
        self.env['TASKSPACES_BINDINGS_FILE'] = str(bindings)
        self.run_task('setup', '--check')
        self.assertEqual({p.name: p.read_bytes() for p in self.state.iterdir()}, before)
        self.assertEqual(shell.read_bytes(), config_before)
        self.assertFalse((self.runtime / 'taskspaces.lock').exists())
        self.assertEqual(self.events('omarchy-menu-select'), [])
        self.assertEqual(self.events('omarchy-menu-input'), [])
        self.assertEqual(self.events('omarchy-notification-send'), [])
        self.assertTrue(all(a[0] in ('clients', 'monitors', 'workspaces', 'workspacerules')
                            for a in self.events('hyprctl')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
