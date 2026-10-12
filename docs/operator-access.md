# Local Operator Access

The local operator token protects history and execution APIs. It is **not a model
credential**, provider login, subscription token, account password, or approval of
individual actions. Pi, OpenCode and local-model authentication remain unchanged.

## Start And Pair

```bash
python3 -m scripts.noetic serve --runs-dir .runtime/runs --port 8765
```

The CLI binds to `127.0.0.1`. On first start it generates a 256-bit CSPRNG token in
`RUNS_DIR/../.operator-access/token`. `--token-file PATH` selects a different managed
file. Existing valid tokens are reused across restarts. The token file is `0600`;
new token-parent directories are `0700`. No existing state tree is recursively
chmodded, and merely creating a library server does not write a token to disk.

With the GUI already running, request a browser handoff from another terminal:

```bash
python3 -m scripts.noetic open --runs-dir .runtime/runs --port 8765
```

`noetic open` uses the same `--runs-dir`, `--token-file` and `--port` selectors as
`serve`. Both public commands use `NOETIC_STATE_HOME/runs` when that environment
variable is set and `--runs-dir` is absent; otherwise they default to the current
directory's `.runtime/runs`. The default token remains
`RUNS_DIR/../.operator-access/token`. A custom service token path must be passed
explicitly: neither command discovers it. For the installed service on this host,
use the [desktop launch example](installed-gui-service.md#desktop-launch), not bare
`noetic open`. That example supplies the actual runs directory, token path and port.

The opener reads and validates an **existing** owner token. It never creates,
rotates or chmods the token or any directories, and never starts a GUI, model or
actor. It requires a nonzero listener port and checks the token with a read-only
`HEAD /api/runs` request to `127.0.0.1` (five-second socket timeout, no proxy or
redirect following). Missing/invalid files, an unavailable GUI, rejected token or
failed browser handoff return a nonzero exit status with a token-free diagnostic.
Match the running service's selectors before considering any token-file repair.

The default browser receives the existing fragment pairing URL; its subprocess
standard input/output/error are disconnected from the launching terminal, with a
15-second handoff timeout. No token or pairing URL is printed, including browser
failure output. This is a local graphical-session handoff, not browser automation:
success says **Browser handoff requested**, not that a tab rendered or authenticated.
Browser selection follows Python's `webbrowser` support (including `BROWSER`).
Headless sessions and desktop-specific launcher behavior need a configured browser
and real desktop verification. A timeout/refusal does not prove no tab was attempted.

Alternatively, open the **private pairing URL printed to the owner's server
terminal**. Its token is in
`#token=...`, not a query parameter. The fragment is not sent in HTTP requests;
the UI immediately removes it from the address/history entry and holds the token
in tab-scoped `sessionStorage`. Alternatively, enter the token into the masked
field labeled `local operator token, not provider credential`. Do not enter a
provider credential. Do not share, publish, screenshot or retain terminal output
containing the pairing URL. The startup terminal is intentionally trusted.

Static HTML, JavaScript and CSS are public, contain no generated secret or actual
state paths, and initially show only the pairing shell. API reads and actions
always send `Authorization: Bearer TOKEN`; tokens in query parameters or cookies
do not authorize requests. Request logging is disabled so even accidentally pasted
query tokens and malformed request targets are not logged by this HTTP server.

## Lock And Logout

- **Lock** clears the tab's token, immediately removes private displayed content,
  and reloads the public shell. Form drafts, current page and evidence selections
  remain in tab-scoped session storage for the next successful unlock.
- **Logout / forget this tab** also removes those drafts and selections.
- **HTTP 401** triggers the same lock operation rather than leaving cached private
  evidence displayed. Late responses from the previous pairing cannot be rendered.
- An unpaired page does not poll the private APIs. Unlock checks the token before
  showing the workspace. Background model inference is not added.

Neither operation stops an already running driver, revokes a copied token, nor
logs out a provider. New drafts and tokens are stored only in `sessionStorage`,
never written to `localStorage`. Legacy drafts are preserved until an explicit
post-pairing migration choice; logout forgets only this tab's session drafts.
Browser session restore or tab duplication can retain/copy session storage; use
explicit logout when leaving a shared browser. Storage-disabled browsers can pair
in memory but cannot retain drafts or pairing through reload.

## Previous-Version Drafts

Upgrading from 0.2 does not automatically delete or import the browser's legacy
`localStorage` entry `noetic-workspace-v1`. While unpaired, the app does not read
that entry or display its contents. After valid pairing, a generic notice offers:

- **Import previous drafts:** asks for confirmation before replacing this tab's
  saved forms and view selections. Only known form fields, page, selected run,
  scroll positions and per-run evidence selections are copied. Unknown fields
  and credentials are not imported. The app writes and reads back the allowed
  state and current token in `sessionStorage` before removing the unchanged legacy
  entry, then reloads with pairing retained to restore the imported state.
- **Forget previous drafts:** asks for confirmation before explicitly deleting
  the legacy entry. This is separate from logout and does not erase current tab
  drafts. Leaving the notice alone, locking or logging out preserves the entry.

Malformed JSON or invalid known fields leave the original entry intact. Blocked,
full or unverifiable session storage prevents legacy removal. Storage errors use
generic messages without echoing draft contents, credentials or parser details.
If the legacy entry changes during import, it is not removed. Legacy data remains
browser-persistent until successful import or explicit Forget; it is not made
private merely by upgrading or pairing.

## Python And HTTP

```python
server = create_server(runs_dir, port=0)  # fresh ephemeral in-memory token
server.token                            # trusted host-process access only
server.pairing_url                      # trusted host-process access only
```

`create_server(..., access_token=token)` accepts an explicitly managed token of
32-128 URL-safe ASCII characters. There is no unauthenticated mode; empty or
malformed explicit tokens are rejected. Library-created ephemeral tokens change
for each new server unless explicitly supplied. CLI-created tokens persist.

The guard runs before route dispatch, API data reads, JSON body processing, and
actions. Missing/wrong tokens return generic `401` with `Cache-Control: no-store`
and no state, path or token details. HEAD is guarded identically and returns no
body. Unknown API routes and unsupported methods do not fall back to anonymous
access. The public exception is limited to GET/HEAD of the four static shell
routes. Successful pairing retains existing JSON/content-size and same-Origin
action checks; no permissive CORS headers are added. Token comparison uses
`hmac.compare_digest`.

## Permissions And Rotation

Existing token files must be regular, single-link, owner-owned `0600` files, not
symlinks. The immediate parent must be owner-controlled without group/other write
access. Unsafe files produce an actionable error instead of implicit repair.
Inspect ownership, permissions and links first. If it is the intended
owner-controlled file, explicitly change **only that file** to `0600`; otherwise
select a new owner-controlled private directory with `--token-file`. Existing
ancestor directories are not automatically changed. The token path and its
ancestors must remain under the owner's control.

To revoke a copied token, stop all operator servers using that token, explicitly
remove/replace its managed file, then start again and pair with the new URL.
Simply restarting the CLI reuses the token and does **not** revoke it. A crash
while initially writing a token can leave an invalid file; with the server stopped,
explicitly replace that file rather than treating invalid content as a secret.
No production restart, existing-key migration or rotation is performed by this unit.

## Scope And Checks

The isolated wheel/import check needs the existing packaging tools (`pip`,
`setuptools>=68`, `wheel`) in the test interpreter, not as runtime dependencies.
On this host those are available in `/usr/bin/python3`; the shell's default
`python3` environment lacks `pip`. No dependency installation is needed here.

```bash
/usr/bin/python3 -B -m unittest tests.programs.test_noetic_open tests.programs.test_operator_access tests.programs.test_noetic_web tests.programs.test_controller_view tests.programs.test_application_gui -q
node --check scripts/web/app.js
```

These are implementation checks using temporary state, synthetic kernels,
loopback HTTP and executable DOM adapters, not independent QA or real-browser
pairing evidence. They cover unauthorized reads/actions/HEAD/unknown routes,
authorized history and pause, retained Origin/JSON checks, no secret in HTTP
bodies/assets/logs, permissions, restart reuse, fragment removal, bearer headers,
lock/logout, auth failure and late responses. The lead owns exactly one independent
QA pass and real-browser pairing.

Opener checks use synthetic tokens and an ephemeral localhost server, with browser
handoffs explicitly mocked. A real child process with a synthetic `webbrowser.open`
checks suppression of stdout, stderr and exception output; it is not a real-browser
or installed-delivery check. Defaults/environment/explicit selectors, the custom
service-path shape, read-only state, refusal paths and existing server token loading
are covered without accessing production credentials or changing the installed GUI.

This unit restricts other ordinary local clients and unpaired browser contexts.
It does not isolate root, malicious processes running as the owner, or a person
using an unlocked paired browser. It is loopback HTTP, not a remote TLS deployment
or multi-user identity service. All token holders have the owner's operator access.
Filesystem privacy for journals, artifacts, caches and other backend stores is a
separate writer's unit; HTTP pairing does not protect existing disk copies,
backups, terminal captures or previously disclosed content.
