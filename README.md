# Taskspaces

Start a task with one key, finish it with one key: you never pick a workspace number or maintain a workspace.
Send a window to a named task, open what you need across its screens, then close the task's windows or move them back.

<img src="docs/assets/hero.png" width="800" alt="Send one window to a named task workspace, open the other windows you need there, then finish the group by closing its windows or moving them back.">

Example: send one window to a task, then open the other windows you need inside it. New tasks use one screen by default; the experimental setting lets a task use two.

## Why

Picking workspace numbers, remembering what lives where, and tidying up are work of their own, especially when an urgent task interrupts. A task is not tied to one app: an email window can belong to one task and the next to another, so fixed app-to-workspace rules do not fit.

## How it works

1. **Start:** Press your send key (`Super+N` by default). Accept the name suggested from the window title with Enter; the window moves to the task's workspace and you follow it. An optional silent-send binding lets you stay where you are.
2. **Work:** Open the windows you need inside the task. The bar shows the task name; there are no workspace notes or shortcuts per workspace to remember.
3. **Finish:** Press your finish key (`Super+D` by default), then choose Close or Keep. The menu shows where kept windows will go. Close sends normal close requests; a window left open keeps the task unfinished and triggers a notification.

On a numbered workspace, **Turn this workspace into a task…** names it without moving windows; finishing with Keep makes it an ordinary numbered workspace again. Setup lets you choose free keys for these actions. See [Bindings](#bindings).

### Workspace numbering

New tasks start at workspace **6** by default, so **1 to 5 stay yours** for ordinary desktop use. On two screens, new tasks use 6–7, then 8–9; a reservation on either number skips that pair. A workspace above 5 in Omarchy's bar usually means an open task, or a window you put there yourself. Omarchy's stock bar draws workspace numbers only up to **10**; tasks above 10 remain accessible through the Taskspaces label and Go-to-task menu.

Change **First workspace for tasks** in the Taskspaces widget settings to choose another starting number. It sets `"firstTaskWorkspace": 6` inline in the `tithi-stack.taskspaces` bar entry in `${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/shell.json`, alongside `experimentalTwoScreenTasks`. It accepts integers **1 to 50**; missing or invalid values fall back to **6**. Setting it to **1** restores the previous allocation, including non-consecutive two-screen numbers when needed. Changes affect new allocation only; open tasks keep their recorded numbers.

**Turn this workspace into a task…** still works on workspaces 1 to 5. On two screens it keeps that chosen number and allocates a companion at or above the setting (for example, 3 and 6 with the default). Adopting a low workspace or lowering the setting lets you put tasks on low numbers deliberately.

**Skipped numbers:** Two-screen allocation skips numbers with windows, an active monitor, another task member, a persistent or renamed workspace, or an enabled numbered Hyprland rule. A rule can come from Omarchy's **Super+L** layout toggle. Skipping it is intentional: Hyprland cannot take just the layout back out of a merged rule, so releasing a task's rule could disable the user's rule too. Single-screen tasks keep their existing reservations for live workspaces and recorded task members, including empty workspace slots.

Run `taskspaces setup --check` to see the setting, connected screen count and one line per inspected workspace number with its reservation reasons. The listing includes the stricter two-screen reservations even when that experiment is off. It labels unused numbers below the setting **kept for you**, rather than available. This check is read-only: it needs no terminal or menus and never enters shortcut setup or reads or writes the bindings file.

## Two screens, one task

Tasks use one workspace by default, even with two screens connected.
Two-screen tasks are experimental: enable **Experimental two-screen tasks** in the Taskspaces widget settings, which sets `"experimentalTwoScreenTasks": true` in its `tithi-stack.taskspaces` bar entry in `${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/shell.json`.
New tasks then use one workspace per screen, with the other screen starting empty and both bars showing the same task name.
Go and normal Send switch both screens, silent Send leaves the visible workspaces unchanged, and Finish reviews the combined windows.
After unplugging a screen, choosing Go combines the task's windows on the remaining screen; choosing it again after reconnecting restores the moved windows, though a different connector or a third screen can leave the task stuck.
Turning the setting off affects new tasks only: existing two-screen tasks still support Go, Send and Finish, and **Forget this task** drops a stuck task without moving its windows.

## Status and requirements

**Alpha (0.1.0), requiring Omarchy 4 with a Lua Hyprland config; `.conf` configs are not supported.** The single-screen flow was tried on Omarchy 4.0.4 with Hyprland 0.56.2. Experimental two-screen behavior has mock coverage and still needs a real desktop trial, including unplug/replug, both bar labels and fullscreen windows. App save prompts also need a desktop trial. The browser helper supports Chromium-family browsers only.
See [Status](#status) for runtime tools and limits.

## Install

Repository: `omarchy-taskspaces`; plugin id: `tithi-stack.taskspaces`; command: `taskspaces`. Installing alone does not add shortcuts.

1. Add the plugin and choose Yes when asked to enable it. Omarchy shows a warning and asks you to confirm before it clones.
   ```bash
   omarchy plugin add https://github.com/tithi-stack/omarchy-taskspaces
   ```
2. Set up your shortcuts. Run this one line, then choose **Yes, add them** to allow the change:
   ```bash
   "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces" setup
   ```
   Setup offers two keys: `Super+N` for the task menu and `Super+D` for finish. It backs up your bindings first, checks the reload, and restores the backup if verification fails. It reports the keys you chose. **Show me the lines first** previews the exact block; **No, I'll add them myself** leaves your file alone.

The plugin never touches your Hyprland files unless you run `taskspaces setup` and choose Yes. Installing or enabling it does not run setup.

If a shortcut is already taken, setup names what uses it and offers a free alternative when one is available. You can also pick your own key or skip that shortcut. Existing shortcuts are never replaced.

Updates: `omarchy plugin update tithi-stack.taskspaces`. The bindings point at the helper inside the plugin folder, so you do not change them after an update.

Re-running setup leaves an existing managed block unchanged, including an older five-key block. To replace it with two keys, run `taskspaces setup --remove`, then `taskspaces setup`; each change asks for confirmation and makes a backup.

## Bindings

Setup offers only `Super+N` for start, send, go and rename through its menu, and `Super+D` for finish. After the optional PATH link, run `taskspaces setup` to check whether shortcuts are already installed. `taskspaces setup --dry-run` asks the same questions and prints the block after Yes, without writing or reloading.

These are suggested defaults. Use the actual keys you chose in setup or in your manual bindings. After manual changes, run `hyprctl reload` and `hyprctl configerrors`.

| Suggested default | Action | Command |
|---|---|---|
| `SUPER + N` | Send the focused window to a task, then follow it | `taskspaces send` |
| `SUPER + ALT + N` (manual, optional) | Send the focused window to a task, and stay here | `taskspaces send --silent` |
| `SUPER + D` | Finish the current task | `taskspaces finish` |
| `SUPER + ALT + T` (manual, optional) | Go to a task by name | `taskspaces go` |
| `SUPER + ALT + B` (manual, optional) | Open a new browser window here | `taskspaces browser` |

`taskspaces --help` prints usage. `taskspaces --version` prints `0.1.0`.

### Conflict check

Setup compares modifier masks and keys with `hyprctl binds -j` and checks Omarchy's stock Lua bindings before suggesting an alternative. If it cannot read live shortcuts, it stops without writing. For manual setup, inspect `hyprctl binds -j` yourself and choose free keys; do not remove someone else's shortcut to make room.

## Optional

If your bar already shows the window title, turn off **Show the window title outside a task** in the widget settings.

Move the widget to the center of your bar:

```bash
omarchy bar move tithi-stack.taskspaces --section center
```

Put the helper on your `PATH`, if `~/.local/bin` is on it:

```bash
ln -s "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces" ~/.local/bin/taskspaces
```

### Manual Lua bindings

Paste these suggested defaults into `${XDG_CONFIG_HOME:-$HOME/.config}/hypr/bindings.lua` only after checking that the keys are free. Adjust the helper path if you use a custom `XDG_CONFIG_HOME`:

```lua
-- taskspaces: send the focused window to a task, or finish the task
local taskspaces_bin = os.getenv("HOME") .. "/.config/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces"
o.bind("SUPER + N", "Send window to task", taskspaces_bin .. " send")
o.bind("SUPER + D", "Finish task", taskspaces_bin .. " finish")
-- Optional: check that each key is free before uncommenting.
-- o.bind("SUPER + ALT + N", "Send window to task (stay here)", taskspaces_bin .. " send --silent")
-- o.bind("SUPER + ALT + T", "Go to task", taskspaces_bin .. " go")
-- o.bind("SUPER + ALT + B", "New browser window here", taskspaces_bin .. " browser")
```

## Usage

1. Focus the window you want to move. For example, an email window titled `Reply to the team - Mail`.
2. Press your send key (`Super+N` by default). A menu opens.
3. The first row, **Start task "Reply to the team"**, uses the suggested name. Its grey line says `suggested from window title · moves this window` (Chrome also shows `whole window (all tabs)`). Press Enter to accept it, or choose **Start task with my own name…** to enter your own.
4. The window moves to a new workspace named after the task, and you follow it. A notification says `Started task "Reply to the team"`.

The menu puts rows that move this window first: suggested name, custom name, **Send to "<task>"**. Rows that leave it here follow: **Go to a task…**, then **Turn this workspace into a task…** or **Rename this task…**. Each row has a grey description; choices that do not apply stay hidden.

To open a browser inside the task, use the optional new-browser-window shortcut; the stock launcher can take you to a browser window elsewhere. See [Opening more windows in a task](#opening-more-windows-in-a-task).

The bar shows the task icon followed by `Reply to the team`.

Press your finish key (`Super+D` by default) to finish. With one window, choose **Close 1 window and finish**, **Keep 1 window and finish**, or **Cancel**. With more windows, the rows show the count and use `windows`. The keep row says `returns to workspace S · nothing is closed` in grey, or `stays in workspace S · nothing is closed` for a task made from a numbered workspace. `S` is the workspace number.

Choose one. If you choose Close and an app keeps its window open, for example to ask you to save, the task stays unfinished. Taskspaces waits up to 30 seconds. It stops early after 10 seconds with no windows closing if no new window has appeared, then names up to three windows still open. Windows are checked again before the choice runs. Paired tasks act only on the reviewed windows; a new window keeps the task unfinished.

To send without following, add the optional `Super+Alt+N` binding above and press it in step 2. The full menu rows and naming rules are in [How Taskspaces works](docs/how-it-works.md).

On a numbered workspace, **Turn this workspace into a task…** names the current workspace without moving its windows; finishing that task with Keep leaves the windows there and restores the workspace's numbered name. Its grey line says `name this workspace · windows stay here`. Suggested names are capped at 35 characters so the first row always reads `Start task "<name>"`. Names you type are capped at 40 characters. Quotes and backslashes are removed from task names; names taken from an app are cleaned too. A name made only of digits gets `Task ` in front, for example `Task 2`.

The menu uses these icons: 󰐗 for the suggested name, 󰏫 for typing or renaming, 󰉗 for naming the current workspace, 󰁌 for sending, 󰉒 for going to a task, 󰖭 for Close, 󰐃 for Keep, and 󰁍 for Cancel. The menu uses the Nerd Font icons included with Omarchy. Send choices show window summaries followed by `· moves this window` in grey.

Finishing removes the task record. In the single-screen flow, kept windows return to its starting workspace only if it still has the same name and is not another task. Otherwise they go to workspace 1. If workspace 1 is also in use by a task or has a custom name, Taskspaces uses the lowest unused workspace number. Focus follows the windows. Tasks started from a scratchpad also return to workspace 1, subject to that same safety check.

### Back to a task

Focus a window and press your send key, then choose **Send to "<task>"** to send it there and follow it.
Task rows show their windows in grey, with the most recently used task first.
Silent send leaves you where you are; its notification reads `Sent to "Field Job Posting"` when you choose that task.

To return without moving a window, left-click the bar label (task name or window title), choose **Go to a task…** in the send menu, or run `taskspaces go`.
When opened from the task menu, the Go list has a **Back** row that returns to that menu; Escape closes it, and direct Go or bar clicks have no Back row.
The widget itself never focuses, moves or closes a window. A click only launches your own Go-to-task list; focusing happens only when you pick a row. Hover still shows the full label with a **click for tasks** hint.
For a direct key, paste the optional `Super+Alt+T` binding above after checking it is free.
Choose a task to focus it; the bar shows its name.
If the Go-to list has no tasks, the notification reads `No tasks yet`.

On an empty numbered workspace, the send key opens **Task** with **Turn this workspace into a task…** (`name this empty workspace` in grey), or **Rename this task…** (`change this empty task name`) if it is already a task. **Go to a task…** (`switch to another task`) appears when other tasks exist. Naming uses the same **Task name** prompt and keeps you here.

For an existing single-workspace task that is not persistent, the confirmation adds `open a window before leaving or this name will be lost`. Hyprland drops that workspace when you leave it empty; its name disappears, and Taskspaces removes its record on the next task refresh. Open a window before switching away to keep the task. Experimental two-screen tasks keep missing areas recoverable while at least one area exists; when all areas are gone and no windows remain, the next bar refresh or task action retires the record, and the next task action releases its rules and restores surviving task workspace names. Other workspaces without a focused window keep the Go-to list fallback.

## Opening more windows in a task

Omarchy's stock browser launcher can hand a request to the running Chromium browser; when given a URL, it also focuses an existing browser window, which can take you back to that window's workspace. `taskspaces browser` requests a fresh window here with an existing profile, offering a profile picker only when there is more than one; it works on any workspace and leaves the stock `Super+Shift+Return` shortcut untouched.

Supported Chromium browsers: Chromium, Google Chrome (`google-chrome-stable`), Brave, Brave Origin, and Microsoft Edge (`microsoft-edge-stable`). With no saved profiles, it reports `No browser profiles found.`; open your browser normally first to create one.

For a direct key, paste the optional `Super+Alt+B` binding above after checking it is free. Setup does not offer a browser binding. `setup --remove` removes any optional lines inside its marked block, including those from an older setup; bindings pasted outside the block stay in place.

## Uninstall

1. Finish or Forget any two-screen tasks first to release their temporary workspace rules, then remove setup's shortcuts before deleting the plugin:
   ```bash
   "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces" setup --remove
   ```
   Choose **Yes, remove them**. Only the managed block is removed, after a backup. If you pasted the manual snippet, setup tells you which binding lines to delete yourself; also delete its `taskspaces_bin` line, then run `hyprctl reload`.
2. If you made the optional PATH symlink, remove it: `rm ~/.local/bin/taskspaces`.
3. Remove the plugin. This disables it, then deletes its folder:
   ```bash
   omarchy plugin remove tithi-stack.taskspaces
   ```
4. Optional: delete leftover task records. They live in the runtime directory, which your session normally clears.
   ```bash
   rm -rf "${XDG_RUNTIME_DIR:?}/taskspaces"
   ```

Already removed the plugin? Its shortcuts stay in your bindings file and do nothing. Open `~/.config/hypr/bindings.lua`, delete the lines from `-- >>> taskspaces` to `-- <<< taskspaces <<<` (including the marker lines), then run `hyprctl reload`. Setup's backups are in `~/.local/state/taskspaces/backups/` (or `$XDG_STATE_HOME/taskspaces/backups/` if set).

Disabling the plugin hides the bar label only. The shortcuts keep working until you run `taskspaces setup --remove`.

## Troubleshooting

- **A task is stuck.** Press `Super+D` on it and choose **Forget this task**, or run `taskspaces forget --task-id ID` with its primary workspace number. Forget removes the task record and rules, restores numbered workspace names, and leaves every window where it is. `taskspaces forget` forgets the task on the current workspace.

- **The key does nothing.** Cause: another Taskspaces action holds the lock, and the helper exits silently when it cannot get it. Or the bind did not load. Fix: wait a second and press again. If it still does nothing, run `hyprctl configerrors`.
- **Notification: "No tasks yet".** Cause: the Go-to list has no tasks to show. Fix: focus a window and use the send key to start a task.
- **Notification: "This workspace isn't a task".** Cause: your finish key ran on a plain workspace. Fix: switch to the task workspace, then press your finish key (`Super+D` by default).
- **Notification: "Dispatch failed: <reason>".** Cause: Hyprland rejected a command, or did not reply ("no reply from Hyprland"). Fix: run `hyprctl version`. If that fails, Hyprland is not reachable from this shell. If it works, the reason after the colon is Hyprland's reply to the rejected command.
- **Notification: "Missing required command: <names>".** Cause: the listed commands are not on `PATH`. Fix: install them, then check each with `command -v <name>`.
- **No notification appears, and nothing happens.** Cause: neither `omarchy-notification-send` nor `notify-send` is installed, so messages go to stderr, which a keybinding does not show. Fix: run the same command from a terminal to see the message.
- **`XDG_RUNTIME_DIR is required`, in a terminal only.** Cause: the variable is not set in that shell. Fix: run the command from your desktop session.

## FAQ

- **Does it change my Hyprland config?** Setup edits your Lua bindings file only after you choose Yes, with a backup and `setup --remove` to undo its block. Experimental two-screen tasks, off by default, also use `hyprctl eval` to add temporary rules to the running compositor without editing a config file. A config reload, such as a theme change, clears those rules; empty task workspaces can disappear until Go restores them.
- **Does it use the network or sudo?** No. It runs only local commands. See [SECURITY.md](SECURITY.md).
- **Can I keep using numbered workspaces?** Yes. A task takes the lowest unused number while it exists. See [Workspace numbers](docs/how-it-works.md#workspace-numbers).
- **Does it work with a `.conf` Hyprland config?** No. Omarchy 4 with a Lua Hyprland config is required; task actions use Lua dispatchers.
- **Is it in a plugin marketplace?** Not yet.

## Status

See [Status and requirements](#status-and-requirements) for release status and untested desktop behavior.

Omarchy 4 with a Lua Hyprland config is required; `.conf` configs are not supported. A task takes a workspace number. Finish can close windows; it never force-kills processes or answers save prompts. Focus returns to the safe return workspace described in [Usage](#usage).

| Requirement | Used for |
|---|---|
| Hyprland, with `hyprctl` on `PATH` | Moving, renaming, focusing, and closing windows |
| `jq`, `python3`, `flock`, `bash`, GNU coreutils | Script logic, name rules, and a lock so one action runs at a time |
| `omarchy-menu-select`, `omarchy-menu-input` | Menus and the name prompt. These ship with Omarchy. |
| `omarchy-notification-send` (preferred) or `notify-send` (fallback) | Notifications. Without either, messages go to stderr. |

Check your Omarchy version with `omarchy version`. The targeted release supplies the plugin system and Lua bindings.
Send, Go, Finish and Forget also need `XDG_RUNTIME_DIR` set; setup and browser do not. See [Troubleshooting](#troubleshooting).

## More

- [How Taskspaces works](docs/how-it-works.md): menus, naming rules, finish behavior, and state files
- [CONTRIBUTING.md](CONTRIBUTING.md): tests and how to propose changes
- [SECURITY.md](SECURITY.md): what the plugin runs, and how to report a vulnerability
- [CHANGELOG.md](CHANGELOG.md): release history

## License

MIT. See [LICENSE](LICENSE).
