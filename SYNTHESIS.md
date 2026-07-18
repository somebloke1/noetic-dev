# Synthesis: The Backbone for a Unified Development + Cognitive Framework

**Author:** synthesis agent (goal chain `chain-1`)
**Date:** 2026-07-11
**Status:** Recommendation, confidence 0.85 (raised from 0.78 after verifying organ extractability — `KNOWNS.md` k-20260711-0003; still conditioned on the client-scope open question, `OPEN_QUESTIONS.md` oq-20260711-0001)
**Evidence base:** `KNOWNS.md` (verified findings), `DECISIONS.md` (adjudications). Source-cited throughout.

---

## 0. The request, restated

You have run ~8 overlapping experiments for a year and want the *correct and practically-correct* backbone to integrate them into **one development and cognitive framework**. The key move in this document is to notice that "development **and** cognitive framework" names **two backbones**, not one — and that the synthesis is to join them *hylomorphically* (form + matter), not to crown a single winning repo.

- **The cognitive backbone is the FORM** — the invariant you already discovered: the Standard Model of Cognition (P1 Attentiveness → P2 Intelligence → P3 Reasonableness → P4 Responsibility, with P4 governing the whole recursively). This is your "periodic table for the alchemy."
- **The development backbone is the MATTER/SPINE** — the runnable thing that carries purpose across sessions and clients: **Telos** (portable goalchains) on the local-inference substrate.

Everything else is either an *organ* attached to that spine, a *substrate* beneath it, or *deprecated scaffolding*.

---

## 1. What each project actually is (verified)

Grounded from source on 2026-07-11 (full detail in `KNOWNS.md` k-20260711-0001/0002).

