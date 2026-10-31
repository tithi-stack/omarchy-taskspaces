# How Taskspaces works

This page describes Taskspaces 0.1.0. The automated tests use mock commands. Omarchy Quattro has not been tested yet.

## Goals

- **No fixed assignments:** a task is not tied to an app. Its windows go where the task is.
- **Low mental load:** you never pick a workspace number, and you keep no per-workspace shortcuts. Three keys cover send, silent send, and finish.
- **Safe close:** finish sends each window a normal close request, so an app's own unsaved-changes prompt can still appear (not tested here).
- **No force-kill:** Taskspaces never kills a process. A window that stays open keeps its task unfinished.
- **Nothing edits your config:** Taskspaces does not change Hyprland or Omarchy settings. You paste the bindings yourself.

## Terms

| Term | Meaning |
|---|---|
| Task | A workspace that Taskspaces has named. Each task has one record file. |
| Source | The workspace a task's window came from. Finishing returns windows there. |
| In-place task | A task made from a numbered workspace with **Turn workspace S into a task…**. It keeps its number. |

## Send menu

`taskspaces send` opens a menu. Rows that do not apply to your current workspace are hidden.

| Row | Grey line | Shown when | What it does |
|---|---|---|---|
| `Start task "<name>"` | `name suggested from the window title`; for Chrome, `name suggested from the window title · whole window (all tabs)` | Always | Creates a task with the suggested name |
| **Start task with my own name…** | — | Always | Creates a task with a name you type |
| **Rename this task…** | — | On a task workspace | Renames the task |
| **Turn workspace S into a task…** | `windows stay where they are` | On a numbered workspace with no task record | Turns that workspace into an in-place task |
| **Send to: <task>** / **Move to: <workspace>** | Workspace number | Other tasks, and other workspaces that are not tasks | Moves the window there. Only a task gets a record. |

`S` is the source workspace number. A suggested name that makes the main row longer than 50 characters uses `Start "<name>"` instead, preserving the full task name.

`taskspaces send --silent` uses the same menu and moves the window without following it.

### Name rules

The suggested name comes from the window title.

- For a short list of known apps, removes the app-name suffix at the end of the title. Also removes leading marks like `(3)` or `*`.
- Removes URLs, email addresses, long IDs, and numbers with 10 or more digits.
- Keeps the text before the first ` - `, ` — `, ` – `, ` · `, or ` | `.
- Removes quotes, brackets, `$`, backticks, and control characters. Caps names at 40 characters.
- Empty titles, titles like `New Tab` or `Untitled…`, and titles equal to the app name become `<App> task`, for example `Terminal task`.
- A duplicate name gets a number: `Fix login bug 2`.

## Send results

- **Start task:** the window moves to the lowest unused workspace number. That workspace is renamed to the task. The record stores the source workspace.
- **Existing task:** the window moves to that task's workspace.
- **Plain workspace:** the window moves. No record is written.
- **No focused window:** nothing moves. You get the notification "No window focused".

## Finish

`taskspaces finish` works only on a task workspace. On any other workspace you get "This workspace isn't a task".

- **No windows:** the task record is removed, and focus returns to the source workspace, or to the lowest other numbered workspace if the source is gone. For an in-place task, the workspace gets its number back as its name, and focus stays where it is.
- **Windows present:** a menu offers three rows.
  - **Close 1 window and finish** / **Close N windows and finish:** sends each window a close request, never a kill. The grey line lists the apps. Taskspaces checks every 0.25 seconds, for up to 30 seconds. It stops early if no window has closed for 5 seconds and no new window has appeared. If windows remain, the task is kept, and a notification names up to three of them by title.
  - **Send 1 window back to workspace S and finish** / **Send N windows back to workspace S and finish:** moves the windows back to the source, then finishes. For an in-place task this row reads **Keep 1 window here and finish** / **Keep N windows here and finish**. Both variants have the grey line `nothing is closed`.
  - **Cancel:** does nothing.

`N` is the window count (two or more for the plural rows); `S` is the source workspace number. The menus open at width 600. For example, `Send 10 windows back to workspace 10 and finish` is 47 characters, within the 50-character main-text limit.

## Workspace numbers

- A new task takes the lowest positive workspace number that no workspace currently uses. With workspaces 1, 2, and 4 in use, a new task takes 3.
- While the task exists, pressing `SUPER + 3` goes to the task, because the task is workspace 3. This follows from the number rule. It is not tested on a live desktop.
- Taskspaces does not rebind keys or rename numbered workspaces, except for the number a task takes.
- When an in-place task finishes, its number becomes its name again.

## Files and state

- **Task records:** one JSON file per task, at `$XDG_RUNTIME_DIR/taskspaces/<workspace id>.json`. Each record holds the name, the workspace ID, the source, and the creation time.
- **Lock:** `$XDG_RUNTIME_DIR/taskspaces.lock` stops two actions from running at once. A second action exits without a message.
- **Messages:** notifications use `omarchy-notification-send`, or `notify-send` if that is missing. They have the title `taskspaces`. With neither command, messages go to stderr.
- **Nothing else:** Taskspaces writes no config files and makes no network calls. It runs `hyprctl`, `jq`, `python3`, `flock`, and Omarchy's menu commands, plus a notification command.
- **Lifetime:** `XDG_RUNTIME_DIR` is per session, so records do not survive a reboot. This is the usual behavior of `XDG_RUNTIME_DIR`, not something Taskspaces tests.

## Bar widget

The widget shows `◆ <name>` when the active workspace is a task. Otherwise it shows the active window's title. It reads only the workspace name from Hyprland. It shares no files or state with the helper.
