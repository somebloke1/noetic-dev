# Cognitive program contract

**Issue:** [#11](https://github.com/somebloke1/noetic-dev/issues/11)

**Status:** M0 executable contract; no model call, controller command, file change, or other runtime effect is authorized.

## Governing rule

**Programs propose; the controller disposes.** A cognitive program is a portable, versioned declaration compiled to `controller.program/v0`. It can emit attributed reports, submit artifacts, request an interaction, or propose remediation. It has no effect authority and cannot enact controller transitions, amend its own graph, choose an endpoint, or expand Telos scope.

Telos owns objective, principles, acceptance, cancellation, and delegation. The controller owns structural validity, authority, scheduling, state transitions, retries, leases, and publication. Genus-router selects from a capability request; LiteLLM/direct adapters invoke the selected endpoint. Programs own only cognitive role semantics and artifact/report production.

## Canonical form and boundaries

Every program declares the recurring form:

- **P1 attend:** purpose-bounded data and questions; no judgment.
- **P2 understand:** hypotheses or intelligible formulations; no assertion of truth.
- **P3 judge:** evidence-conditioned judgment by a critic/QA role; evidence provenance is mandatory.
- **P4 decide:** decision or responsible proposal grounded in a P3 judgment. P4 governs the complete cycle through its Telos binding, but does not erase phase distinctions.

Data, hypothesis, evidence, judgment, decision, artifact, QA finding, and remediation proposal are typed boundaries. A later phase can transform earlier materials but cannot silently relabel them. Canonical events are minimal attributed reports (`noetic.event/v0`); an agent's P3/P4 report is never itself controller-enacted domain truth.

## Portable manifest

`program-manifest.schema.json` pins:

- semantic program ID/version and immutable controller graph digest;
- Telos delegation, goal, objective digest, and reproductive-clause version;
- phase, operation, role, typed input/output, and event classes for every stage;
- model **capability request** and policy class, never provider, model, URL, credential, or endpoint ownership;
- propose-only allowed intents and zero stage effect authority;
- evidence-before-judgment and judgment-before-decision rules;
- bounded stage attempts, bounded remediation, and interaction on exhaustion;
- reference-only secrets and minimal attributed reports.

## Verification and remediation

Every implementation generation has exactly one independent QA stage: `1:1_per_generation`. The QA role cannot implement; the implementer cannot self-certify. A finding may produce a remediation proposal, but only the controller can admit and schedule a remediation generation. Remediation is bounded to five generations and stage attempts to ten; exhaustion requests controller interaction rather than looping or self-amending.

## Standard programs

- `phronesis.cycle` is a reflective P1→P4 discipline, preserving distinct fresh attention, insight, critical judgment, and responsible proposal.
- `development.verified-change` extends that form with implementation, independent QA, and remediation proposal stages. The controller's typed DAG and barrier policy remain authoritative.
- Differentiated cognition and emergent-probability audits should become additional manifests or reusable stage templates, not framework-specific orchestrators.

## Harvested lessons

Donor phronesis preserves phase prompts, progression, fresh/accumulated context, grounding acknowledgement, and lifecycle tests. The superior contract retains those semantic stages while removing database, tmux, pi extension, and APM state-machine coupling. Donor implementation procedures preserve structured dependencies and QA/remediation; noetic-dev keeps their deterministic invariants while rejecting free-form self-authorization and unbounded rework.

Programs remain content-portable data. Runtime implementations must prove compilation parity, event conformance, capability-only model routing, privacy, and the exactly-one QA invariant before execution is enabled.