| Project | Real role | Maturity / recency | Verdict |
|---|---|---|---|
| **saeproj** | The cognitive theory (SMC) + model training to make the operational geometry explicit (GEH) | Theory ALIGNED; training intermittent; active 2026-06-28 | **FORM source** + long-horizon substrate R&D |
| **telos** | Runtime-pure goalchains; reproductive clause; MCP tools; **Pi + OpenCode** | 47 test files; active 2026-07-08; runs this chain | **SPINE** |
| **genus-router** | Deterministic MCP model-selection router; "designed for telos first" | **Most recent, 2026-07-10** | **Substrate: model selection** |
| **noetic-pi** | Self-developing agent OS: APM, mesh, disciplines, pipelines, orchestration, session search | **Most mature: 2,069 tests**; but coupled to `pi-mono`; export **stuck/deferred** | **Organ DONOR (harvest, don't host)** |
| noetic-pi-docker | Forward product instance of noetic-pi | active 2026-07-02 | Product deployment, not the reusable core |
| cognitive-disciplines | Codex plugin extraction of the P1–P4 cycle | active 2026-06-22 | Fold into shared discipline spec |
| cf-controlplane / ContextForge | MCP gateway aggregation | active 2026-06-25; "messy… not fruitful" (your words) | **Demote to optional transport** |
| cognitional_notation (ECN) | Formal A/I/R/D operator grammar | stale 2026-02 | Fold into one canonical notation |

**The load-bearing asymmetry:** noetic-pi is the most *capable* system but the least *movable* — its own manifest records that "control-plane extraction remain deferred," the public-export effort has been stuck since April with no merged/publishable basis, and `pnpm -r build` is blocked by its coupling to `pi-mono` (which must not be modified). Meanwhile telos is *built to be portable* and genus-router is *explicitly built to serve telos*. Your revealed center of gravity has already shifted to the portable axis.

---

## 2. The synthesis backbone

```
                    ┌─────────────────────────────────────────────┐
   FORM (grammar)   │  COGNITIVE BACKBONE — SMC / P1–P4 invariant  │
   the "periodic    │  one canonical notation; the design +        │
   table"           │  evaluation grammar for every layer          │
                    └───────────────────────┬─────────────────────┘
                                             │ conforms
   SPINE (purpose)  ┌───────────────────────▼─────────────────────┐
   teleological     │  TELOS — portable goalchains (P4 made        │
   governor         │  durable). runtime-pure core + MCP + Pi/OC   │
                    │  adapters. reproductive clause = evolution.  │
                    │  steers a host agent (or dispatcher) that…  │
                    └───────────────────────┬─────────────────────┘
                                   steers ▼  │  which enacts (MCP)
   ORGANS           ┌───────────────────────▼─────────────────────┐
   harvested from   │  DISCIPLINE + PIPELINE CAPABILITIES          │
   noetic-pi,       │  • cognitive cycles: phronesis / EP audit /  │
   re-exposed as    │    differentiated-cognition  (P1–P4 loops)   │
   MCP capabilities │  • design_intentions→design→impl_procedure→  │
                    │    implementation, w/ QA↔remediation cycles  │
                    │  • ordinal delegation-tree identity          │
                    │  • session embedding + summarization         │
                    └───────────────────────┬─────────────────────┘
                                             │ selects/serves
   SUBSTRATE        ┌───────────────────────▼─────────────────────┐
   models + compute │  genus-router (model selection)  +           │
                    │  saeproj-trained models  +                   │
                    │  local inference: 2×3090 (llama.cpp Qwen3.6- │
                    │  A3B+vision, ollama embed, Qwen3-ASR)        │
                    └───────────────────────┬─────────────────────┘
                                             │ transported by
   TRANSPORT        ┌───────────────────────▼─────────────────────┐
   (optional)       │  plain MCP stdio/HTTP by default;            │
                    │  ContextForge ONLY if a real multi-host      │
                    │  distribution need appears                   │
                    └─────────────────────────────────────────────┘
```

The five layers each map to a moment of the cognitional structure, which is why the architecture feels inevitable once named: **substrate** is the material of P1 (data/attention), **organs** are P2 (insight) and P3 (reflective QA/judgment), **spine/telos** is P4 (responsible purpose that governs the rest), and the **form** is the recursive whole `R(P1→P2→P3→P4→R)` that every layer must instantiate.

### Why telos is the spine (not noetic-pi)
- **Portable by construction** — runtime-pure `core`, thin Pi/OpenCode adapters, MCP tool surface. noetic-pi is welded to `pi-mono` and cannot currently be extracted.
- **Purpose-bearing** — a goalchain *is* P4 (responsibility/telos) made durable across sessions; the reproductive clause is the evolutionary mechanism. This is the layer that should govern.
- **Where you are already going** — genus-router (your newest work) declares telos its first consumer.

### How the spine actually "drives" (verified — k-20260711-0004)
A precise correction to avoid a false expectation: **Telos steers; it does not spawn.** Its drive mechanism is *continuation steering* — the pi-runtime `GoalContinuation` re-injects the host agent's loop when idle (Codex-style), and `core/continuation.ts` decides the next sub-goal and emits the continuation message. It governs *the agent it is embedded in* (this is literally what is steering this analysis). It has a first-class `delegations` schema and a `delegated-pending` status, but **no delegation dispatcher yet** — `delegate_context` is only a guard flag. So Telos-as-it-exists has no general outbound MCP-client/agent-dispatch capability.

This makes the picture *more* faithful to `P4 governs recursively`, not less: **Telos is P4 (the governor); the host agent — or a small delegation dispatcher you build — is the P1–P3 enactor that calls the MCP organs.** It also names the **one genuinely-new component the synthesis needs**: the delegation/dispatch enactment seam — which is exactly your already-stated intent to "make Telos multi-agent." Everything else in this plan is harvest and integration; this is the single real build.

### The executive plane: a deterministic orchestration controller (k-20260711-0007, dec-20260711-0008)

A correction worth making explicit, because it changes the shape: the APM is **not an optional sidekick** to the disciplines and pipeline tools. It is a near-deterministic **state machine** for multi-agent pipelines, and the disciplines and the design→implementation pipeline *run on it*. So the framework has **two distinct kinds of governance**, both necessary:

- **Teleological governance — Telos (P4):** *why*. Purpose, goalchains, evolution. It steers.
- **Executive / orchestration governance — the harvested APM state machine:** *how and when*. It deterministically sequences the multi-agent work. It controls.

The means of ordering multi-agent orchestration, verified from the APM source, is concretely: work decomposed into **work units grouped into numbered waves**; waves run **sequentially** (wave *N* runs → QA gate → commit boundary → advance to *N+1*); **typed `dependency_roles`** (`launch_required` vs `governing` vs `future_produced` vs `contextual`) enforce ordering *legality* so a unit can't launch against inputs that don't exist yet; **per-wave QA with remediation cycling** (0–3 passes, then escalation); and **ordinal delegation-tree identity** placing agents structurally. It's a sequenced-waves-plus-dependency-legality machine, not an arbitrary DAG scheduler — and it carries ~1,100 tests plus several hard-won "dependency-ontology" and "total-compliance" campaigns of hardening. **Harvest it; don't reinvent it.**

The load-bearing discipline it embodies (and that the framework must preserve): the **controller stays deterministic** (structural/harness mechanics — sequencing, gating, commits, spawn/retire), while **semantic judgment stays with the agents** (the P1–P4 cognitive work inside each unit). Never collapse the two.

That gives the real execution layering:

```
  Telos (teleology, P4)                     — why: goals, evolution
    ↓ delegation dispatcher (the new seam)
  Deterministic orchestration controller     — how/when: waves, dependency
    (harvested APM)                              legality, QA gates, commits,
    ↓ spawn/retire by ordinal                    model selection (via genus-router)
  Agents doing P1–P4 cognitive work         — the non-deterministic work
    ↓ emit cognitional events
  Observability + control plane              — watch it all happen
```

So what I earlier called "two organs" (disciplines, pipeline) are better understood as **programs that run on one executive organ**: the pipeline is a particular wave program; a discipline (phronesis / EP-audit / differentiated-cognition) is a P1–P4 loop the same controller dispatches. The orchestration controller is therefore the **single most valuable harvest** in the whole plan.

### The interface: an observability + control plane, not a terminal multiplexer (k-20260711-0005, dec-20260711-0004)

You like noetic-pi's web paradigm but are unsure about embedding PTY terminals in a browser, and you want a client that is minimalistic, highly capable, portable, and the best *medium for expressing this design*. These pull against each other only if the interface and the client stay fused, the way noetic-pi fuses them today. They don't have to.

noetic-pi's own web package already separates the two concerns in code: `terminal.ts` is the xterm/PTY embedding (the part you're unsure about), while `observability.ts`, the inquiry panels, and the `sidebar-*-section` files are **event- and archive-driven** — they render planning, implementation, differentiated-cognition, emergent-probability, census, and backend state from structured `/observability/...` endpoints and SSE, **not** terminal byte streams. The thing you value is the event-driven observability; the terminal is incidental to it.

