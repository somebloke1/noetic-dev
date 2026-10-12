# Installed GUI Startup

`deploy/systemd/user/noetic-installed-gui.service` is a reusable user-service
template for an installed Noetic application. Install Noetic first, then review
the app home, port, token location and provider executable paths for the target
installation. The service starts the GUI; it does not install releases or
supervise agent lifetimes.

## Scope

The template invokes `~/.local/bin/noetic serve` from the installation-owned
`~/.local/share/noetic-dev` directory, on loopback port 8765, with a token at
`~/.local/share/noetic-dev/operator-access/token`. The managed launcher supplies
the installation's explicit `NOETIC_STATE_HOME`; `serve` selects its `runs`
directory. An installation can override that binding with an explicit
`--runs-dir`. The selected current release supplies code; future release switches
affect the next GUI start. Starting this service does not advance or replay an
actor. Creating a project still requires an explicit project directory.

Managed launcher v2 preserves the caller's cwd for normal installed releases and
keeps adopted state explicit through `NOETIC_STATE_HOME`. Only explicit legacy
selection retains the old cwd and missing-runs startup check. Help/version no
longer require the recovery checkout. The service's installation-owned working
directory also removes the checkout dependency before the launcher runs.
Retained histories may still live at explicitly adopted external paths; moving
the working directory does not move or recreate them. Missing-history disclosure
and scope resolution remain operation-level concerns.

On dgk's existing installation, the unit deliberately retains its historical
`--runs-dir` beneath `~/workspace/synthesis-worktrees/feature-cognitional-event-journal`,
existing provider PATH and token location. Only its working directory changes to
the app home. The development CPU embedding profile is selected by a separate
installation drop-in. These local bindings are not copied into the reusable
template. Other installations inherit the user manager's PATH or set their own
`Environment="PATH=..."` drop-in so Node, Pi and selected providers are available.

`WantedBy=default.target` enables startup with the systemd user manager, normally
at login. On this host `loginctl show-user dgk -p Linger` already returned `yes`
before deployment. That setting is deliberately unchanged: the existing manager
configuration can start user services at boot without login and retain them
after logout. This is not a login-only guarantee or reboot-tested persistence.
No lingering command, sudo, new daemon framework, or reboot is required here.

## Desktop Launch

The simple user-facing launch is a desktop entry invoking `noetic open`, **after
an installed code delivery containing that command**. This source change does not
install the entry, update the installed release, or start/restart the service.
The existing service must already be listening. Bare `noetic open` does not infer
this service's custom token path: its default remains
`RUNS_DIR/../.operator-access/token`, not the service's `operator-access/token`.

Exact operator installation example for
`/home/dgk/.local/share/applications/noetic-installed-gui.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Noetic
Comment=Open the running local Noetic workspace
Exec=/home/dgk/.local/bin/noetic open --runs-dir /home/dgk/workspace/synthesis-worktrees/feature-cognitional-event-journal/.runtime/runs --token-file /home/dgk/.local/share/noetic-dev/operator-access/token --port 8765
Icon=applications-development
Terminal=false
Categories=Development;
StartupNotify=false
```

These absolute executable, runs and token paths and port 8765 intentionally match
the service's `ExecStart` above; no token value is embedded. Review all paths for
another owner or installation. Desktop `Exec` is not a shell command: do not use
`~`, `$HOME` or systemd's `%h` in place of those absolute paths. Inspect any existing
entry before an explicitly authorized installation; do not overwrite unrelated
desktop customizations.

This is a Linux/freedesktop template. A local graphical session and configured
default browser are required; menu refresh and launcher trust prompts vary by
desktop. With `Terminal=false`, an exit diagnostic may not be shown by the menu.
For troubleshooting, run the exact `Exec` command in a terminal: it reports missing
or invalid tokens, unreachable GUI, rejected pairing or browser refusal without
printing the pairing URL. Successful output means **browser handoff requested**,
not a rendered/authenticated tab. Real browser pairing, menu launch and installed
delivery remain the lead's independent QA and later deployment checks.

## Driver Lifetime

