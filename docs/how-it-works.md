# How Taskspaces works

This page describes Taskspaces 0.1.0. The automated tests use mock commands.

## Goals

- **No fixed assignments:** a task is not tied to an app. Its windows go where the task is.
- **Low mental load:** you never pick a workspace number, and you keep no per-workspace shortcuts. Two keys cover the task menu and finish; silent send has an optional manual binding.
- **Safe close:** finish sends each window a normal close request, so an app's own unsaved-changes prompt can still appear (not tested here).
- **No force-kill:** Taskspaces never kills a process. A window that stays open keeps its task unfinished.
- **Consent before config changes:** only setup edits your Hyprland bindings, after you choose Yes. Installing the plugin does not run setup.

## Setup

Run `taskspaces setup` (or the full helper path from the README). Setup needs no `XDG_RUNTIME_DIR`. It reads only `${XDG_CONFIG_HOME:-$HOME/.config}/hypr/bindings.lua` as the user bindings file. `TASKSPACES_BINDINGS_FILE` overrides that path for tests.

1. It checks for its managed block or hand-added `taskspaces` bindings and leaves them unchanged. This includes an older five-key block. To replace it with two keys, run `taskspaces setup --remove`, then `taskspaces setup`; both changes ask for confirmation and make backups.
2. It reads `hyprctl binds -j` and Omarchy's stock Lua bindings to reserve occupied keys. An unreadable reply or missing tool stops setup. Lua shortcuts are recognised by key, modifiers and label; older `exec` entries are matched by command.
3. It offers only `Super+N` for the task menu and `Super+D` for finish. If a key is taken, **Use … instead** offers a free alternative, **Pick my own key…** allows three attempts, and **Skip this shortcut** leaves the CLI available. Send alternatives are Super+Shift+T, H and J; finish alternatives are Super+Shift+D, Super+Ctrl+D and Super+E.
4. A final menu lists the chosen keys. **Yes, add them** permits the write; **Show me the lines first** previews it; declining changes nothing. Without menus, a terminal gets y/n prompts and the exact lines; without either, setup stops.
5. After Yes, setup rechecks the file and keys, backs up, appends its block, reloads and verifies. `setup --dry-run` prints the block after Yes without writing or reloading. Go remains in the task menu and bar click; direct Go, silent send and browser keys are optional manual snippets in the README.

The appended block has these exact marker lines around a helper variable and the selected `o.bind(...)` calls:

```lua
-- >>> taskspaces (added by `taskspaces setup`; undo with `taskspaces setup --remove`) >>>
-- The helper variable and chosen bindings go here.
-- <<< taskspaces <<<
```

Backups live at `${XDG_STATE_HOME:-$HOME/.local/state}/taskspaces/backups/bindings.lua.<UTC timestamp>`. The backup contains the original bytes. The write uses a temporary file beside the target and a rename, preserving file permissions. A symlink stays intact: setup writes its resolved target. A missing or unwritable bindings file is left alone, with a message explaining what to fix.

Verification requires `hyprctl reload` to succeed, no new lines in `hyprctl configerrors` compared with the pre-write reply, and each newly chosen key to appear in `hyprctl binds -j` with the label setup wrote for its action (or, on an older config, as an `exec` binding to this helper and the right action). Removal uses the same test and fails, with a rollback, if a removed shortcut is still listed. Failure restores the backup atomically and reloads again. If another program changes the bindings during verification, setup leaves those edits intact and asks you to restore the named backup yourself. If the second reload fails, the message asks you to reload yourself and gives the backup path. Pre-existing config errors do not count as new errors.

`taskspaces setup --remove` asks for consent, backs up the file, removes exactly the managed block between its markers, then reloads and verifies that its shortcuts are gone. It preserves surrounding content. With no block it says there is nothing to remove. Hand-pasted bindings are never removed; setup gives their line numbers instead. Damaged or repeated markers stop setup for manual inspection.

## Browser windows

`taskspaces browser` works on any workspace and needs no task record or runtime directory. It asks `omarchy-cmd-default-browser` for the desktop entry, then reads its first `Exec` command from the same application locations as `omarchy-launch-browser`: `~/.local`, `~/.nix-profile`, then `/usr`, each under `share/applications`. It supports exactly Chromium, Google Chrome stable, Brave, Brave Origin, and Microsoft Edge stable.