So the move is:

- **Elevate the web interface to a portable observability + control plane** that consumes a structured **cognitional-event stream** (P1–P4 operation traces, agent census, discipline-cycle state, pipeline phase/QA state) from the spine (Telos) and the harvested organs. Because it consumes events, it is **client-agnostic**.
- **Demote the PTY-terminal multiplexer** to an optional "attach a terminal" view, not the core abstraction.
- **The client becomes a reversible choice, not the backbone.** Portability and the web paradigm now coexist: swap the runtime underneath without losing the interface.

**Attaching to live agents is a separate, swappable layer — and you already have the minimalist version of it.** Your `pi2` project multi-panes agents through a project-scoped **tmux** server (each agent is a pane; succession opens the successor in an adjacent pane), which is the same agent-population/disciplines family as noetic-pi but terminal-native and browser-free (k-20260711-0006). That gives a clean three-layer interface stack (dec-20260711-0006):

1. **Observability + control plane** — the durable value, event-driven, renders to *either* a web view *or* a TUI. Build once against the event stream.
2. **Attach / live-visibility** — how you actually watch or enter a running agent, and it's swappable: **tmux multi-paning (from `pi2`) is the recommended default** because it matches your "minimalistic, terminal-native" instinct, works over ssh, and you already have it working; the **browser PTY multiplexer (from noetic-pi)** stays optional for when a browser is already your surface.
3. **Client/runtime** — reversible, as above.

