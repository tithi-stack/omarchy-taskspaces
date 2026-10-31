# How taskhop works

This page describes taskhop 0.1.0. The automated tests use mock commands. Omarchy Quattro has not been tested yet.

## Terms

| Term | Meaning |
|---|---|
| Task | A workspace that taskhop has named. Each task has one record file. |
| Source | The workspace a task's window came from. Finishing returns windows there. |
| In-place task | A task made from a numbered workspace with **Make workspace N a task…**. It keeps its number. |

## Send menu

`taskhop send` opens a menu. Rows that do not apply to your current workspace are hidden.

| Row | Shown when | What it does |
|---|---|---|
| **New task: <name>** | Always | Creates a task with the suggested name |
| **New task, type a name…** | Always | Creates a task with a name you type |
| **Rename this task…** | On a task workspace | Renames the task |
| **Make workspace N a task…** | On a numbered workspace with no task record | Turns that workspace into an in-place task |
| **Send to: <task>** / **Move to: <workspace>** | Other tasks, and other workspaces that are not tasks | Moves the window there. Only a task gets a record. |

`taskhop send --silent` uses the same menu and moves the window without following it.

### Name rules

The suggested name comes from the window title.

- Removes app suffixes such as ` - Google Chrome` or ` - Visual Studio Code`, and leading marks like `(3)` or `*`.
- Removes URLs, email addresses, long IDs, and numbers with 10 or more digits.
- Keeps the text before the first ` - `, ` — `, ` – `, ` · `, or ` | `.
- Removes quotes, brackets, `$`, backticks, and control characters. Caps names at 40 characters.
- Empty titles, titles like `New Tab` or `Untitled…`, and titles equal to the app name become `<App> task`, for example `Terminal task`.
- A duplicate name gets a number: `Fix login bug 2`.

## Send results

- **New task:** the window moves to the lowest unused workspace number. That workspace is renamed to the task. The record stores the source workspace.
- **Existing task:** the window moves to that task's workspace.
- **Plain workspace:** the window moves. No record is written.
- **No focused window:** nothing moves. You get the notification "No window focused".

## Finish

`taskhop finish` works only on a task workspace. On any other workspace you get "This workspace isn't a task".

- **No windows:** the task record is removed, and focus returns to the source workspace, or to the lowest other numbered workspace if the source is gone. For an in-place task, the workspace gets its number back as its name, and focus stays where it is.
- **Windows present:** a menu offers three rows.
  - **Close N windows and finish:** asks each window to close. taskhop waits up to 30 seconds. If some windows stay open, the task is kept and you get a notification that lists them.
  - **Move windows to ws N and finish:** moves the windows back to the source, then finishes. For an in-place task this row reads **Keep windows here and finish**.
  - **Cancel:** does nothing.

## Workspace numbers

- A new task takes the lowest positive workspace number that no workspace currently uses. With workspaces 1, 2, and 4 in use, a new task takes 3.
- While the task exists, pressing `SUPER + 3` goes to the task, because the task is workspace 3. This follows from the number rule. It is not tested on a live desktop.
- taskhop does not rebind keys or rename numbered workspaces, except for the number a task takes.
- When an in-place task finishes, its number becomes its name again.

## Files and state

- **Task records:** one JSON file per task, at `$XDG_RUNTIME_DIR/taskhop/<workspace id>.json`. Each record holds the name, the workspace ID, the source, and the creation time.
- **Lock:** `$XDG_RUNTIME_DIR/taskhop.lock` stops two actions from running at once. A second action exits without a message.
- **Messages:** notifications use `omarchy-notification-send`, or `notify-send` if that is missing. They have the title `taskhop`. With neither command, messages go to stderr.
- **Nothing else:** taskhop writes no config files and makes no network calls. It runs `hyprctl`, `jq`, `python3`, `flock`, and Omarchy's menu commands, plus a notification command.
- **Lifetime:** `XDG_RUNTIME_DIR` is per session, so records do not survive a reboot. This is the usual behavior of `XDG_RUNTIME_DIR`, not something taskhop tests.

## Bar widget

The widget shows `◆ <name>` when the active workspace is a task. Otherwise it shows the active window's title. It reads only the workspace name from Hyprland. It shares no files or state with the helper.
