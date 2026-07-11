# ContextForge operational dependency and continuity inventory

**Issue:** [#14](https://github.com/somebloke1/noetic-dev/issues/14)

**Observation time:** 2026-07-11 10:00 CDT

**Decision:** ContextForge is not noetic-dev's architectural backbone, but it is a live shared transport/control dependency and must remain operational. This inventory performed no service, process, registry, token, permission, client-config, or runtime mutation.

Machine-readable findings and gates live in `../spec/infrastructure/contextforge-continuity.json`.

## Verified current topology

```text
Pi ──stdio── repo wrapper ──HTTP/MCP + scoped token── host ContextForge :4444
                                                       │
OpenCode ──HTTP/MCP + Authorization────────────────────┤
                                                       ├─ bridge/service :9100..:9108
                                                       └─ virtual server → tool/prompt/resource surface

Development harness clients ── isolated ContextForge :4445
                                      └─ sidecars :9201..:9209

Pi Serena ── direct local project-from-cwd process (explicit non-ContextForge exception)
```

Read-only health probes returned HTTP 200 for host `/health`, host `/ready`, and development Docker `/health`. `contextforge.target` is enabled and active. The host gateway and listed bridges are active; all expected host ports 4444 and 9100–9108 are listening. The development gateway and sidecars are also running, but are a separate successor/test surface, not fallback evidence for host-live continuity.

## Consumers

| Consumer | Verified source | Current attachment | Services / implications |
|---|---|---|---|
| Pi runtime used by this work | `~/.pi/agent/mcp.json`; live `mcp` readback | Six local stdio entries launch `cf-controlplane/scripts/contextforge_mcp_wrapper.py`; Serena launches directly | ContextForge: Chrome DevTools, Context7, GitHub, mentality, Playwright, web search. Live readback: 7/7 MCP servers, 177 tools. Serena is not ContextForge-backed. |
| OpenCode | `~/.config/opencode/opencode.json` (values redacted) | Six remote streamable-HTTP virtual-server URLs under host `:4444`, each with an Authorization header | Same six ContextForge families. Local Serena entry is disabled. |
| Current noetic-dev/Pi session | runtime service status and successful calls during issues #6–#14 | inherits Pi attachments | GitHub/Projects, web research, Context7, mentality, browser services depend on the shared transport. The composition root itself has no `.project/context_forge_state.json`. |
| noetic-pi project state | `noetic-pi/.project/context_forge_state.json` | recorded project bindings, not current client-visible proof | Four records: Context7, GitHub, Playwright, web search. State says initialized, but drift is `unknown`; treat as historical/recorded evidence until revalidated. |
| ContextForge operator/test harness | `cf-controlplane/docker/contextforge-harness/compose.yml` and `SERVICE_LOCALITY.md` | isolated Docker gateway `:4445` and sidecars `:9201..:9209` | mentality, ssh-tmux, Context7, Playwright, Exa, GitHub, web search, time, and project Serena proxy. Never substitute host-live services for successor parity. |

`~/.pi/agent/mcp-cache.json` contains aliases beyond current `mcp.json`; it is cache evidence, not configuration authority. No cleanup is authorized from that observation.

## Service and locality inventory

| Service | Host unit/port | Current client evidence | Scope and failure impact |
|---|---|---|---|
| Gateway | `contextforge-gateway.service`, 4444 | Pi wrappers and OpenCode URLs | Shared single point for six configured families in both clients. Outage removes those attachments together. |
| mentality | `contextforge-mentality.service`, 9100 | Pi + OpenCode | Caller-supplied repository scope; governance ledger access fails if bridge/gateway fails. |
| Chrome DevTools | `contextforge-chrome-devtools.service`, 9101 | Pi + OpenCode | Isolated browser runtime; browser/debug tools fail independently at bridge level. |
| ssh-tmux | `contextforge-ssh-tmux.service`, 9102 | service/catalog evidence, not current Pi/OpenCode config | Session/remote-target scoped; hidden consumers cannot be excluded solely from current configs. |
| Context7 | `contextforge-context7.service`, 9103 | Pi + OpenCode + noetic-pi state | Shared documentation lookup. |
| Playwright | `contextforge-playwright.service`, 9104 | Pi + OpenCode + noetic-pi state | Session-scoped browser state; transport migration must preserve session affinity. |
| Exa search | `contextforge-exa-search.service`, 9105 | active catalog/service, not current Pi/OpenCode config | Credential-scoped; may support other consumers or web-search composition. Do not stop as “unused.” |
| GitHub | `contextforge-github.service`, 9106 | Pi + OpenCode + noetic-pi state; active requests | Credential/account scoped. Historical restart counter is 130, but service has remained active since July 8 and showed repeated HTTP 200 requests in the bounded journal window. Investigate; do not infer current failure. |
| web search | `contextforge-web-search.service`, 9107 | Pi + OpenCode + noetic-pi state | Provider-credential/request scoped. Credential-file permission finding below is blocking security follow-up. |
| Serena cf-controlplane | project unit, 9108 | operator repo/service evidence | Project-specific identity; not interchangeable with current Pi's direct cwd-scoped Serena. |

There are seven project-Serena unit files: six active/enabled and one inactive/disabled cognitive-disciplines unit. Project-scoped instances must not be collapsed into one shared identity merely to simplify the catalog.

## Authentication and credential boundaries

The Pi wrapper source (`cf-controlplane/scripts/contextforge_mcp_wrapper.py`) was inspected completely:

1. it reads the ignored gateway env and 0600 token cache;
2. resolves exactly one named virtual server;
3. uses a configured bearer or logs in through the local gateway;
4. normally creates an ephemeral server-scoped token with `servers.use`, tool read/execute, resource read, and prompt read;
5. forwards MCP with session ID handling; and
6. revokes the scoped token on process completion.

OpenCode stores Authorization headers per virtual-server entry; values were not printed or recorded. Backend credentials belong in ignored service-local env files.

### Security finding CF-001

`cf-controlplane/server-instances/web-search/.env` is ignored but mode **0664** and contains nonempty variables whose names indicate GitHub and provider credentials. Values were not read into evidence or printed. This is too permissive compared with the 0600 gateway, token-cache, and Exa env boundaries. Inventory scope forbids silently changing it; [contextforge-control-plane#394](https://github.com/somebloke1/contextforge-control-plane/issues/394) must correct permissions, verify service ownership/reload implications, and prove no exposure without rotating values implicitly.

## Additional operational findings

- **CF-002:** the operational `cf-controlplane` checkout (`b2eb799...`) is dirty, includes untracked source/runtime artifacts, and is one commit ahead of its tracked branch. Live services may therefore not be reproducible from remote HEAD. Do not clean or reset it; first capture provenance in its own governed work.
- **CF-003:** Pi cache aliases and noetic-pi `drift=unknown` make cleanup-by-name unsafe. Current client config plus live readback are authoritative.
- **CF-004:** GitHub's historical restart count needs bounded investigation, but current evidence is stable/HTTP 200. Do not mislabel it healthy forever or currently broken.
- **CF-005:** gateway-wide blast radius spans six configured service families in both Pi and OpenCode. The direct Serena exception does not provide substitutes for them.

## Continuity invariants

1. Do not stop, restart, disable, decommission, re-register, rotate credentials, rewrite client config, chmod credential files, or clean caches in inventory work.
2. Keep host-live `:4444` and development Docker `:4445` distinct; neither is silent fallback evidence for the other.
3. Preserve ContextForge as configured transport until each consumer/service edge has schema, auth, session, error, privacy, tool-policy, and rollback parity.
4. Preserve service locality: project, credential, user, session, filesystem, and hardware boundaries define identity more strongly than gateway convenience.
5. Never claim the issue #8 canonical-event ContextForge sink already exists. MCP virtual servers are not event-sink proof.
6. Treat ContextForge demotion as architectural responsibility separation, not operational removal.

## Migration/attachment gate

Any future replacement or new attachment must, one service/consumer edge per PR:

- inventory live and recorded consumers, including caches/project state and hidden service users;
- snapshot names, schemas, errors, auth scopes, session behavior, rate limits, redaction, and locality without secrets;
- run identical client-visible fixtures through old and candidate paths;
- prove no authority broadening, semantic rewrite, hidden fallback, or session loss;
- inject per-service and gateway-wide failure and verify bounded retries;
- provide a tested rollback restoring config, virtual-server identity, token boundary, and health;
- receive exactly one adversarial QA pass for its implementation generation.

Until those gates pass, ContextForge remains operational and maintained.

## Evidence sources

- `/home/dgk/.pi/agent/mcp.json` and sanitized live MCP status
- `/home/dgk/.config/opencode/opencode.json` (header names only; no values)
- `/home/dgk/.config/systemd/user/contextforge-*.service` and read-only `systemctl` status
- `/home/dgk/workspace/cf-controlplane/scripts/contextforge_mcp_wrapper.py`
- `/home/dgk/workspace/cf-controlplane/server-instances/*/instance.json`
- `/home/dgk/workspace/cf-controlplane/docs/pi-contextforge-integration-architecture.md`
- `/home/dgk/workspace/cf-controlplane/docker/contextforge-harness/SERVICE_LOCALITY.md`
- `/home/dgk/workspace/noetic-pi/.project/context_forge_state.json` (shape/status only)
- read-only socket, health, file-mode, Git state, container, and bounded journal observations recorded above