This fully dissolves the browser-vs-terminal question: it's a rendering/attach choice under one event-driven plane, not an architecture fork. `pi2` thus becomes a **third harvest donor** (tmux multi-paning + its PHAF disciplines) alongside noetic-pi and Telos. One caveat carried from `pi2`'s own experience: tmux has a ~16KB spawn-command limit, so use its minimal-bootstrap pattern (spawn a tiny identity, deliver the full curriculum via an APM response) rather than pushing large prompts through the tmux command.

The deeper point about your "best medium for expressing this design" criterion: **the medium of expression is the observability + control plane itself** — the surface where the cognitional operations become *visible* as they happen — not the terminal and not any single CLI. That is the untapped observability potential you're sensing. The terminal is skeuomorphic; watching cognition unfold is the real thing.

This adds a second small new component alongside the delegation dispatcher: a **cognitional-event schema** — the plane's input contract, which doubles as the P1–P4 event vocabulary the whole framework emits. noetic-pi's typed event vocabulary and observability endpoints are the donor for it.

**Client, once decoupled** — criteria become: MCP-native, extensible (can host Telos and emit the event stream), minimalistic, and headless-capable (so the plane observes it rather than *being* it). Default lean: **OpenCode** as the portable reference runtime (open, extensible, Telos already runs in it, not `pi-mono`-locked); keep **Pi** as the rich instance you harvest from; watch **Goose** as an MCP-native minimalist alternative. This is now a low-stakes, hands-on decision you can defer without blocking the architecture.

### Why noetic-pi is an organ donor (not the spine)
It is the richest proven mechanism library you have, and it should not be rewritten from scratch. But its value must be *harvested* — re-expressed as portable capabilities the telos spine can call over MCP — rather than kept trapped inside the locked, `pi-mono`-coupled instance. Do **not** stake the synthesis on finally unlocking its export; that is a blind alley by its own record.

**Harvest is verified feasible** (k-20260711-0003), not aspirational: the APM daemon that carries the disciplines and the pipeline depends only on shared types + `better-sqlite3` + `node-pty` — **no `pi-mono`, no pi SDK** — and already talks over a TCP/IPC seam. The `pi-mono` coupling that blocks noetic-pi's build lives at the web-terminal/app layer (hosting pi agents in PTYs), not in the logic worth harvesting. Re-exposing that logic (with its ~1,100 APM tests) as an MCP service is integration work behind an existing clean boundary, not a rewrite.

---

## 3. Practical migration path (survivable, incremental)

The ordering follows the scheme of recurrence: **keep a stable base durable, treat blocked mass as recyclable, never block the spine on an unlockable dependency.**

This section records the architectural migration rationale. The canonical current
checkpoint, aggregate dependency order, unresolved governance conflicts, and
measurable exit gates live in [`ROADMAP.md`](ROADMAP.md). Where historical sequence
or status prose here conflicts with that roadmap or a later accepted decision, the
conflict must be reconciled explicitly rather than inferred away.

