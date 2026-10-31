# Taskspaces

Turn the window you're in into a task: one key to start, one key to finish.

**Status: alpha (0.1.0).** Targets Omarchy Quattro (4.0.0.alpha). See [Status](#status).

<!-- Preview: add a screenshot or short GIF here once one exists. -->

## The problem

Unrelated tasks pile up in one set of workspaces, and an urgent task interrupts the one you are in. Fixed app-to-workspace assignments do not fit, because a task is not tied to an app: one email window can belong to one task, and the next email window to another.

## The idea

- **The workspace follows the task.** Sending the first window creates the task's workspace. Finishing removes the task's record, and Hyprland drops the workspace once it is empty (not tested here).
- **Nothing to maintain.** You never pick a workspace number, keep notes, or remember a shortcut per workspace. Three keys cover send, silent send, and finish.
- **Send.** The first menu row is the suggested name, taken from the window title. Enter accepts it.
- **Finish.** Each window gets a normal close request, so an app's own unsaved-changes prompt can still appear (not tested here). Nothing is force-killed. Focus returns to the workspace the task came from.
- **Open windows.** If a window stays open, the task is not marked finished, and you get a notification.

## What it does

- **Send:** your send key (`Super+N` by default) moves the focused window to a named task workspace. The name is suggested from the window title.
- **Send silently:** your silent send key (`Super+Alt+N` by default) does the same, but you stay on your current workspace.
- **Finish:** your finish key (`Super+D` by default) asks whether to close or keep the task's windows. The keep option shows where the windows will go and confirms that nothing is closed. The bar widget shows the task name.

Setup suggests these defaults and lets you choose free keys. See [Bindings](#bindings).

## How it differs

Parts of this exist in other projects. Some tools give you places to organize windows, such as pre-declared workspaces or bar switchers. Another is a heavier task manager. Taskspaces differs in the lifecycle: the workspace is made for a task and finished with it. Numbered workspaces keep their names and bindings, except that a task takes one number (see [Workspace numbers](docs/how-it-works.md#workspace-numbers)).

- **[jsimonrichard/hypr-taskspace](https://github.com/jsimonrichard/hypr-taskspace)** is a heavier task manager. Each task gets its own named workspaces. It can use git worktrees for linked repos, runs a systemd user daemon (`tskd`), and opens a control overlay on `SUPER + Tab`. Choose it if you want that model.
- **[tornikegomareli/omarchy-spaces](https://github.com/tornikegomareli/omarchy-spaces)** is a different tool: a bar workspace switcher that shows the apps open on each workspace. Its README describes switching and previews, not sending windows to tasks.

omarchy-taskspaces is not affiliated with hypr-taskspace or omarchy-spaces; the similar names are a coincidence.

Taskspaces has no daemon and no overlay. It is one helper script and one bar widget. Both project descriptions were checked on 2026-10-30.

## Requirements

| Requirement | Used for |
|---|---|
| Omarchy Quattro (4.0.0.alpha) | Plugin system and Lua bindings |
| Hyprland, with `hyprctl` on `PATH` | Moving, renaming, focusing, and closing windows |
| `jq`, `python3`, `flock`, `bash`, GNU coreutils | Script logic, name rules, and a lock so one action runs at a time |
| `omarchy-menu-select`, `omarchy-menu-input` | Menus and the name prompt. These ship with Omarchy. |
| `omarchy-notification-send` (preferred) or `notify-send` (fallback) | Notifications. Without either, messages go to stderr. |

Check your Omarchy version with `cat /usr/share/omarchy/version`.

Send and finish also need the `XDG_RUNTIME_DIR` variable set. Setup and browser do not. See [Troubleshooting](#troubleshooting).

## Install

1. Add the plugin. Omarchy shows a warning and asks you to confirm before it clones.
   ```bash
   omarchy plugin add https://github.com/tithi-stack/omarchy-taskspaces
   ```
2. Enable it. If you answered yes to "Enable now?" in step 1, skip this step.
   ```bash
   omarchy plugin enable tithi-stack.taskspaces
   ```
3. Set up your shortcuts. Run this one line, then choose **Yes, add them** to allow the change:
   ```bash
   "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces" setup
   ```
   Setup offers send, silent send and finish, plus an optional **new browser window here** shortcut for a supported browser. It backs up your bindings first, checks the reload, and restores the backup if verification fails. It reports the keys you chose. **Show me the lines first** previews the exact block; **No, I'll add them myself** leaves your file alone.
4. Optional: move the widget to the center of your bar:
   ```bash
   omarchy bar move tithi-stack.taskspaces --section center
   ```
5. Optional: put the helper on your `PATH`, if `~/.local/bin` is on it:
   ```bash
   ln -s "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces" ~/.local/bin/taskspaces
   ```

The plugin never touches your Hyprland files unless you run `taskspaces setup` and choose Yes. Installing or enabling it does not run setup.

If a shortcut is already taken, setup names what uses it and offers a free alternative. You can also pick your own key or skip that shortcut. Silent send starts with your chosen send key plus Alt; if that is taken, you can choose another. Existing shortcuts are never replaced.

Updates: `omarchy plugin update tithi-stack.taskspaces`. The bindings point at the helper inside the plugin folder, so you do not change them after an update.

Already have setup's three Taskspaces shortcuts? Run setup again to add only the optional browser shortcut. If a `taskspaces browser` shortcut already exists in your bindings file or live shortcuts, setup reports its key and changes nothing.

## Bindings

Setup is the primary path. After the optional PATH link, run `taskspaces setup` to check whether shortcuts are already installed. `taskspaces setup --dry-run` asks the same questions and prints the block after Yes, without writing or reloading.

### Manual alternative

Paste these suggested defaults into `${XDG_CONFIG_HOME:-$HOME/.config}/hypr/bindings.lua` only after checking that the keys are free. Adjust the helper path if you use a custom `XDG_CONFIG_HOME`:

```lua
-- taskspaces: send the focused window to a task, or finish the task
local taskspaces_bin = os.getenv("HOME") .. "/.config/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces"
o.bind("SUPER + N", "Send window to task", taskspaces_bin .. " send")
o.bind("SUPER + ALT + N", "Send window to task (stay here)", taskspaces_bin .. " send --silent")
o.bind("SUPER + D", "Finish task", taskspaces_bin .. " finish")
-- Optional: check that the key is free before uncommenting.
-- o.bind("SUPER + ALT + B", "New browser window here", taskspaces_bin .. " browser")
```

These are suggested defaults. Use the actual keys you chose in setup or in your manual bindings. After manual changes, run `hyprctl reload` and `hyprctl configerrors`.

| Suggested default | Action | Command |
|---|---|---|
| `SUPER + N` | Send the focused window to a task, then follow it | `taskspaces send` |
| `SUPER + ALT + N` | Send the focused window to a task, and stay here | `taskspaces send --silent` |
| `SUPER + D` | Finish the current task | `taskspaces finish` |
| `SUPER + ALT + B` (optional) | Open a new browser window here | `taskspaces browser` |

`taskspaces --help` prints usage. `taskspaces --version` prints `0.1.0`.

### Conflict check

Setup compares modifier masks and keys with `hyprctl binds -j` and checks Omarchy's stock Lua bindings before suggesting an alternative. If it cannot read live shortcuts, it stops without writing. For manual setup, inspect `hyprctl binds -j` yourself and choose free keys; do not remove someone else's shortcut to make room.

## Usage

1. Focus the window you want to move. For example, an email window titled `Reply to the team - Mail`.
2. Press your send key (`Super+N` by default). A menu opens.
3. The first row, **Start task "Reply to the team"**, uses the suggested name. Its grey line says `name suggested from the window title` (with ` · whole window (all tabs)` added for Chrome). Press Enter to accept it, or choose **Start task with my own name…** to enter your own.
4. The window moves to a new workspace named after the task, and you follow it. A notification says `Task "Reply to the team" → workspace N`.
5. Work in the task. The bar shows the task icon followed by `Reply to the team`.
6. Press your finish key (`Super+D` by default) to finish. With one window, choose **Close 1 window and finish**, **Keep 1 window and finish**, or **Cancel**. With more windows, the rows show the count and use `windows`. The keep row says `returns to workspace S · nothing is closed` in grey, or `stays in workspace S · nothing is closed` for a task made from a numbered workspace. `S` is the workspace number.
7. Choose one. If you choose Close and an app keeps its window open, for example to ask you to save, the task stays unfinished. Taskspaces waits up to 30 seconds. It stops early after 10 seconds with no windows closing if no new window has appeared, then names up to three windows still open. Windows closed or opened while the menu was open are checked again before the choice runs.

To send without following, press your silent send key (`Super+Alt+N` by default) in step 2. The full menu rows and naming rules are in [How Taskspaces works](docs/how-it-works.md).

On a numbered workspace, **Turn workspace S into a task…** names the current workspace without moving its windows. Its grey line says `windows stay where they are`. Suggested names are capped at 35 characters so the first row always reads `Start task "<name>"`. Names you type are capped at 40 characters. Quotes and backslashes are removed from task names; names taken from an app are cleaned too. A name made only of digits gets `Task ` in front, for example `Task 2`.

The menu uses these icons: 󰐗 for the suggested name, 󰏫 for typing or renaming, 󰉗 for naming the current workspace, 󰉒 for sending to another workspace, 󰖭 for Close, 󰐃 for Keep, and 󰁍 for Cancel. The menu uses the Nerd Font icons included with Omarchy. Existing-task and workspace choices spell out `workspace <id>` in grey.

For a task started by moving a window, kept windows return to its starting workspace only if it still has the same name and is not another task. Otherwise they go to workspace 1. If workspace 1 is also in use by a task or has a custom name, Taskspaces uses the lowest unused workspace number. Focus follows the windows. Tasks started from a scratchpad also return to workspace 1, subject to that same safety check.

## Opening more windows in a task

Omarchy's stock browser launcher can hand a request to the running Chromium browser; when given a URL, it also focuses an existing browser window, which can take you back to that window's workspace. `taskspaces browser` requests a fresh window here with an existing profile, offering a profile picker only when there is more than one; it works on any workspace and leaves the stock `Super+Shift+Return` shortcut untouched.

Supported Chromium browsers: Chromium, Google Chrome (`google-chrome-stable`), Brave, Brave Origin, and Microsoft Edge (`microsoft-edge-stable`). Firefox-based browsers, including Firefox and Zen, and other browsers are not supported yet. With no saved profiles, it reports `No browser profiles found.`; open your browser normally first to create one.

Setup offers this as a separate optional shortcut before the final confirmation. It starts with `Super+Alt+B` (B for browser); if taken, it offers `Super+Alt+W`, then `Super+Alt+C` when free, your own key, or a skip. The stock browser shortcut stays in place. Removing setup's shortcuts with `taskspaces setup --remove` also removes its optional browser line.

## Uninstall

1. Remove setup's shortcuts before deleting the plugin:
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

## Troubleshooting

- **The key does nothing.** Cause: another Taskspaces action holds the lock, and the helper exits silently when it cannot get it. Or the bind did not load. Fix: wait a second and press again. If it still does nothing, run `hyprctl configerrors`.
- **Notification: "No window focused".** Cause: no window had focus when you pressed your send key. Fix: focus a window and press it again.
- **Notification: "This workspace isn't a task".** Cause: your finish key ran on a plain workspace. Fix: switch to the task workspace, then press your finish key (`Super+D` by default).
- **Notification: "Dispatch failed: <reason>".** Cause: Hyprland rejected a command, or did not reply ("no reply from Hyprland"). Fix: run `hyprctl version`. If that fails, Hyprland is not reachable from this shell. If it works, the reason after the colon is Hyprland's reply to the rejected command.
- **Notification: "Missing required command: <names>".** Cause: the listed commands are not on `PATH`. Fix: install them, then check each with `command -v <name>`.
- **No notification appears, and nothing happens.** Cause: neither `omarchy-notification-send` nor `notify-send` is installed, so messages go to stderr, which a keybinding does not show. Fix: run the same command from a terminal to see the message.
- **`XDG_RUNTIME_DIR is required`, in a terminal only.** Cause: the variable is not set in that shell. Fix: run the command from your desktop session.

## FAQ

- **Does it change my Hyprland config?** Only when you run setup and choose Yes. It edits only your Lua bindings file, backs it up outside your config folder, and can undo its managed block with `taskspaces setup --remove`.
- **Does it use the network or sudo?** No. It runs only local commands. See [SECURITY.md](SECURITY.md).
- **Can I keep using numbered workspaces?** Yes. A task takes the lowest unused number while it exists. See [Workspace numbers](docs/how-it-works.md#workspace-numbers).
- **Does it work with a legacy `.conf` Hyprland config?** Unverified. Only the Lua form is documented.
- **Is it in a plugin marketplace?** Not yet.

## Status

- Version 0.1.0, alpha. Target: Omarchy Quattro (4.0.0.alpha).
- Automated tests use mock `hyprctl` and menu commands. Quattro has not been tested yet.
- Legacy `.conf` support: unverified.
- Limits: a task takes a workspace number. Finish can close windows, and Taskspaces does not answer their save prompts.

## More

- [How Taskspaces works](docs/how-it-works.md): menus, naming rules, finish behavior, and state files
- [CONTRIBUTING.md](CONTRIBUTING.md): tests and how to propose changes
- [SECURITY.md](SECURITY.md): what the plugin runs, and how to report a vulnerability
- [CHANGELOG.md](CHANGELOG.md): release history

## License

MIT. See [LICENSE](LICENSE).
