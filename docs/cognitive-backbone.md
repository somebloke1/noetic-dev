# The Cognitive Backbone — Canonical Notation Reference

**Status:** Draft for user ratification (resolves migration step 1 of `SYNTHESIS.md`; answers part of `OPEN_QUESTIONS.md` oq notation choice).
**Scope:** This is the **form** layer of the synthesis. It is invariant across every client-scope and architecture decision, so it is safe to fix now, independently of the open questions.
**Primary sources:** Lonergan, *Insight* (`saeproj/docs/foundational/the-notion-of-judgment.txt`, `transcendental-method-structured.txt`); `on_emergent_fidelity.txt`; `theoretical_foundations.md`; `cognitional_notation/FOUNDATION.md`.

---

## 1. What the backbone is

The **transcendental method**: a *normative pattern of recurrent and related operations yielding cumulative and progressive results* (Lonergan). It is not categorial to any field; it is the structure of intelligent operation as such — which is why it can be the single grammar under a *cognitive* framework and the single evaluation rubric for a *development* framework at once.

Four levels, named by the principal operation on each:

| | Operation (Lonergan verb) | Imperative (human gloss) | The question it answers | What it produces |
|---|---|---|---|---|
| **P1** | experiencing / attending | *Be attentive* | (pre-question: attend to the data) | data, presentations |
| **P2** | understanding | *Be intelligent* | **What? Why? How often?** (questions for intelligence) | insight, intelligible form, formulation |
| **P3** | judging | *Be reasonable* | **Is it so?** (question for reflection; yes/no) | judgment — a verified/affirmed truth, a personal commitment |
| **P4** | deciding | *Be responsible* | **What shall I do?** (question for deliberation) | decision, responsible action, value |

Two structural facts that the framework must honor:

- **P4 governs recursively:** `R(P1 → P2 → P3 → P4 → R)`. Responsibility is not merely the last step; it governs and integrates the whole cycle (*on_emergent_fidelity*). This is why **Telos (P4/purpose) is the spine that governs the operational organs (P1–P3)** — the architecture mirrors the form.
- **Intussusception:** each operation transforms its predecessors — attention becomes *intelligent* attention, then *reflective* attention, then *responsible/creative* attention. The levels are distinct but not separable; later levels presuppose and complement earlier ones (Lonergan: "later steps presuppose earlier contributions and add to them").

---

## 2. The notational plurality problem

The same four operations are currently written four different ways across your projects. This is real entropy: a reader (or an agent) must re-derive the mapping every time.

| Canonical | Lonergan verb | ECN operator (`cognitional_notation`) | Imperative (`on_emergent_fidelity`) | AGENTS.md activity separation | noetic-pi functional role |
|---|---|---|---|---|---|
| **P1** | experiencing | `𝔸` Attend | be attentive | data gathering / research | `p1` |
| **P2** | understanding | `𝕀` Intelligize | be intelligent | fecund idea formation | `p2` |
| **P3** | judging | `ℝ` Reason | be reasonable | selective critical reflection | `p3` |
| **P4** | deciding | `𝔻` Decide | be responsible | deliberation & practical responsibility | `p4` |

They are the same structure. The synthesis needs **one** primary notation that everything else maps to.

---

## 3. Recommendation: `P1–P4` as canonical, with a fixed gloss and an optional modal annotation

**Recommended default: the `P1–P4` level notation** as the canonical, machine- and structure-facing form, for four reasons:

1. **Already load-bearing in your operational code.** noetic-pi already uses `p1`–`p4` as functional agent roles, and cognitive-disciplines is built as a "P1–P4 cognitive cycle." Adopting P1–P4 canonically ratifies what your most-used code already does — zero migration for the biggest surfaces.
2. **Language-neutral and identifier-safe.** `p1`…`p4` are stable identifiers for pipeline phases, gate names, agent roles, log tags, and ledger sections. The ECN letters are English-specific (`A/I/R/D`) and `R` collides with the recursion operator `R(...)`; the verbs and imperatives are English-bound and verbose.
3. **Orderable and composable.** The numeric order encodes the presuppositional structure directly (P3 presupposes P2 presupposes P1); ranges and transitions (`P2→P3`) read naturally.
4. **Neutral about content.** It names the *operation*, not a particular English word for it, which suits a "periodic table" meant to be universal.

**Fixed human-facing gloss (always pair the code with the imperative):** `P1 be attentive · P2 be intelligent · P3 be reasonable · P4 be responsible`. Use the gloss in prose and prompts; use the code in identifiers and structure.

**ECN folds in as an optional modality annotation, not a rival notation.** ECN's genuinely additive idea is its *operator markers* — `^!` (assertoric/enacted) vs `^?` (interrogative/sought). Retain these as an *optional* annotation on a level when modality matters (e.g., `P3^?` = a judgment being sought / under reflection; `P4^!` = a decision enacted). This preserves the expressive power of `cognitional_notation` without keeping a second full notation alive.

**What this retires:** `cognitional_notation` as a standalone project (its grammar idea survives as the P-level + optional modal markers), and the ad-hoc plurality of glosses. The Lonergan verbs and the AGENTS.md activity phrases remain valid *descriptions*, but they are no longer separate notations — they are rows in the crosswalk above.

---

## 4. How each layer of the framework instantiates the backbone

The form recurs at every scale (this is the embodiment principle from the reproductive clause):

- **A single agent turn:** attend to context (P1) → form an approach (P2) → check it against evidence (P3) → act/commit (P4).
- **The development pipeline:** `design_intentions` (P1–P2) → `design` (P2) → `implementation_procedure` (P2–P3) → `implementation` with QA↔remediation (P3), all under the goal's purpose (P4).
- **The disciplines:** phronesis / EP-audit / differentiated-cognition are P1–P4 loops applied reflectively to the work itself.
- **Evaluation gates:** keep *structural* checks (deterministic) distinct from *semantic* judgment (P3, requires model/agent judgment) — never evaluate meaning with regex.
- **The governance ledgers:** `knowns` = P1/P2 (verified data/insight); `decisions` = P3/P4 (judgment/commitment); `open-questions` = live P3 questions for reflection not yet answered.
- **Model training (saeproj):** make the operational geometry of P1–P4 explicit in representation space (GEH).

---

## 5. The irreducible decision left to you

Everything above is P1–P3 groundwork. The remaining act is P4 — yours to make:

- **Ratify or amend** the recommended default (`P1–P4` canonical + imperative gloss + optional ECN `^!`/`^?` modal markers). If you prefer the ECN letters or the verbs as the primary surface, say so and this reference flips; the crosswalk stays the same.

Once ratified, this file becomes the single source every other project references instead of re-deriving its own notation.