1. **Canonicalize the notation (form first).** *Drafted* — see `docs/cognitive-backbone.md`, which reconciles the four scattered notations into one crosswalk and recommends `P1–P4` as canonical (it is already what noetic-pi's roles and the cognitive-disciplines plugin use), with the imperative gloss for prose and ECN's `^!`/`^?` markers kept only as optional modality annotation. Only your P4 ratification remains; every other project then references that one file instead of re-deriving. Low cost, high entropy reduction.
2. **Confirm the spine, and build its one missing seam.** Adopt telos as the governance/orchestration entrypoint (its goalchain tools already work in Pi and OpenCode — that is your cross-client backbone). Then build the **delegation dispatcher**: the enactment seam that turns a `delegated-pending` sub-goal into an actual dispatched unit of work against an MCP organ. Telos already has the `delegations`/`delegation_events` schema and the guard semantics; what is missing is the dispatcher that enacts them. This is the *only* genuinely-new component in the whole synthesis (and it is your stated "make Telos multi-agent" intent), so treat it as the critical build (k-20260711-0004).
3. **Wire the substrate — access and selection at their own layers.** Make genus-router the single model-*selection* MCP for telos-driven work, and ratify **LiteLLM as the single model-*access*/normalization body** beneath it (you've already de facto done this — genus-router routes all 13 models through one `local-litellm` endpoint). Keep them distinct: LiteLLM normalizes provider access (one maintenance surface), genus-router chooses *which* model per task genus. Preserve genus-router's "LiteLLM is one endpoint, not the boundary" principle so a direct llama.cpp/ollama endpoint stays registerable — and consider keeping latency-sensitive **embeddings/ASR direct** rather than proxied, as a measured config choice (dec-20260711-0005). Register the 2×3090 endpoints and finish this.
4. **Harvest organ #1 — the disciplines.** Extract the phronesis / EP-audit / differentiated-cognition *contracts* (their packet templates, gates, recursion rules) from noetic-pi and cognitive-disciplines into one MCP-exposed "cognitive disciplines" service the spine can invoke. This retires the standalone cognitive-disciplines plugin's need to exist separately.
5. **Harvest organ #2 — the pipeline.** Re-express the `design_intentions→design→implementation_procedure→implementation` pipeline with QA↔remediation as a portable capability (its logic is already proven and heavily tested in noetic-pi's APM).
6. **Substrate R&D on its own clock.** saeproj (SMC training) stays a research track that *improves the models under the substrate*; it does not gate the framework. Its payoff is models that natively perform the operations the framework already scaffolds.
7. **Demote transport.** Default to plain MCP; keep ContextForge only if/when a real multi-host distribution need is demonstrated.

Each step leaves a runnable, more-integrated system; none requires the noetic-pi export to close.

---

## 4. What to deprecate or fold in

- **cognitional_notation (ECN):** stale; promote its *grammar idea* into the single canonical notation, retire it as a live project.
- **cognitive-disciplines (Codex plugin):** its content becomes the harvested MCP disciplines service; keep a Codex adapter only if Codex remains a first-class client (see open question).
- **cf-controlplane / ContextForge:** demote to optional transport; stop treating it as an integration backbone.
- **noetic-pi export saga:** stop trying to make the whole instance portable; harvest mechanisms instead.
- **noetic-pi web app:** split it — *keep and elevate* the observability + control plane (event-driven, portable); *demote* the PTY-terminal multiplexer (`terminal.ts`) to an optional attach-view. Don't preserve or discard the web app as a whole; preserve the observability, drop the terminal-as-core-abstraction (dec-20260711-0004).

---

## 4b. The target project: `synthesis` as a thin composition root (dec-20260711-0007)

A question worth making crystal clear: **where does the harvested material actually become the synthetic form?** The answer is *this* workspace — but with a promotion and a discipline.

**Promote `synthesis` from a deliberation record to the composition root** — the integration home where the parts are bound into a running whole. It already holds the form spec (`docs/cognitive-backbone.md`) and the governing decisions; those become the specs and governance *of the composition root*, exactly the way your other repos carry their own `DECISIONS.md`/`OPEN_QUESTIONS.md`.

**The discipline: it composes components; it does not absorb them.** This is harvest-not-host applied to the target itself. Keep three roles distinct:

1. **Deliberation / governance record** — the ledgers and this document. (What `synthesis` is today.)
2. **Composition root / integration home** — the canonical form spec, the event-schema contract, the config that wires spine + organs + substrate, the run/deploy composition. **This is the target project.**
3. **Component homes** — where each capability lives and evolves independently: Telos in the Telos repo; the disciplines/pipeline MCP services as new packages derived from noetic-pi's `apm`; the tmux attach from `pi2`. The root *references* these (submodule or package dep); it does not copy their code in.

**Where each new or harvested piece lives** (the concrete answer to "where do we bring what is harvested into the synthetic form"):

| Piece | Home | Origin |
|---|---|---|
| Delegation dispatcher | **Telos repo** | new (the spine's own capability) |
| Cognitional-event schema (P1–P4 vocabulary) | **synthesis root** `spec/` | new connective tissue |
| Observability + control plane | **synthesis root** (or a package it owns) | new; donor = noetic-pi endpoints/event vocab |
| Disciplines MCP service | new component/package | harvested from noetic-pi `packages/apm` |
| Pipeline MCP service | new component/package | harvested from noetic-pi `packages/apm` |
| tmux multi-paning attach | component/adapter | harvested from `pi2` |
| Model selection + access + local inference | **synthesis root** `config/` | genus-router + LiteLLM + 2×3090 |

**Proposed shape of the composition root:** `docs/` (form spec + this architecture), the governance ledgers, `spec/` (the cognitional-event schema), `config/` (endpoint registry, genus-router binding, LiteLLM, local endpoints), `compose/` (how spine + organs + planes run together), and component references.

**Two practical consequences:** (a) `git init` this workspace — it isn't versioned yet, and a composition root must be; (b) the framework may want its own **name** — "synthesis" names the *act*, not the *thing* — your call. And as you did with noetic-pi vs noetic-pi-docker, keep the *basis* (this integration root) distinct from the *composed running framework* (the product).

**Why thin rather than a swallowing monorepo:** it preserves each component's portability (Telos stays Pi+OpenCode-portable; the organs stay independently testable with their donor test suites) and avoids re-creating noetic-pi's `pi-mono` entanglement in a new location. The composition root is durable; the components hanging off it stay recyclable.

## 5. The deepest point (why this is *your* framework, not a generic one)

Your own `on_emergent_fidelity` thesis says alignment begins with **self-appropriation of the operations of knowing** — "interior alignment is the hidden ground of technical work." The framework therefore should not merely *orchestrate* agents; it should **embody the cognitional operations authentically at every level**: agent behavior (P1–P4 in a turn), pipeline phases (attend→understand→judge→decide), evaluation gates (structural checks vs. semantic judgment kept distinct), and even model training (saeproj making the operations explicit in representation space). The backbone above is the minimal skeleton on which that self-similar embodiment can grow — the same form (`R(P1→P2→P3→P4→R)`) recurring at each scale.

---

## 6. Open questions blocking full confidence

1. **Client scope** (oq-20260711-0001): which coding assistants are first-class? "Any MCP client" firmly confirms the telos spine + harvest-not-host path; "Pi only" would license using noetic-pi's mechanisms in place. **Default assumed: any MCP client.**
2. **Notation choice:** A/I/R/D vs P1–P4 — a decision you should make, not one to leave plural.
3. **saeproj coupling:** is trained-model substrate a near-term dependency or a long-horizon research bet? (Recommend: long-horizon; do not gate the framework on it.)

---

*This document is the P4 deliverable of the synthesis goal chain. Findings that ground it are in `KNOWNS.md`; the adjudication is `DECISIONS.md` dec-20260711-0002; unresolved issues are in `OPEN_QUESTIONS.md`.*
