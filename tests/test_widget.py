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
                                    text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
