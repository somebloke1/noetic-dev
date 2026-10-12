# Scoped command entry points

`noetic disciplines`, `noetic purposes`, and `noetic recall` expose the maintained
discipline, purpose ownership, and scoped recall APIs. Each command's `--help`
describes its arguments. These commands retain the underlying scope validation
and native identities; routing does not allocate an effort or adopt old history.

The installed launcher supplies `NOETIC_APP_HOME` and `NOETIC_STATE_HOME`.
Without an explicit override, these commands use the installation's ordinal
namespace at `$NOETIC_APP_HOME/state/ordinals.sqlite3`. Discipline and purpose
namespace arguments precede their subcommand. Recall uses
`$NOETIC_STATE_HOME/runs` for both structured runs and the developer session
registry. An explicit `--runs-dir` also becomes recall's session source unless
`--sessions-home` is separately specified.

Installed `noetic harness start` also defaults to `$NOETIC_STATE_HOME/runs`.
Its final `--verify` command is preserved verbatim; verifier arguments do not
select harness storage.
Other harness operations continue to take their explicit run path. Existing
installed `serve`, `open`, `list`, and `sessions` defaults are preserved.

Explicit options, including `--option=value`, take precedence. Without the
installation environment, supply the paths required by the underlying command.
Help and routing do not create state. The native `noetic goal` interface remains
available with its existing Telos arguments; `purposes` provides explicit
ownership across effort stores.
