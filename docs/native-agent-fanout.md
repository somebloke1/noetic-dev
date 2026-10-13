# Native agent multicast and broadcast

`agent_send` remains the single-recipient tool. Use `agent_multicast_send` for a list of exact `{ordinal, instantiation, session}` targets in the caller's effort. Use `agent_broadcast_send` with an explicit `population`: `direct_children`, `descendants`, or `effort`.

```json
{"targets":[{"ordinal":"0.2.1","instantiation":1,"session":1},{"ordinal":"0.2.2","instantiation":1,"session":1}],"message":"Please report your named result to me; no group acknowledgment is needed.","mode":"follow_up"}
```

```json
{"population":"direct_children","message":"The shared input changed. Use the new version on your next step; do not rebroadcast this notice.","mode":"steer"}
```

Broadcast takes one namespace snapshot of current native contexts in the chosen logical delegation population. It does not include other efforts, application-wide populations, unobserved reservations, structured-only contexts or superseded sessions. New contexts appearing after the snapshot are not added. A snapshot recipient that becomes superseded fails rather than redirecting to its successor.

Duplicate multicast targets are removed. Self is excluded by default; `include_self:true` explicitly includes the sender. Both tools permit at most 128 recipients and never silently truncate. Delivery uses up to eight concurrent ordinary native message operations. Larger populations require an explicitly narrower population or separate target lists.

The result contains a `batch_id`, frozen `recipients`, explicit `excluded` entries and ordered per-recipient `results`. Each accepted recipient retains its ordinary canonical binding and exact sender/recipient/reply route, with fanout batch provenance. `accepted` means the native envelope was accepted, not that work completed or a reply occurred. `failed` includes its error, any retained binding and `not-dispatched` or `uncertain` outcome. A binding alone does not establish delivery. A receipt persistence failure is separately reported as `receipt_error`.

The sender's retained events include the original batch body/population and individual outcomes. If the tool connection is interrupted, inspect those records and canonical bindings before choosing any retry. Never implicitly retry successful recipients; there is no automatic batch resume or all-or-nothing guarantee.

One announcement should not trigger identical rebroadcasts or group acknowledgments. Reply by `agent_send` to the exact originating sender only when a response is useful. The logical `parent` alias selects that position's current context; `creation_parent` in the registered self-context records historical native creation provenance and may no longer be sendable.
