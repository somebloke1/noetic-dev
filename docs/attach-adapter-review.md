# Attach adapter adversarial review

**Implementation:** issue #13 attach contracts

**Review count:** 1 implementation : 1 adversarial QA

## Threat pass

| Threat | Attack | Contract disposition |
|---|---|---|
| Identity confusion | reuse an adapter handle for another agent/attempt | Reject: attach binds run, node, attempt, agent, lease/fence, session, and generation; handle is opaque evidence only. |
| Unauthorized input | observer sends terminal bytes | Reject: observe excludes `send_input`; interactive requires distinct unexpired authority. |
| Stale reconnect | old WebSocket/pane reconnects after replacement | Reject: current session generation and workspace fence are mandatory on every reconnect. |
| Command injection | shell syntax or oversized prompt enters spawn | Reject: runtime reference + typed bounded argv/env references; shell metacharacters and payloads over 4096 bytes fail. |
| Session leakage | terminal output/secrets copied to durable events | Reject: restricted classification, redacted logs, input digests, and no raw-output persistence. |
| Kernel contamination | tmux/PTY/WebSocket state becomes controller state | Reject: kernel records runtime-neutral intent/receipt and lifecycle only. |
| Detach confusion | viewer detach cancels execution | Reject: detach and controller-authorized cancellation are distinct. |
| Adapter privilege drift | optional browser bypasses tmux rules | Reject: both profiles share parity assertions and fixtures. |

## Findings

1. **High — shell-bearing bootstrap. Corrected before acceptance.** Donor tmux code invokes `sh -c` around a caller-built command. The contract now excludes shell strings, permits typed argv/reference bootstrap only, caps it at 4096 bytes, and provides an injection fixture.
2. **High — stale reconnect could cross attempts. Corrected before acceptance.** Session ID alone was insufficient. Generation and current workspace fence are now mandatory.
3. **High — read-only clients could write. Corrected before acceptance.** Mode/permission consistency is executable and tested in both directions.
4. **Medium — terminal data could become durable domain truth. Corrected before acceptance.** Raw output is transient adapter-local data, not canonical truth; persistence is forbidden and audit stores digests/lifecycle.
5. **Medium — adapter handles could leak host topology. Corrected before acceptance.** The envelope accepts opaque `adapter:*` references only.

## Residual risks

- Runtime implementations must provide a shell-free process API; the contract cannot make a shell-bearing implementation safe.
- Browser credential transport remains implementation-specific. A future implementation must prove credentials are short-lived and absent from URL/access logs.
- Redaction quality, terminal escape parsing, and multi-client input arbitration require runtime tests in the implementation:QA pair.

**Judgment:** Acceptable for M0 contract publication after validators and CI pass. This does not authorize runtime attachment or process effects.
