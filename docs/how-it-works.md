# How Taskspaces works

This page describes Taskspaces 0.1.0. The automated tests use mock commands. Omarchy Quattro has not been tested yet.

## Goals

- **No fixed assignments:** a task is not tied to an app. Its windows go where the task is.
- **Low mental load:** you never pick a workspace number, and you keep no per-workspace shortcuts. Three keys cover send, silent send, and finish.
- **Safe close:** finish sends each window a normal close request, so an app's own unsaved-changes prompt can still appear (not tested here).
- **No force-kill:** Taskspaces never kills a process. A window that stays open keeps its task unfinished.
- **Consent before config changes:** only setup edits your Hyprland bindings, after you choose Yes. Installing the plugin does not run setup.

## Setup

Run `taskspaces setup` (or the full helper path from the README). Setup needs no `XDG_RUNTIME_DIR`. It reads only `${XDG_CONFIG_HOME:-$HOME/.config}/hypr/bindings.lua` as the user bindings file. `TASKSPACES_BINDINGS_FILE` overrides that path for tests.

1. It checks for its managed block or hand-added `taskspaces` send/finish bindings. If found, it reports the configured keys and exits without changing anything.
2. It reads `hyprctl binds -j`. An unreadable reply or missing `hyprctl` stops setup. Modifier masks and keys are compared without regard to key letter case. Omarchy's stock bindings in `/usr/share/omarchy/default/hypr/bindings/*.lua` also reserve keys.
3. The suggested defaults are `Super+N` for send, the chosen send key plus Alt for silent send, and `Super+D` for finish. A taken key opens a menu naming its current action. **Use … instead** offers the first free candidate: Shift+N, Ctrl+N, then T with Super for send; Shift+D, Ctrl+D, then E with Super for finish. Silent alternatives add Alt to send's candidate list. **Pick my own key…** accepts modifiers and a letter, number, function key, or named navigation key, with up to three attempts. **Skip this shortcut** keeps the CLI available. Skipping send also skips silent send.
4. A final menu lists the real keys in grey. **Yes, add them** permits the write; **Show me the lines first** prints the exact block and returns to the menu; **No, I'll add them myself** changes nothing. Without the menu helper, a terminal gets the lines and a y/n prompt; without either, setup stops. Conflicting keys are skipped when the menu helper is unavailable.
5. After Yes, setup rechecks the file and live keys, saves a backup, appends atomically, reloads, and verifies. `taskspaces setup --dry-run` uses the same menus but prints the block after Yes and writes and reloads nothing.

The appended block has these exact marker lines around a helper variable and the selected `o.bind(...)` calls:

```lua
-- >>> taskspaces (added by `taskspaces setup`; undo with `taskspaces setup --remove`) >>>
-- The helper variable and chosen bindings go here.
-- <<< taskspaces <<<
```

Backups live at `${XDG_STATE_HOME:-$HOME/.local/state}/taskspaces/backups/bindings.lua.<UTC timestamp>`. The backup contains the original bytes. The write uses a temporary file beside the target and a rename, preserving file permissions. A symlink stays intact: setup writes its resolved target. A missing or unwritable bindings file is left alone, with a message explaining what to fix.

Verification requires `hyprctl reload` to succeed, no new lines in `hyprctl configerrors` compared with the pre-write reply, and each chosen key to appear in `hyprctl binds -j` as an exec binding to this helper and the right action. Failure restores the backup atomically and reloads again. If another program changes the bindings during verification, setup leaves those edits intact and asks you to restore the named backup yourself. If the second reload fails, the message asks you to reload yourself and gives the backup path. Pre-existing config errors do not count as new errors.

`taskspaces setup --remove` asks for consent, backs up the file, removes exactly the managed block between its markers, then reloads and verifies that its shortcuts are gone. It preserves surrounding content. With no block it says there is nothing to remove. Hand-pasted bindings are never removed; setup gives their line numbers instead. Damaged or repeated markers stop setup for manual inspection.

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
- Send and finish do not rebind keys. They only rename the workspace number a task takes; setup adds shortcuts separately with consent.
- When an in-place task finishes, its number becomes its name again.

## Files and state

- **Task records:** one JSON file per task, at `$XDG_RUNTIME_DIR/taskspaces/<workspace id>.json`. Each record holds the task name, its workspace number, the starting workspace number (`source`) and name (`source_name`), and the creation time. Earlier records without `source_name` can return only to a workspace that still has its numbered name and is not another task; otherwise the same fallback rule applies.
- **Lock:** `$XDG_RUNTIME_DIR/taskspaces.lock` stops two actions from running at once. A second action exits without a message.
- **Messages:** notifications use `omarchy-notification-send`, or `notify-send` if that is missing. They have the title `taskspaces`. With neither command, messages go to stderr.
- **Setup files:** only consented setup writes the Lua bindings file, its temporary replacement and state-directory backups. Taskspaces makes no network calls. It runs `hyprctl`, `jq`, `python3`, `flock`, and Omarchy's menu commands, plus a notification command.
- **Lifetime:** `XDG_RUNTIME_DIR` is per session, so records do not survive a reboot. This is the usual behavior of `XDG_RUNTIME_DIR`, not something Taskspaces tests.

## Bar widget

The widget shows its task icon followed by the task name when the active workspace is a task. Otherwise it shows the active window's title. It reads only the workspace name from Hyprland. It shares no files or state with the helper.
