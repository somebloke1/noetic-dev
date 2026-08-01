# Project-local OpenCode roles

This directory adds only two roles that close recurring noetic-dev capability
and permission gaps. It does not create architectural authority; repository
authority remains in `AGENTS.md`, `SYNTHESIS.md`, the ledgers, specifications,
issues, and protected Git/GitHub evidence.

## Roles

| Role | Use | Why it exists | Effective boundary |
|---|---|---|---|
| `noetic-tracer` | P1 evidence, provenance, authority, and cross-component architecture tracing before design or judgment | The built-in explorer has broad shell access and does not encode noetic-dev's observation/judgment separation | Read tool only, including explicitly allowed `~/workspace` roots; no search, shell, edits, delegation, skills, web/browser, MCP resources/mutation, or model-initiated state mutation |
| `noetic-qa` | The one independent adversarial QA pass for an exact frozen implementation generation | Generic agents retain write/delegation capabilities, while `AGENTS.md` requires exact 1:1 implementation:QA pairing | Repository read tool only; no search, shell, edits, external project paths, delegation, skills, browser/remote/MCP access, Git promotion, or model-initiated state mutation |

Use the normal primary `build` agent for implementation, debugging, and
documentation changes. Do not use either specialized role for release or
promotion; follow `docs/development-practices.md` and protected GitHub policy.
No project skill or command is added: the primary workflow already lives in
`AGENTS.md` and `docs/development-practices.md`, while repository validation is
already one direct command.

## Model handoff

The agent files intentionally contain no `model` or `variant`. Their model
handoff contract is `classify -> route_task -> validate -> invoke through
LiteLLM -> report_outcome`. The caller must pass the routing decision ID, exact
model and variant, and named outcome-reporting controller into the invocation.
Both agents stop when that evidence is absent, and their final handoff gives the
controller the evidence needed to call `report_outcome`. An inherited or fallback
model without that evidence is a failed handoff, not an accepted default. A
different model family does not by itself prove reviewer independence or
coverage.

## Pairing and handoff

For each implementation generation:

1. the external controller freezes and authenticates an exact commit or staged
   index tree, then supplies its 40-lowercase-hex identity, base, complete patch
   or changed contents and manifest, claim, acceptance criteria, independently
   captured deterministic test evidence, intended paths, and unrelated state;
2. it starts exactly one `noetic-qa` session with routing, model/variant, and
   outcome-owner evidence;
3. `DERIVED RED` returns control to the primary agent for repair;
4. the primary freezes the successor snapshot and resumes the same reviewer
   session until a non-empty `DERIVED GREEN` or terminal `DERIVED RED` result;
5. the named controller calls genus-router `report_outcome` from the terminal
   handoff;
6. no role here approves, publishes, or merges the change.

Use `noetic-tracer` before P2/P3 when source authority or cross-component
behavior is unclear. Its questions hand off to the primary agent; its output is
not an architecture decision or QA result.

## Permission limits

OpenCode permissions are last-matching lexical gates on tool-call resources,
not an OS, process, filesystem, container, or network sandbox. OpenCode 1.18.11
derives shell permission checks from parsed command nodes, so command allowlists
cannot safely exclude redirection-only writes. Both roles therefore expose only
the read tool. They deny the tool-output directory itself and its contents after
the broad read allowance; this compensates for OpenCode's later external-directory
traversal allowance. They also deny `mcp:*` resources and secret files.

The read-only claim describes the model tool surface, not OpenCode startup. On a
writable checkout, OpenCode creates ignored `.opencode` dependency support before
an agent runs. Invoke these roles in a disposable overlay/worktree when source
immutability is required. Snapshot authentication and deterministic execution
belong to the external controller; the reviewer rejects missing evidence instead
of claiming it independently froze Git or ran tests.

Neither role has a temporary-fixture write exception. This keeps the model tool
surface mutation-free and avoids path rules that change depth between the root
checkout and sibling worktrees. If a future recurring probe truly needs a
fixture, add one fixed path only after validating its actual worktree-relative
permission resource from both layouts.

## Discovery and restart

These files were revalidated for OpenCode `1.18.11`. First run repository validation
in the source worktree:

```text
python3 scripts/validate_repo.py
```

Then validate discovery from a fresh disposable copy or overlay of the exact
snapshot, because OpenCode writes ignored dependency support under `.opencode`:

```text
opencode agent list
opencode debug agent noetic-tracer
opencode debug agent noetic-qa
opencode debug skill
```

Also start OpenCode outside this repository and confirm both roles are absent.
Do not assume malformed frontmatter fails closed: OpenCode 1.18.11 can discover
an invalid agent file with broad default tools. Treat any unexpected resolved
mode, prompt, or tool as a validation failure; inspect the effective agent, not
only the Markdown/YAML text.
OpenCode loads agents, skills, commands, plugins, and config at startup; quit and
restart OpenCode before expecting changed definitions to become active.