The command reads `<user-data directory>/Local State` with Python, using `${XDG_CONFIG_HOME:-$HOME/.config}` plus `chromium`, `google-chrome`, `BraveSoftware/Brave-Browser`, `BraveSoftware/Brave-Origin`, or `microsoft-edge`, respectively. `TASKSPACES_BROWSER_STATE_DIR` overrides the user-data directory for tests. It never writes browser files. Profiles marked `is_omitted` are skipped, and names and emails lose control characters. One profile opens directly. Several profiles open a **<Browser> - new window here** menu with the profile name (at most 50 characters), signed-in email or `Local profile` in grey, and the Material Design account glyph 󰀄. Duplicate names and emails include the profile folder in grey. Cancelling launches nothing; missing or unreadable profiles produce `No browser profiles found.` and a non-zero exit. An unsupported default browser gets one notification and a non-zero exit.

It launches `uwsm-app -- <browser> --profile-directory=<folder> --new-window about:blank`, or the browser directly if `uwsm-app` is missing, detached so the helper returns immediately. It never calls Omarchy's browser launcher, handoff helper or focus helper. Omarchy's stock launcher can send a request through a running Chromium browser's singleton socket and, when given a URL, calls its focus helper to focus an existing window. Taskspaces requests an explicit new window and makes no request to focus an existing one. It leaves Omarchy's launcher and stock shortcuts unchanged.

## Terms

| Term | Meaning |
|---|---|
| Task | One identity with one native workspace per participating screen (up to two), stored in one record file. Older one-workspace records are read as one-member tasks. |
| Source | The workspace where a task started. Taskspaces remembers its number and name so it can return windows there safely. |
| In-place task | A task made from a numbered workspace with **Turn this workspace into a task…**. It keeps its number. |

## Send menu

`taskspaces send` opens a menu with the rows that move this window first, followed by the rows that leave it here. Every row has a grey description. Rows that do not apply to your current workspace are hidden. Enter starts a task with the suggested name.

| Icon | Row | Grey line | Shown when | What it does |
|---|---|---|---|---|
| 󰐗 | `Start task "<name>"` | `suggested from window title · moves this window`; Chrome includes `whole window (all tabs)` before the move description | Always | Creates a task with the suggested name |
| 󰏫 | **Start task with my own name…** | `type a custom name · moves this window` | Always | Creates a task with a name you type |
| 󰁌 | `Send to "<task>"` | Window summary followed by `· moves this window`; `no windows yet` for an empty task | Other tasks | Sends the window to that task |
| 󰁌 | **Move to another workspace…** | `pick a plain workspace · moves this window` | Plain destinations available | Opens a list of other plain workspaces |
| 󰉒 | **Go to a task…** | `switch tasks · leaves this window here` | Tasks exist | Opens the Go-to list |
| 󰉗 | **Turn this workspace into a task…** | `name this workspace · windows stay here` | On a plain numbered workspace | Names the current workspace as a task |
| 󰏫 | **Rename this task…** | `change task name · windows stay here` | On a task workspace | Renames the task |

Task rows appear most recently used first; records without a `used` time sort last.
The plain-workspace list covers the bar’s always-show range and extends to the highest workspace Hyprland currently has. It excludes this workspace, tasks and special workspaces, and sorts by number. It uses window summaries as labels, `No windows` for an empty destination, and the workspace number only in grey. Move is hidden when there are no plain destinations.
The range reads `persistentWorkspaces` from inline bar widget settings in `omarchy/shell.json` under the config directory. Missing or invalid settings use the stock range; if several widgets set it, the widest range is used.
Selecting a plain workspace moves the window there, including an empty destination that does not exist yet, without writing a task record.
Suggested names are capped at 35 characters, including any duplicate-name suffix.
Icons are Material Design glyphs from the Nerd Font shipped with Omarchy.

`taskspaces send --silent` uses the same menu and moves the window without following it.

### Go to task