`KillMode=process` sends stop signals only to the main GUI process. A five-second
stop timeout permits SIGKILL of that main process if needed, not its descendants.
Do not replace this with `control-group` or `mixed`: detached harness drivers
remain in the service cgroup despite `start_new_session=True` and must survive
GUI stop/restart. An isolated real detached `/usr/bin/sleep` child fixture checks
same-cgroup survival through both operations without a production actor start.

Systemd warns that process-only killing is discouraged for ordinary services;
it is intentional here because driver lifetime is independently managed by the
application. A stopped GUI does not mean its cgroup is empty or actors stopped.
Do not use `systemctl kill` with all-process semantics for GUI maintenance.
User-manager shutdown, logout policy, reboot and explicit actor cancellation
remain outside this survival guarantee. The service does not recover drivers.

`Restart=on-failure`, `RestartSec=5`, `StartLimitIntervalSec=60` and
`StartLimitBurst=3` bound repeated startup failures. Manual stop is not retried.
After resolving a persistent failure, use `systemctl --user reset-failed
noetic-installed-gui.service` followed by `systemctl --user start
noetic-installed-gui.service`. No unlimited retry wrapper is installed.

## Private Output

Both standard streams append to the existing
`~/.local/share/noetic-dev/operator-access/server.log`, not journald. This log
contains the private pairing URL: do not print, paste or attach its contents.
Its directory must remain owner-only `0700`; log and token must remain `0600`.
`UMask=0077` protects newly created service output; it does not repair an existing
broad file. Validate modes before starting. No log rotation is installed; any
future rotation must preserve private permissions and append destinations.
Systemd lifecycle metadata can still appear in the journal, without GUI output.

## Operations

Inspect `~/.config/systemd/user` first. Do not overwrite an unrelated unit or
drop-in. Create/edit the intended unit using `apply_patch`; the repository copy
is a reviewed template, not an automatic installer. The app home and private
output directory must exist. Preserve existing instance-specific arguments,
provider PATH, token and drop-ins when updating a deployed unit. With an available bus:

```sh
systemd-analyze --user verify ~/.config/systemd/user/noetic-installed-gui.service
systemctl --user daemon-reload
systemctl --user start noetic-installed-gui.service
systemctl --user enable noetic-installed-gui.service
systemctl --user is-active noetic-installed-gui.service
systemctl --user is-enabled noetic-installed-gui.service
systemctl --user show noetic-installed-gui.service -p MainPID -p KillMode -p Restart
systemctl --user restart noetic-installed-gui.service
```

If a tool session inherits a private D-Bus address, explicitly address the
already-running login user's bus for these commands (this host's UID is 1000):

```sh
env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000 systemctl --user is-active noetic-installed-gui.service
```

Use the same prefix for other `systemctl --user` commands from that session.
Do not create a replacement bus/daemon if the actual user manager is unavailable.

For initial handoff, retain the known detached GUI until verification and the
child fixture pass. Capture runtime hashes/modes, exact PID/start identity, argv,
cwd and output destinations. Recheck identity immediately before sending TERM
only to that GUI; start the service and perform read-only readiness checks.
Do not use broad `pkill`, stop drivers, or start a second GUI on the same port.

If handoff fails, stop/disable only this service and restart the original
installed command detached, with the same cwd and existing private log opened
append-only. Verify readiness before declaring restoration. The original command
is the unit's `ExecStart` with `%h` expanded; keep the token value out of argv.

Acceptance checks: active/enabled; a different main PID after restart; public
shell 200; unauthenticated `/api/runs` 401; authenticated API 200 and 19 runs;
installed CLI list 19; unchanged runtime path sets, SHA-256/size and owner/mode
inventories. Read the existing capability only in the checking process, discard
history payloads, and report counts/statuses rather than token or task content.
Check both actual output descriptors and scan only this unit's journal in memory
for accidental capability disclosure without printing journal contents.

Deployment evidence is private at `/tmp/opencode/noetic-gui-service-evidence`;
the outcome and commands are in `/tmp/opencode/noetic-gui-service-report.txt`.
Temporary evidence is subject to host cleanup. No reboot/login-cycle test or
production actor execution is part of this bounded verification.
