import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Shows the task name of the active workspace, or the active window title.
// Read-only: this widget never focuses, moves or closes a window.
BarWidget {
  id: root
  moduleName: "tithi-stack.taskhop"

  readonly property var monitor: {
    var window = root.QsWindow.window
    return window && window.screen ? Hyprland.monitorFor(window.screen) : null
  }
  readonly property var ws: monitor ? monitor.activeWorkspace : null
  readonly property string taskName: ws && ws.name !== String(ws.id) ? ws.name : ""
  readonly property var toplevel: ToplevelManager.activeToplevel
  readonly property string title: toplevel ? (toplevel.title || toplevel.appId || "") : ""
  readonly property bool taskActive: taskName !== ""
  readonly property string glyph: String(setting("taskGlyph", "◆"))
  readonly property string label: taskActive ? (glyph ? glyph + " " : "") + taskName : title
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

  // Hover only: no mouse buttons are accepted, so the widget never handles a click.
  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.NoButton
    cursorShape: Qt.ArrowCursor
    onEntered: if (root.bar) root.bar.showTooltip(root, root.taskActive ? root.taskName + " · workspace " + root.ws.id : root.title)
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
