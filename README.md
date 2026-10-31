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

- **Send:** `SUPER + N` moves the focused window to a named task workspace. The name is suggested from the window title.
- **Send silently:** `SUPER + ALT + N` does the same, but you stay on your current workspace.
- **Finish:** `SUPER + D` asks whether to close the task's windows or send them back without closing them. For a task made from a numbered workspace, you can keep the windows there instead. The bar widget shows the task name.

The keys are suggestions. You choose them in [Bindings](#bindings).

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

The helper also needs the `XDG_RUNTIME_DIR` variable set. See [Troubleshooting](#troubleshooting).

## Install

1. Add the plugin. Omarchy shows a warning and asks you to confirm before it clones.
   ```bash
   omarchy plugin add https://github.com/tithi-stack/omarchy-taskspaces
   ```
2. Enable it. If you answered yes to "Enable now?" in step 1, skip this step.
   ```bash
   omarchy plugin enable tithi-stack.taskspaces
   ```
3. Optional: place the widget in a bar section. It starts in its default section, which is the center unless its manifest sets another. To move it:
   ```bash
   omarchy bar move tithi-stack.taskspaces --section center
   ```
4. Paste the bindings from [Bindings](#bindings) into `~/.config/hypr/bindings.lua`. Taskspaces never edits this file.
5. Reload Hyprland, then check for config errors. Fix any errors before you test.
   ```bash
   hyprctl reload && hyprctl configerrors
   ```
6. Optional: put the helper on your `PATH`, if `~/.local/bin` is on it.
   ```bash
   ln -s ~/.config/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces ~/.local/bin/taskspaces
   ```

Updates: `omarchy plugin update tithi-stack.taskspaces`. The bindings point at the helper inside the plugin folder, so you do not change them after an update.

## Bindings

Paste these into `~/.config/hypr/bindings.lua`:

```lua
-- taskspaces: send the focused window to a task, or finish the task
local taskspaces_bin = os.getenv("HOME") .. "/.config/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces"
o.bind("SUPER + N", "Send window to task", taskspaces_bin .. " send")
o.bind("SUPER + ALT + N", "Send window to task (stay here)", taskspaces_bin .. " send --silent")
o.bind("SUPER + D", "Finish task", taskspaces_bin .. " finish")
```

The keys are suggestions. If you have already remapped `SUPER + N`, `SUPER + ALT + N`, or `SUPER + D`, change the keys in the snippet to free ones.

| Keys | Action | Command |
|---|---|---|
| `SUPER + N` | Send the focused window to a task, then follow it | `taskspaces send` |
| `SUPER + ALT + N` | Send the focused window to a task, and stay here | `taskspaces send --silent` |
| `SUPER + D` | Finish the current task | `taskspaces finish` |

`taskspaces --help` prints usage. `taskspaces --version` prints `0.1.0`.

### Conflict check

- The default bindings in `/usr/share/omarchy/default/hypr/bindings/*.lua` on Omarchy 4.0.0.alpha do **not** use `SUPER + N`, `SUPER + ALT + N`, or `SUPER + D`. This was checked against those files. Omarchy Quattro was not checked.
- To check your own setup, run this before you paste the bindings:
  ```bash
  hyprctl -j binds | jq -r '.[] | select(.key == "N" or .key == "D") | "\(.modmask) \(.key) \(.dispatcher)"'
  ```
  Modmask `64` means `SUPER`, and `72` means `SUPER + ALT`. A line with `64` or `72` for `N` or `D` means that key is already bound. Find the other bind in `~/.config/hypr/bindings.lua` before you add taskspaces's line.
- To rebind a taken key, call `hl.unbind("SUPER + N")` before the matching `o.bind(...)` line, and note what the key did before.

## Usage

1. Focus the window you want to move. For example, an email window titled `Reply to the team - Mail`.
2. Press `SUPER + N`. A menu opens.
3. The first row, **Start task "Reply to the team"**, uses the suggested name. Its grey line says `name suggested from the window title` (with ` · whole window (all tabs)` added for Chrome). Press Enter to accept it, or choose **Start task with my own name…** to enter your own.
4. The window moves to a new workspace named after the task, and you follow it. A notification says `Task "Reply to the team" → workspace N`.
5. Work in the task. The bar shows `◆ Reply to the team`.
6. Press `SUPER + D` to finish. With one window, the menu offers **Close 1 window and finish**, **Send 1 window back to workspace S and finish** (or **Keep 1 window here and finish** for a task made from a numbered workspace), or **Cancel**. `S` is the number of the workspace where you started the task. With more windows, the rows show the count and use `windows`. The send-back and keep-here rows say `nothing is closed` in grey.
7. Choose one. A window that stays open, for example because an app asks you to save, keeps the task. Taskspaces stops waiting after 30 seconds and notifies you, naming up to three windows that are still open.

To send without following, press `SUPER + ALT + N` in step 2. The full menu rows and naming rules are in [How Taskspaces works](docs/how-it-works.md).

On a numbered workspace, **Turn workspace S into a task…** names the current workspace without moving its windows. Its grey line says `windows stay where they are`. Long suggested names use `Start "<name>"` so the row fits the menu; the task keeps its full name.

## Uninstall

1. Delete the `taskspaces_bin` line and the three `o.bind` lines from `~/.config/hypr/bindings.lua`. Then run `hyprctl reload`.
2. If you made the optional symlink in step 6, remove it: `rm ~/.local/bin/taskspaces`.
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
- **Notification: "No window focused".** Cause: no window had focus when you pressed `SUPER + N`. Fix: focus a window and press it again.
- **Notification: "This workspace isn't a task".** Cause: `SUPER + D` ran on a plain workspace. Fix: switch to the task workspace, then press `SUPER + D`.
- **Notification: "Dispatch failed: <reason>".** Cause: Hyprland rejected a command, or did not reply ("no reply from Hyprland"). Fix: run `hyprctl version`. If that fails, Hyprland is not reachable from this shell. If it works, the reason after the colon is Hyprland's reply to the rejected command.
- **Notification: "Missing required command: <names>".** Cause: the listed commands are not on `PATH`. Fix: install them, then check each with `command -v <name>`.
- **No notification appears, and nothing happens.** Cause: neither `omarchy-notification-send` nor `notify-send` is installed, so messages go to stderr, which a keybinding does not show. Fix: run the same command from a terminal to see the message.
- **`XDG_RUNTIME_DIR is required`, in a terminal only.** Cause: the variable is not set in that shell. Fix: run the command from your desktop session.

## FAQ

- **Does it change my Hyprland config?** No. You paste the bindings yourself. The plugin ships a helper script and a bar widget.
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
