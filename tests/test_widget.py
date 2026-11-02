"""Check manifest defaults and evaluate the widget's label bindings offscreen."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WidgetTests(unittest.TestCase):
    def test_click_contract_matches_manifest_and_docs(self):
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        self.assertEqual(manifest['entryPoints']['barWidget'], 'TaskLabel.qml')
        self.assertIn('left-click for Go to task', manifest['barWidget']['description'])
        source = (ROOT / 'TaskLabel.qml').read_text()
        self.assertRegex(source, r"(?m)^  function triggerPress\(button\) \{")
        self.assertIn('Util.execArgv([root.taskspacesCommand, "go"])', source)
        self.assertIn('acceptedButtons: Qt.NoButton', source)
        self.assertNotIn('onClicked:', source)
        self.assertNotIn('Hover only', source)
        self.assertNotIn('TSDIAG', source)
        self.assertIn('omarchy-restart-shell', (ROOT / 'docs/how-it-works.md').read_text())
        for name in ('TaskLabel.qml', 'README.md', 'SECURITY.md',
                     'docs/how-it-works.md', 'CHANGELOG.md'):
            with self.subTest(file=name):
                text = (ROOT / name).read_text()
                self.assertIn('never focuses, moves or closes a window', text)
                self.assertIn('Go-to-task list', text)
                self.assertRegex(text, r'focusing happens only when (?:the user picks|you pick) a row')
                self.assertNotRegex(text, r'Read-only:|never handles a click|only reads the workspace name|reads only the workspace name')

    def test_bar_slot_dispatch_offscreen(self):
        runner = shutil.which('qmltestrunner')
        if not runner and Path('/usr/lib/qt6/bin/qmltestrunner').exists():
            runner = '/usr/lib/qt6/bin/qmltestrunner'
        if not runner:
            self.skipTest('Qt QML test runner is not installed')
        source = (ROOT / 'TaskLabel.qml').read_text()
        command = re.search(r'^  readonly property string taskspacesCommand:.*$', source, re.M)[0]
        mouse = re.search(r'  MouseArea \{.*?\n  \}', source, re.S)[0]
        trigger = re.search(r'  function triggerPress\(button\) \{.*?\n  \}', source, re.S)[0]
        trigger = trigger.replace('Util.execArgv', 'recorder.execArgv')
        bindings = '\n'.join(re.findall(
            r'^  (?:readonly )?property (?:bool|string) (?:taskActive|glyph|showWindowTitle|label|interactive|pressable|concealed):.*$',
            source, re.M))
        visibility = re.search(r'^  visible:.*$', source, re.M)[0]
        opacity = re.search(r'^  opacity:.*$', source, re.M)
        # Keep the widget's actual root eligibility properties and trigger hook.
        # The overlay below mimics Bar.qml's slot dispatch, rather than sending
        # presses straight to the inner MouseArea. No real process is launched.
        mouse = mouse.replace('MouseArea {', 'MouseArea {\n    objectName: "mouse"', 1)
        with tempfile.TemporaryDirectory(prefix='taskspaces-widget-') as folder:
            plugin = Path(folder) / "plugin space ' # % ü"
            plugin.mkdir()
            (plugin / 'TestLabel.qml').write_text('''import QtQuick
Item {
  id: root
  width: 300; height: 40
  property bool vertical: false
  property var settings: ({})
  function setting(name, fallback) {
    var value = settings[name]
    return value === undefined || value === null ? fallback : value
  }
  property string taskName: "Project plan"
  property string title: "Project notes"
  property var ws: ({id: 7})
  property var bar: host
  QtObject {
    id: host
    property string tooltip: ""
    function showTooltip(item, text) { tooltip = text }
    function hideTooltip(item) { tooltip = "" }
  }
  QtObject {
    id: recorder
    property var calls: []
    function execArgv(argv) { calls = calls.concat([argv]) }
  }
  property alias calls: recorder.calls
  property alias tooltip: host.tooltip
''' + command + '\n' + bindings + '\n' + visibility + '\n'
                + (opacity[0] if opacity else '') + '\n' + trigger + '\n' + mouse + '\n}\n')
            test = plugin / 'tst_click.qml'
            test.write_text('''import QtQuick
import QtTest
TestCase {
  name: "TaskLabelClick"
  visible: true
  when: windowShown
  width: 400; height: 100
  TestLabel { id: label }
  // Eligibility and activeItem fallback from Omarchy Bar.qml. An overlay owns
  // presses, as modulePointer does; the widget MouseArea cannot receive them.
  function moduleTargetClickable(target) {
    return target
      && target.visible !== false
      && target.opacity !== 0
      && target.interactive !== false
      && target.pressable !== false
      && target.concealed !== true
      && typeof target.triggerPress === "function"
  }
  MouseArea {
    id: modulePointer
    z: 10
    width: label.width; height: label.height
    acceptedButtons: Qt.LeftButton
    onClicked: function(mouse) {
      if (moduleTargetClickable(label)) label.triggerPress(mouse.button)
      else mouse.accepted = false
    }
  }
  function test_clicks() {
    var area = findChild(label, "mouse")
    compare(area.acceptedButtons, Qt.NoButton)
    verify(moduleTargetClickable(label))
    compare(typeof label.triggerPress, "function")
    label.triggerPress(Qt.RightButton)
    label.triggerPress(Qt.MiddleButton)
    compare(label.calls.length, 0)
    label.triggerPress(Qt.LeftButton)
    compare(label.calls.length, 1)
    compare(label.calls[0], [label.taskspacesCommand, "go"])
    label.calls = []
    compare(area.cursorShape, Qt.PointingHandCursor)
    compare(label.taskspacesCommand, ''' + json.dumps(str(plugin / 'bin/taskspaces')) + ''')
    mouseMove(label, 10, 10)
    tryCompare(label, "tooltip", "Project plan · workspace 7 · click for tasks")
    mouseClick(label, 10, 10, Qt.RightButton)
    mouseClick(label, 10, 10, Qt.MiddleButton)
    compare(label.calls.length, 0)
    mouseClick(label, 10, 10, Qt.LeftButton)
    compare(label.calls.length, 1)
    compare(label.calls[0], [label.taskspacesCommand, "go"])
    compare(label.tooltip, "")
    mouseMove(label, 350, 60)
    tryCompare(label, "tooltip", "")
    label.taskName = ""
    mouseMove(label, 10, 10)
    tryCompare(label, "tooltip", "Project notes · click for tasks")
    mouseClick(label, 10, 10, Qt.LeftButton)
    compare(label.calls.length, 2)
    compare(label.calls[1], [label.taskspacesCommand, "go"])
    label.opacity = 0
    verify(!moduleTargetClickable(label))
    mouseClick(modulePointer, 10, 10, Qt.LeftButton)
    compare(label.calls.length, 2)
    label.opacity = 1
    label.settings = {showWindowTitle: false}
    verify(!moduleTargetClickable(label))
    mouseClick(modulePointer, 10, 10, Qt.LeftButton)
    compare(label.calls.length, 2)
    label.settings = {showWindowTitle: true}
    verify(moduleTargetClickable(label))
    label.bar = null
    mouseMove(label, 350, 60)
    mouseMove(label, 10, 10)
    mouseClick(label, 10, 10, Qt.LeftButton)
    compare(label.calls.length, 3)
  }
}
''')
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=folder)
            result = subprocess.run([runner, '-input', str(test)], env=env,
                                    text=True, errors="replace", capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_window_title_setting_defaults_on(self):
        widget = json.loads((ROOT / 'manifest.json').read_text())['barWidget']
        setting = next((item for item in widget['schema'] if item['key'] == 'showWindowTitle'), None)
        self.assertIsNotNone(setting)
        self.assertEqual(setting['type'], 'boolean')
        self.assertEqual(setting['label'], 'Show the window title outside a task')
        self.assertIs(setting['defaultValue'], True)
        self.assertIs(widget['defaults']['showWindowTitle'], True)

    def test_label_binding_reacts_to_setting_and_task(self):
        runner = shutil.which('qmltestrunner')
        if not runner and Path('/usr/lib/qt6/bin/qmltestrunner').exists():
            runner = '/usr/lib/qt6/bin/qmltestrunner'
        if not runner:
            self.skipTest('Qt QML test runner is not installed')
        source = (ROOT / 'TaskLabel.qml').read_text()
        # Evaluate the actual label bindings with synthetic inputs. The host's
        # setting() contract supplies a fallback for missing/null settings.
        bindings = '\n'.join(re.findall(
            r'^  readonly property (?:bool|string) (?:taskActive|glyph|showWindowTitle|label):.*$',
            source, re.M))
        with tempfile.TemporaryDirectory(prefix='taskspaces-widget-') as folder:
            test = Path(folder) / 'tst_label.qml'
            test.write_text('''import QtQuick
import QtTest
TestCase {
  name: "TaskLabel"
  QtObject {
    id: label
    property var settings: ({})
    property string taskName: ""
    property string title: "Project notes"
    function setting(name, fallback) {
      var value = settings[name]
      return value === undefined || value === null ? fallback : value
    }
''' + bindings + '''
  }
  function test_setting() {
    compare(label.label, "Project notes")
    label.settings = {showWindowTitle: false}
    compare(label.label, "")
    label.taskName = "Project plan"
    compare(label.label, "󰌨 Project plan")
    label.settings = {showWindowTitle: false, taskGlyph: ""}
    compare(label.label, "Project plan")
    label.taskName = ""
    compare(label.label, "")
    label.settings = {showWindowTitle: true}
    compare(label.label, "Project notes")
    label.settings = {showWindowTitle: null}
    compare(label.label, "Project notes")
  }
}
''')
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=folder)
            result = subprocess.run([runner, '-input', str(test)], env=env,
                                    text=True, errors="replace", capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_each_screen_resolves_shared_name_from_its_actual_workspace(self):
        runner = shutil.which('qmltestrunner') or '/usr/lib/qt6/bin/qmltestrunner'
        if not Path(runner).exists():
            self.skipTest('Qt QML test runner is not installed')
        source = (ROOT / 'TaskLabel.qml').read_text()
        resolver = re.search(r'  function taskForWorkspace\(workspace, labels\) \{.*?\n  \}', source, re.S)[0]
        with tempfile.TemporaryDirectory(prefix='taskspaces-widget-') as folder:
            test = Path(folder) / 'tst_members.qml'
            test.write_text('''import QtQuick
import QtTest
TestCase {
  name: "TaskMembers"
''' + resolver + '''
  function test_screen_truth() {
    var labels = {
      "3": {name: "Project plan", workspace_name: "taskspaces-3-1"},
      "4": {name: "Project plan", workspace_name: "taskspaces-3-2"},
      "5": {name: "Other task", workspace_name: "Other task"}
    }
    compare(taskForWorkspace({id: 3, name: "taskspaces-3-1"}, labels), "Project plan")
    compare(taskForWorkspace({id: 4, name: "taskspaces-3-2"}, labels), "Project plan")
    // A number-key switch changes only that screen's label.
    compare(taskForWorkspace({id: 5, name: "Other task"}, labels), "Other task")
    compare(taskForWorkspace({id: 1, name: "1"}, labels), "")
    compare(taskForWorkspace({id: 4, name: "Unrelated"}, labels), "")
    compare(taskForWorkspace({id: 4, name: "taskspaces-3-2"}, {}), "")
    compare(taskForWorkspace(null, labels), "")
    labels["3"].name = "Renamed plan"
    compare(taskForWorkspace({id: 3, name: "taskspaces-3-1"}, labels), "Renamed plan")
  }
}
''')
            result = subprocess.run([runner, '-input', str(test)],
                                    env=dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=folder),
                                    text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_label_query_is_read_only_and_screen_local(self):
        source = (ROOT / 'TaskLabel.qml').read_text()
        self.assertIn('Hyprland.monitorFor(window.screen)', source)
        self.assertIn('monitor.activeWorkspace', source)
        self.assertIn('"true",', source)
        self.assertIn('"labels"]', source)
        self.assertIn('interval: 1000', source)
