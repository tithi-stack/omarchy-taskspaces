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
| Source | The workspace where a task started. Taskspaces remembers its number and name so it can return windows there safely. |
| In-place task | A task made from a numbered workspace with **Turn workspace S into a task…**. It keeps its number. |

## Send menu

`taskspaces send` opens a menu. Rows that do not apply to your current workspace are hidden.

| Icon | Row | Grey line | Shown when | What it does |
|---|---|---|---|---|
| 󰐗 | `Start task "<name>"` | `name suggested from the window title`; for Chrome, `name suggested from the window title · whole window (all tabs)` | Always | Creates a task with the suggested name |
| 󰏫 | **Start task with my own name…** | — | Always | Creates a task with a name you type |
| 󰏫 | **Rename this task…** | — | On a task workspace | Renames the task |
| 󰉗 | **Turn workspace S into a task…** | `windows stay where they are` | On a numbered workspace that is not already a task | Names the current workspace as a task; its windows stay there |
| 󰉒 | `Send to: <task>` / `Move to: <name>` | `workspace <id>` | Other tasks, and other workspaces that are not tasks | Moves the window there. Only a task gets a record. |

`S` is the current workspace number. Suggested names are capped at 35 characters, including any duplicate-name number. The first row always reads `Start task "<name>"` and fits the menu. Icons are Material Design glyphs from the Nerd Font shipped with Omarchy.

`taskspaces send --silent` uses the same menu and moves the window without following it.

### Name rules

The suggested name comes from the window title.

- For a short list of known apps, removes the app-name suffix at the end of the title. Also removes leading marks like `(3)` or `*`.
- Removes URLs, email addresses, long IDs, and numbers with 10 or more digits.
- Keeps the text before the first ` - `, ` — `, ` – `, ` · `, or ` | `.
- Removes quotes, backslashes, brackets, `$`, backticks, and control characters, including from fallback app names. Suggested names are capped at 35 characters; names you type are capped at 40. Longer names end in `…`.
- Empty titles, titles like `New Tab` or `Untitled…`, and titles equal to the app name become `<App> task`, for example `Terminal task`.
- A name made only of digits gets `Task ` in front, for example `Task 2`, so the bar can distinguish it from a numbered workspace. A duplicate name gets a number, such as `Fix login bug 2`; duplicate checks also compare digit-only names with workspace numbers.

## Send results

- **Start task:** the window moves to the lowest unused workspace number. That workspace is renamed to the task. The record stores the starting workspace's number and name. For a scratchpad or other special workspace, it records workspace 1 instead.
- **Existing task:** the window moves to that task's workspace.
- **Plain workspace:** the window moves. No record is written.
- **No focused window:** nothing moves. You get the notification "No window focused".

## Finish

`taskspaces finish` works only on a task workspace. On any other workspace you get "This workspace isn't a task".

With windows open, the menu offers these choices. `N` is the number of windows when there are two or more; `S` is the workspace number.

| Icon | Row | Grey line | What it does |
|---|---|---|---|
| 󰖭 | **Close 1 window and finish** / **Close N windows and finish** | App summary, such as `Terminal ×2, Files` | Requests that each window close, then finishes the task once all have closed |
| 󰐃 | **Keep 1 window and finish** / **Keep N windows and finish** | `returns to workspace S · nothing is closed` | Sends the windows to the return workspace and finishes the task |
| 󰐃 | **Keep 1 window and finish** / **Keep N windows and finish** | `stays in workspace S · nothing is closed` | For a task made from a numbered workspace: keeps the windows there, restores the workspace's numbered name, and finishes the task |
| 󰁍 | **Cancel** | — | Leaves the task and windows alone |

After the menu closes, Taskspaces checks the task's windows again. A window closed by hand is skipped; a window opened meanwhile is included. If a window disappears just before the close or move request reaches it, finishing continues. Other dispatch failures still keep the task unfinished and show an error.

Fallback app names in the grey app summary follow the same cleaning rules as task names. Close sends a normal close request, never a kill. Taskspaces checks every 0.25 seconds, for up to 30 seconds. It stops early if no window has closed for 10 seconds and no new window has appeared. If windows remain, the task is kept, and a notification names up to three of them by title. Taskspaces does not answer save prompts for you.

For a task started by moving a window, the Keep destination must still exist, have the same name it had when the task started, and not belong to another task. If any of these checks fail, the windows go to workspace 1. The destination is checked when the menu opens and again before windows move. If workspace 1 also belongs to a task or has a custom name, the windows go to the lowest unused workspace number instead. Focus always follows the workspace where the windows landed.

With no windows, the task finishes without opening a menu and focus goes to that same safe return workspace. For a task made from a numbered workspace, its number becomes its name again and focus stays there.

## Workspace numbers

- A new task takes the lowest positive workspace number that no workspace currently uses. With workspaces 1, 2, and 4 in use, a new task takes 3.
- While the task exists, pressing `SUPER + 3` goes to the task, because the task is workspace 3. This follows from the number rule. It is not tested on a live desktop.
- Taskspaces does not rebind keys or rename numbered workspaces, except for the number a task takes.
- When an in-place task finishes, its number becomes its name again.

## Files and state

- **Task records:** one JSON file per task, at `$XDG_RUNTIME_DIR/taskspaces/<workspace id>.json`. Each record holds the task name, its workspace number, the starting workspace number (`source`) and name (`source_name`), and the creation time. Earlier records without `source_name` can return only to a workspace that still has its numbered name and is not another task; otherwise the same fallback rule applies.
- **Lock:** `$XDG_RUNTIME_DIR/taskspaces.lock` stops two actions from running at once. A second action exits without a message.
- **Messages:** notifications use `omarchy-notification-send`, or `notify-send` if that is missing. They have the title `taskspaces`. With neither command, messages go to stderr.
- **Nothing else:** Taskspaces writes no config files and makes no network calls. It runs `hyprctl`, `jq`, `python3`, `flock`, and Omarchy's menu commands, plus a notification command.
- **Lifetime:** `XDG_RUNTIME_DIR` is per session, so records do not survive a reboot. This is the usual behavior of `XDG_RUNTIME_DIR`, not something Taskspaces tests.

## Bar widget

The widget shows its task icon followed by the task name when the active workspace is a task. Otherwise it shows the active window's title. It reads only the workspace name from Hyprland. It shares no files or state with the helper.
