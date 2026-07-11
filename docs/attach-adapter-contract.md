# Live-agent attach adapter contract

**Issue:** [#13](https://github.com/somebloke1/noetic-dev/issues/13)

**Status:** M0 executable contract. No tmux, PTY, WebSocket, browser, process, input, resize, detach, or spawn effect is authorized.

## Boundary

Attach is a runtime adapter capability, never controller execution authority. The controller may emit an attach effect intent and record a receipt/lifecycle event, but stores no tmux socket/pane, PTY object, WebSocket, browser, process, or terminal buffer.

`tmux` is the minimalist default. `browser_pty` is optional and must satisfy the same identity, authority, fence, reconnect, privacy, and audit semantics. Observe mode cannot send input. Interactive input requires a distinct unexpired `send_input` grant and still cannot invoke controller commands merely by typing terminal text.

## Donor lessons

- pi2 `src/apm/tmux.js` usefully keeps a project-scoped socket, argument-vector `spawnSync`, detached split, pane liveness check, and visible multi-pane layout. Its spawn path still passes a caller-built command through `sh -c`, interpolates environment values, and embeds prompts; noetic-dev instead permits only a bounded minimal bootstrap of typed argv/config references.
- pi2 phronesis tests prove that full grounding/task context should arrive after launch through an acknowledged protocol, not an oversized spawn command.
- noetic-pi browser `terminal.ts`, `ws-routes.ts`, and `pty-manager.ts` prove authenticated attach, bounded reconnect, resize, output buffering, explicit cleanup, and useful visual observability. They also expose risks: token in WebSocket query, direct terminal-input forwarding, raw PTY buffers, image payloads, and session/process identity conflation. The canonical contract uses short-lived authority references, digests input, forbids raw-output persistence, and revalidates generation/fence on every reconnect.

## Identity and reconnect

An attach binds exactly one run, node, attempt, agent, workspace lease/fence, session ID, and session generation. Adapter handles are opaque references, not authority. Reconnect succeeds only when:

- attach authority remains unexpired;
- run/attempt/agent identity still matches;
- workspace fence is current;
- session generation is unchanged; and
- bounded retry policy has not exhausted.

A stale browser socket or tmux pane is evidence, not a routable replacement. Detach ends only the viewer/input attachment; attempt cancellation requires a separate controller command.

## Bootstrap and input

Bootstrap uses an allowlisted `runtime:*` command reference, typed argv, allowlisted `env:*` references, and at most 4096 bytes. Shell metacharacters, inline prompts, raw environment assignments, and adapter-specific command strings are rejected. Full context is fetched after launch through a versioned role/session acknowledgement.

Each input frame is bounded, attributed, authorized, digested, and audited through canonical events. Secrets and raw terminal text are not copied into broad events. Terminal output may be held in a bounded adapter-local transient buffer for reconnect but is not canonical truth and is not persisted by this contract.

## Parity and lifecycle

Both adapters support observe/interactive, resize, bounded reconnect, and detach under identical policy. Browser-only rendering and tmux-only layout are presentation features. Spawn, attach, detach, and cleanup receipts are idempotent. Natural process exit, explicit detach, and authorized kill remain distinct events.

No ContextForge, tmux, or browser dependency enters the kernel. Future adapters must replay the same identity/authority/privacy fixtures and receive a separate implementation:QA pair.