`taskspaces go` opens **Go to task**, listing every task by name with the same window summaries and most-recently-used order.
Selecting a task activates its workspace on each recorded connected screen, then returns focus to the initiating screen. With one screen remaining it merges the paired areas; after reconnect it restores the recorded window placements. See [Paired-screen recovery](#paired-screen-recovery).
The send menu's **Go to a task…** row opens this list too, as does `taskspaces send` with no focused window.
With no tasks, the notification reads `No tasks yet`.
`go --dry-run` prints the focus plan for the first task without opening menus, writing state or a lock, or dispatching commands.
The bar resolves its own active workspace through the task records after a send-and-follow or a Go-to selection.

### Name rules

The suggested name comes from the window title.

- For a short list of known apps, removes the app-name suffix at the end of the title. Also removes leading marks like `(3)` or `*`.
- Removes URLs, email addresses, long IDs, and numbers with 10 or more digits.
- Splits the title at ` - `, ` — `, ` – `, ` · `, or ` | ` and uses the first useful segment. Status and shell words such as `Ready`, `Working`, or `bash` try the next segment, then fall back to `<App> task`. Terminal paths use their last component; a bare home folder falls back to `Terminal task`.
- Removes quotes, backslashes, brackets, `$`, backticks, and control characters, including from fallback app names. Suggested names are capped at 35 characters; names you type are capped at 40. Longer names end in `…`.
- Empty titles, titles like `New Tab` or `Untitled…`, and titles equal to the app name become `<App> task`, for example `Terminal task`.
- A name made only of digits gets `Task ` in front, for example `Task 2`, so the bar can distinguish it from a numbered workspace. A duplicate name gets a number, such as `Fix login bug 2`; duplicate checks also compare digit-only names with workspace numbers.

## Send results

- **Start task:** the notification reads `Started task "<task name>"`. The window moves to the lowest unused workspace number. That workspace is renamed to the task. The record stores the starting workspace's number and name. For a scratchpad or other special workspace, it records the fallback return workspace instead.
- **Existing task:** the window moves to that task's workspace; the notification reads `Sent to "<task name>"`.
- **Plain workspace:** the window moves; the notification reads `Moved to "<window summary>"`. No record is written.
- **No focused window:** the Go-to list opens; no window moves.

## Finish

`taskspaces finish` works only on a task workspace. On any other workspace you get "This workspace isn't a task".

With windows open, the menu offers these choices. `N` is the number of windows when there are two or more; `S` is the workspace number.

| Icon | Row | Grey line | What it does |
|---|---|---|---|
| 󰖭 | **Close 1 window and finish** / **Close N windows and finish** | App summary, such as `Terminal ×2, Files` | Requests that each window close, then finishes the task once all have closed |
| 󰐃 | **Keep 1 window and finish** / **Keep N windows and finish** | `returns to workspace S · nothing is closed` | Sends the windows to the return workspace and finishes the task |
| 󰐃 | **Keep 1 window and finish** / **Keep N windows and finish** | `stays in workspace S · nothing is closed` | For a task made from a numbered workspace: keeps the windows there, restores the workspace's numbered name, and finishes the task |
| 󰁍 | **Cancel** | — | Leaves the task and windows alone |

After the menu closes, Taskspaces checks the task's windows again. A window closed by hand is skipped. The legacy single-workspace flow includes a window opened meanwhile; paired tasks act only on the reviewed addresses and keep the record if any unreviewed window remains. If a window disappears just before the close or move request reaches it, finishing continues. Other dispatch failures still keep the task unfinished and show an error.

Fallback app names in the grey app summary follow the same cleaning rules as task names. Close sends a normal close request, never a kill. Taskspaces checks every 0.25 seconds, for up to 30 seconds. It stops early if no window has closed for 10 seconds and no new window has appeared. If windows remain, the task is kept, and a notification names up to three of them by title. Taskspaces does not answer save prompts for you.

In the existing single-workspace flow, the Keep destination must still exist, have the same name it had when the task started, and not belong to another task. If any of these checks fail, the windows go to workspace 1. The destination is checked when the menu opens and again before windows move. If workspace 1 also belongs to a task or has a custom name, the windows go to the lowest unused workspace number instead. Focus always follows the workspace where the windows landed.

With no windows, the task finishes without opening a menu and focus goes to that same safe return workspace. For a task made from a numbered workspace, its number becomes its name again and focus stays there.

## Paired-screen recovery

Two-screen tasks are experimental and off by default; new tasks use only one workspace even with two screens connected. To opt in, enable **Experimental two-screen tasks** in the Taskspaces widget settings. This stores `"experimentalTwoScreenTasks": true` in the `tithi-stack.taskspaces` bar entry in `${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/shell.json`. Turning it off affects new tasks only; existing two-screen tasks still support Go, Send and Finish.

With the experimental setting on, Start with two connected screens creates a primary area on the selected window's output and an empty companion on the other output. Naming an empty numbered workspace adopts only that workspace and creates the empty companion. Native names are readable and distinct: the shared task name on the first area and the name plus a trailing `·` on the second. More trailing markers avoid collisions with other workspace or task names. The current widget maps both to the shared name; an older running widget that displays raw workspace names still shows readable text. Go upgrades generated names from the earlier paired build, retaining authorized old names in the record during partial renames. A renamed paired task updates both its metadata and its readable native names. Starting with one screen and old records retain the existing single-workspace behavior. Expanding existing tasks, remapping a task to different docking connectors, and third-monitor policy are follow-ups.

Go validates all recorded IDs against live names and other task ownership before dispatch. Persistence rules include the requested output before they can create an empty area. Existing task-owned handles are updated with that binding and the readable default name; configured numbered rules remain untouched. Missing members remain reserved and are restored. With two screens, it places each workspace on its recorded output, activates both, and restores the initiating screen's task focus. The exact-version audit confirmed that an unbound persistent rule can snap a moved workspace back to the focused screen on the next property refresh. The rule now includes the requested monitor and immediately calls `hl.exec_scheduled_prop_refresh_immediately()` before verification. If placement still needs repair, `hl.dsp.workspace.move({ workspace = ..., monitor = ... })` targets only the owned ID; Go verifies ownership, focuses each screen then its workspace, and restores the initiating screen. Silent Start never uses this visible repair. The sequence is not atomic; partial failures retain the record, and a later Go retries. Fullscreen/special overlays and pointer movement need live qualification.

The runtime persistence bridge uses Hyprland 0.56's `hyprctl eval`, `hl.workspace_rule`, `persistent` and `default_name`. Handles live in `_G.__taskspaces_rules`; enabling/disabling a handle schedules the compositor's rule refresh, which the helper flushes immediately. Existing owned rules are re-registered to update their binding and default name. A configured numeric rule without an owned handle is preserved. Config reload can expire the handles; Go re-registers absent rules. If rule creation does not produce the member, Go recreates it by focusing its reserved number and restoring its name. A silent Start cannot use this visible fallback and reports a recoverable error. No `~/.config/hypr` file is edited. Finish disables and forgets all owned member handles. Task refresh also scans the owned handle table and disables handles whose task no longer exists. A generated default from a dead record is released even when its workspace ID now belongs to another live task; that task's readable name is restored before Go proceeds. Every window is preserved. A different live task's name remains a conflict, and a missing member of a valid recorded task remains reserved rather than being pruned. A freshly created owned workspace may have its ordinary numbered name until rename completes; this transitional state is accepted. Finish and prune never disable an unrelated configured rule without an owned handle; removing the plugin alone does not disable session rules, so finish paired tasks before uninstalling.

On explicit Go with only one screen, the member matching that connector becomes visible (primary fallback when neither matches). Each window from the other member gets a durable-in-session recovery entry before moving silently onto the visible member. Its address, PID, initial app identity and stable ID where available are checked before and after movement. A partial or acknowledged-but-ineffective move keeps recovery data and the task. Nothing runs automatically on unplug.

On Go with both recorded outputs back, both workspaces are restored first. Recorded merged windows return to their original members; successful entries are cleared individually. Closed windows are forgotten. Windows moved outside the task by the user are not fetched back, and a reused address with a different identity is skipped while the remaining windows restore. Windows newly opened while merged stay on their current member. Silent send never merges or splits windows. Normal send prepares and activates the destination with Go before moving the captured window, then verifies that the target is visible. Preparation failure leaves that window at its source. Silent send retains its single address-targeted move and leaves both visible workspaces unchanged.

Finish resolves either member and reviews the union once. Keep returns each reviewed window to its own member's validated source on its connected output, using its original member for merged windows. If that source is missing, renamed, task-owned or now on another screen, it uses an empty ordinary area on the member's available output or creates a fresh one there. It never sends external-screen windows to the laptop's workspace 1 merely because that number is the global fallback. Adopted members keep reviewed windows in place and regain numbered names. All task members, including absent ones, are excluded from other tasks' safe return destinations. Close never kills or answers save prompts. New windows, refused closes and partial dispatch failures preserve the task and recovery state.

## Workspace numbers

- Single-screen creation retains the existing lowest-unused-live-workspace rule. Paired creation takes the lowest positive ID not occupied by any client, recorded live task member, active monitor view, enabled numeric workspace rule, or custom/persistent workspace reservation. Empty inactive ordinary numbered areas can be reused. Its companion takes the next eligible ID. Owned rules from dead records are disabled before allocation; surviving windows and live logical tasks still reserve their numbers. Task 1 on IDs 1/3 plus a plain window on ID 2 therefore leaves 4/5 as the next pair.
- While the task exists, pressing `SUPER + 3` goes to the task, because the task is workspace 3. This follows from the number rule. It is not tested on a live desktop.
- Send and finish do not rebind keys. They only rename the workspace number a task takes; setup adds shortcuts separately with consent.
- When an in-place task finishes, its number becomes its name again.

## Files and state

- **Task records:** one JSON file per task, at `$XDG_RUNTIME_DIR/taskspaces/<primary workspace id>.json`. Paired records add `members` containing each reserved `id`, distinct readable native `name`, preferred connector `output`, `source` and `source_name`. `merged_windows` stores addresses, original member IDs, merge destinations and captured window identity for recovery. `pending_names` retains authorized intermediate names across partial creation or Finish cleanup. These additions do not change old record files on read. Each record holds the task name, its workspace number, the starting workspace number (`source`) and name (`source_name`), the creation time (`created`), and optional last-used time (`used`, epoch seconds). Starting a task, sending a window to it, or going to it writes `used`; older records without it remain valid. Earlier records without `source_name` can return only to a workspace that still has its numbered name and is not another task; otherwise the same fallback rule applies.
- **Lock:** `$XDG_RUNTIME_DIR/taskspaces.lock` stops two actions from running at once. A second action exits without a message.
- **Messages:** notifications use `omarchy-notification-send`, or `notify-send` if that is missing. They have the title `taskspaces`. With neither command, messages go to stderr.
- **Setup files:** only consented setup writes the Lua bindings file, its temporary replacement and state-directory backups. Taskspaces makes no network calls. It runs `hyprctl`, `jq`, `python3`, `flock`, and Omarchy's menu commands, plus a notification command.
- **Browser files:** browser reads the default browser desktop entry and its profile list read-only, then launches that browser through `uwsm-app` when available. Taskspaces itself makes no network requests; the launched browser retains its normal behavior.
- **Lifetime:** `XDG_RUNTIME_DIR` is per session, so records do not survive a reboot. This is the usual behavior of `XDG_RUNTIME_DIR`, not something Taskspaces tests.

## Bar widget

The widget shows its task icon followed by the task name when the active workspace is a task. Otherwise it shows the active window's title. It reads the workspace name and active window title and reads task records through the read-only `bin/taskspaces-members` helper on startup and debounced workspace/focus/rename/create/destroy/move events. A 30-second fallback refresh covers a lost event or a metadata-only edit. There is no one-second Python loop; each pair of idle bars performs four fallback queries per minute. A separate published index was not added because legacy shell flows also write task records; direct record reads keep one authoritative mapping. Each widget uses its own monitor's active workspace ID and checks its live name before showing the common task name. Native number-key changes therefore show the actual task on that screen. Native member names are readable even in a stale widget; the current widget always prefers the common task label.

A left click on either label launches your own Go-to-task list via `bin/taskspaces go`, resolved relative to the plugin. The bar host receives the click and calls the widget’s root `triggerPress(button)` hook; the inner MouseArea handles only hover. The hook ignores buttons other than the left button and uses Omarchy’s `Util.execArgv` helper to launch the command detached with the login-shell environment, passing the path as a literal argument. The widget itself never focuses, moves or closes a window; focusing happens only when you pick a row. Right and middle clicks are not handled. Hover shows the full task name and workspace number, or window title, plus a **click for tasks** hint; the cursor is a pointing hand. With no tasks, the existing command reports `No tasks yet`.

After updating the plugin, restart the bar with `omarchy-restart-shell`: the running shell keeps serving the widget file it loaded at startup.
