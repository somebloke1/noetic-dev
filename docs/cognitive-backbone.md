# The Cognitive Backbone — Canonical Notation Reference

**Status:** Accepted canonical form, ratified by the user on 2026-08-02 and recorded in `DECISIONS.md` as `dec-20260802-0001`.
**Scope:** This is the **form** layer of the synthesis. It is invariant across client, runtime, model, transport, and component choices; acceptance of the form does not establish implementation readiness.
**Primary sources:** Lonergan, *Insight*; `saeproj/docs/foundational/transcendental-method-structured.txt`; `saeproj/docs/foundational/on_emergent_fidelity.txt`; `saeproj/docs/foundational/the-notion-of-judgment.txt`; `saeproj/docs/foundational/theoretical_foundations.md`; `saeproj/docs/foundational/self_appropriation.md`; `cognitional_notation/FOUNDATION.md`.

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

- **P4 governs recursively:** `R(P1 → P2 → P3 → P4 → R)`. Responsibility is not merely the last step; it governs and integrates the whole cycle (*on_emergent_fidelity*). At the framework governance boundary, responsibility remains irreducibly human. Agents may contribute attributed judgments and recommendations, while Telos mediates durable humanly authorized purpose and continuation without becoming P4 or the responsible subject.
- **Intussusception:** each operation transforms its predecessors — attention becomes *intelligent* attention, then *reflective* attention, then *responsible/creative* attention. The levels are distinct but not separable; later levels presuppose and complement earlier ones (Lonergan: "later steps presuppose earlier contributions and add to them").
- **No component-to-level equivalence:** P1–P4 names authentic operations, not deterministic states, agent roles, software layers, or components. Every genuinely cognitive activity is evaluated against the whole recurrent form. A controller may establish structural legality, but deterministic transition is not cognition; Telos may preserve purpose, but stored purpose is not responsibility.

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

## 3. Canonical decision: `P1–P4`, with a fixed gloss and an optional modal annotation

**Accepted default: the `P1–P4` level notation** as the canonical, machine- and structure-facing form, for four reasons:

1. **Already load-bearing in your operational code.** noetic-pi already uses `p1`–`p4` as functional agent roles, and cognitive-disciplines is built as a "P1–P4 cognitive cycle." Adopting P1–P4 canonically ratifies what your most-used code already does — zero migration for the biggest surfaces.
2. **Language-neutral and identifier-safe.** `p1`…`p4` are stable identifiers for pipeline phases, gate names, agent roles, log tags, and ledger sections. The ECN letters are English-specific (`A/I/R/D`) and `R` collides with the recursion operator `R(...)`; the verbs and imperatives are English-bound and verbose.
3. **Orderable and composable.** The numeric order encodes the presuppositional structure directly (P3 presupposes P2 presupposes P1); ranges and transitions (`P2→P3`) read naturally.
4. **Neutral about content.** It names the *operation*, not a particular English word for it, which suits a "periodic table" meant to be universal.

**Fixed human-facing gloss (always pair the code with the imperative):** `P1 be attentive · P2 be intelligent · P3 be reasonable · P4 be responsible`. Use the gloss in prose and prompts; use the code in identifiers and structure.

**ECN folds in as an optional modality annotation, not a rival notation.** ECN's genuinely additive idea is its *operator markers* — `^!` (assertoric/enacted) vs `^?` (interrogative/sought). Retain these as an *optional* annotation on a level when modality matters (e.g., `P3^?` = a judgment being sought / under reflection; `P4^!` = a decision enacted). This preserves the expressive power of `cognitional_notation` without keeping a second full notation alive.

**What this retires:** `cognitional_notation` as a standalone project (its grammar idea survives as the P-level + optional modal markers), and the ad-hoc plurality of glosses. The Lonergan verbs and the AGENTS.md activity phrases remain valid *descriptions*, but they are no longer separate notations — they are rows in the crosswalk above.

---

## 4. How to use the backbone as a conformance inquiry

The form is the evaluation grammar at every scale, not a label assignment. These are conformance questions and research hypotheses, not claims that a software sequence, artifact, role, or component performs a P-level:

- **Agent activity:** ask whether the evidence shows differentiated attention, inquiry and insight, critical reflection, and action under humanly authorized purpose. A turn sequence or P-level label is not evidence that those operations occurred.
- **Development programs:** use design intentions, designs, procedures, implementations, QA findings, and remediation as attributed evidence products. Artifact names do not make the artifacts P-levels, and structural progression does not establish cognition.
- **Cognitive disciplines:** treat a claimed P1–P4 cycle as a semantic claim requiring evidence for each differentiated operation. Packet completeness establishes inspectability, not authenticity.
- **Evaluation gates:** keep deterministic structural checks distinct from attributed semantic assessment. Agents and models may propose judgments; their output is not thereby P3 truth or P4 responsibility, and meaning must not be evaluated with regex.
- **Governance ledgers:** use `knowns`, `decisions`, and `open-questions` to preserve activity and authority distinctions. Ledger placement supports disciplined inquiry but does not prove that an authentic operation occurred.
- **Model training (saeproj):** GEH investigates whether operational geometry can be identified and made explicit in representation space. It remains a falsifiable research hypothesis, not evidence that a model performs the operations or possesses responsibility.

---

## 5. Ratification and amendment

The user completed the P4 ratification on 2026-08-02. `P1–P4` with the imperative gloss and optional ECN `^!`/`^?` markers is the canonical notation for noetic-dev.

This file is the cross-project notation reference. A future amendment requires explicit human authority, a recorded decision, and evidence that the revised form preserves the differentiated operations and their recurrent relation.

Ratification establishes the form and its authority boundary. It does not claim that an agent, Telos, a deterministic controller, an event trace, or any current component performs authentic cognition or human responsibility.
