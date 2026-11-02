import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Shows the task name of the active workspace, or the active window title.
// The bar host forwards left clicks to triggerPress.
// The widget itself never focuses, moves or closes a window. A left click opens
// the user's Go-to-task list; focusing happens only when the user picks a row.
BarWidget {
  id: root
  moduleName: "tithi-stack.taskspaces"

  readonly property string taskspacesCommand: decodeURIComponent(String(Qt.resolvedUrl("bin/taskspaces")).replace(/^file:\/\//, ""))

  // The bar host owns slot clicks; the inner MouseArea handles hover only.
  function triggerPress(button) {
    if (button !== Qt.LeftButton) return
    if (root.bar) root.bar.hideTooltip(root)
    Util.execArgv([root.taskspacesCommand, "go"])
  }

  readonly property var monitor: {
    var window = root.QsWindow.window
    return window && window.screen ? Hyprland.monitorFor(window.screen) : null
  }
  readonly property var ws: monitor ? monitor.activeWorkspace : null
  readonly property string taskName: ws && ws.name !== String(ws.id) ? ws.name : ""
  readonly property var toplevel: ToplevelManager.activeToplevel
  readonly property string title: toplevel ? (toplevel.title || toplevel.appId || "") : ""
  readonly property bool taskActive: taskName !== ""
  readonly property string glyph: String(setting("taskGlyph", "󰌨"))
  readonly property bool showWindowTitle: setting("showWindowTitle", true) === true
  readonly property string label: taskActive ? (glyph ? glyph + " " : "") + taskName : (showWindowTitle ? title : "")
  readonly property int taskMaxWidth: Number(setting("taskMaxWidth", 220)) || 220
  readonly property int titleMaxWidth: Number(setting("maxWidth", 450)) || 450
  readonly property int maxLabelWidth: taskActive ? taskMaxWidth : titleMaxWidth

  visible: label !== "" && !vertical
  implicitWidth: visible ? Math.min(maxLabelWidth, labelMetrics.width) + Style.spacing.controlPaddingX * 2 : 0
  implicitHeight: barSize

  TextMetrics {
    id: labelMetrics
    text: root.label
    font.family: root.bar ? root.bar.fontFamily : Style.font.family
    font.pixelSize: Style.font.body
  }

  Behavior on implicitWidth {
    NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
  }

  // Re-read the workspace list on rename so a renamed task shows its new name.
  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (event.name === "renameworkspace") Hyprland.refreshWorkspaces()
    }
  }

  Item {
    anchors.fill: parent
    anchors.leftMargin: Style.space(8)
    anchors.rightMargin: Style.space(8)
    clip: true

    Text {
      id: labelText
      textFormat: Text.PlainText
      anchors.verticalCenter: parent.verticalCenter
      anchors.left: parent.left
      width: parent.width
      text: root.label
      color: root.taskActive ? Commons.Color.accent : (root.bar ? root.bar.barForeground : Commons.Color.foreground)
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.body
      elide: Text.ElideRight
      opacity: root.taskActive ? 1 : 0.85
    }
  }

  // Keep hover feedback while the bar host dispatches clicks to triggerPress.
  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.NoButton
    cursorShape: Qt.PointingHandCursor
    onEntered: if (root.bar) root.bar.showTooltip(root, (root.taskActive ? root.taskName + " · workspace " + root.ws.id : root.title) + " · click for tasks")
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
