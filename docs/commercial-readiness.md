# Commercial Readiness

Documentation baseline: 2026-09-07. Target: a local-first application for
professional developers, with customer-controlled model access. Sell workflow
execution, review evidence, continuity, installation and support, not pooled
access to another vendor's subscription. This is a proposed commercial boundary,
not legal clearance, a production acceptance verdict or authorization to sell.

## Distribution Boundary

[Noetic's current license](../LICENSE.md) remains unchanged: no open-source
license selected; all rights reserved subject to applicable law or explicit
written authorization. This document grants no customer usage rights.

| Component | Current private delivery / dependency boundary |
| --- | --- |
| Noetic Python application | Wheel with local browser assets, pattern JSON and `telos_bridge.mjs`. The research baseline was 0.2.0; current [package metadata](../pyproject.toml) declares 0.3.0, Python >=3.10 and no Python runtime dependencies. Setuptools is build tooling. A wheel contains readable code, not a secrecy mechanism. |
| Genuine Telos core | Separately supplied `telos-core.mjs` and manifest, built from the actual Telos factory. Include the exact [Telos MIT notice](THIRD_PARTY_NOTICES.txt). Noetic's reservation of rights does not remove upstream MIT rights. |
| Python / Node | Customer-installed runtime prerequisites, not bundled: Python >=3.10 plus venv/pip for installation; Node 24 with `node:sqlite` for Telos. No runtime redistribution rights or complete runtime notice inventory are asserted. |
| Build tooling | `setuptools>=68` builds the wheel; external esbuild builds the Telos module. tsx is used only for donor TypeScript execution, not installed module mode. These are not application runtime dependencies or components supplied by the release manifest. |
| Pi / OpenCode | Customer-installed external clients, not redistributed in this delivery. Earlier research records Pi 0.85.1 metadata as MIT and OpenCode upstream as MIT, not verification of the installed OpenCode binary's provenance. These labels do not establish a complete notice inventory for a future bundled client. |
| LiteLLM | Optional customer-operated gateway, not a shipped proxy package or image. Earlier research records MIT outside `enterprise/`, which has separate terms. Software licensing does not grant upstream model-service rights. |
| Qwen / Snowflake, llama.cpp / Ollama | Optional customer-operated models and runtimes. No weights, projector, runtime or container is redistributed. Any later inclusion needs exact-artifact license/model-card review. |

Telos source metadata declares MIT, version 0.1.0, `private: true` and a root
`js-yaml` dependency. npm's private flag is not a restriction overriding MIT.
The selected factory's location under `pi-runtime` does not establish that the
Pi SDK is bundled. Inspect actual bundle inputs before delivery; a root dependency
list or retained comments alone cannot establish complete notice coverage. The
current module manifest records source path/entrypoint, hash and Node target, not
a complete transitive-input inventory; reachability of `js-yaml` is not established
here. Resolve any additional included-code notices for the selected artifact with
focused legal review as needed, rather than attributing every donor dependency to
Noetic. The evidenced Telos obligation is preservation of its copyright and
permission notice in copies or substantial portions; its MIT text does not require
publication of Noetic source. This is not clearance of all shipped material.

## Current Readiness

Status is scoped to the evidence named below: **VERIFIED** means an inspected
artifact fact or a recorded accepted check, not fresh runtime QA or whole-product
certification. **NOT MEASURED** means the cited evidence does not establish the
claim. **OWNER DECISION** means no approval is enacted here.

| Status | Scope | Evidence and limit |
| --- | --- | --- |
| VERIFIED | Package and installed delivery identity | Source metadata is 0.3.0. Deployment QA records installed release `0.3.0-3428ebd027e005ef`; its inspected `release.json` lists the wheel, Telos module/manifest, bootstrap modules, license/notices and two docs. This is not the old 0.2.0 wheel-only delivery. |
| VERIFIED | Permissions migration and GUI service | Migration QA records 460 files at 0600 and 54 directories at 0700 with preserved content. Service QA accepts active/enabled GUI startup and bounded restart/isolated-child survival evidence; later deployment QA confirms the new release serving 19 retained runs. No reboot or host-wide process-cleanup certification. |
| VERIFIED | Managed code rollback | Deployment QA accepts the recorded new -> old managed -> new release exercise and independently checks final deployment/preservation. It did not independently repeat rollback; code selection is not data recovery. |
| VERIFIED | Bounded data recovery | Recovery QA independently checks same-host offline-copy backup/restore equality, 25 SQLite integrity checks and installed read-only inspection of 19 restored runs / 444 outer events. Not strict archive export, portable continuation, live restore or off-device disaster recovery. All 57 legacy ownership unknowns remain unknown. |
| NOT MEASURED | Customer value and unit economics | No matched customer baseline, human effort savings, willingness to pay, verified inference bill, support burden or margin. Earlier task timing below is not a benchmark of this installed release. |
| OWNER DECISION | Commercial delivery | Selected-file rights, customer grant, supported provider/plan claims, price, support/exit commitments and authorized recipients/pilot remain unresolved. Technical acceptance does not authorize sale. |

The installed manifest is under
`/home/dgk/.local/share/noetic-dev/releases/0.3.0-3428ebd027e005ef/release.json`.
It includes `getting-started.md` and `release-and-archives.md`, not this commercial
document or `release-requirements.md`. These edits are repository documentation
only; no installed file, wheel or delivery ZIP is updated by this unit.

## Data And Model Access

Local-first means local control and retained controller, journal and evidence
state, not zero egress. Prompts, selected code, tool results and retrieved context
may reach the selected provider. Local logs, summaries and indexes may themselves
contain customer material. Customer documentation must identify storage locations,
retention, backup/export/deletion scope and optional diagnostic sharing; do not
promise capabilities merely because they are requirements below.

| Route | Data path and authentication owner |
| --- | --- |
| Native Astra | Noetic invokes the customer's Pi or OpenCode client, which sends task context to OpenAI's cloud. Pi's `openai-codex/gpt-6-astra` uses Pi's native OAuth lifecycle; OpenCode's `openai/gpt-6-astra` uses its native subscription integration as documented locally. |
| Gateway Astra | Client -> customer-controlled LiteLLM -> OpenAI cloud. `litellm/codex/gpt-6-astra` is not local inference merely because the gateway is local. The client authenticates to the gateway; LiteLLM's `chatgpt` provider manages upstream subscription refresh/persistence. |
| Local support | Explicitly selected customer-local gateway -> Qwen on llama.cpp for supporting summaries, or Snowflake on Ollama for embeddings. Local deployment must be configured and available; selecting these support routes does not move primary Astra actors offline. |
| Metered API | Customer API account through the chosen client/gateway; usage billing is separate from subscription sign-in. In Pi, `openai/gpt-6-astra` is distinct from its native subscription route. No silent billable fallback. |

See [Astra access](pi-astra.md) and [local models](local-models.md). Gateway
credentials and subscription tokens are different: do not copy native tokens into
gateway configuration or make Noetic own subscription refresh. BYO access grants
neither resale nor pooling rights. Successful authentication is technical evidence,
not permission to share accounts or serve customers from a developer subscription.
Check the actual plan, client, automation use, region and current provider terms
before advertising a supported commercial integration. Customer API/local options
remain distinct choices, not a workaround for subscription restrictions.

## Owner Decisions

The following are suggested owner/legal decisions, **not enacted policy**. Resolve
them for the corresponding external delivery, not as blockers to unrelated local
development:

- Confirm rights to selected first-party contributions, donor material, documentation
  and assets, including relevant employment/contractor assignments. A contributor
  workflow or Git author label does not prove ownership.
- Choose an explicit customer use/distribution grant, support/update period,
  customer project/output rights, confidentiality and opt-in diagnostics terms,
  warranties/liability and jurisdictions. Keep customer projects under customer
  ownership; do not claim exclusivity over MIT components.
- Obtain focused legal advice where needed on distribution terms and AI-assisted
  code copyright/enforceability. Provider output assignment cannot create rights
  the law does not recognize; non-unique output and third-party rights remain
  relevant. Preserve genuine human design/edit history without manufacturing
  authorship. Human review alone does not establish copyright protection.
- Approve recipients and delivery channel separately. The research reports a public
  repository and this checkout contains uncommitted application additions. Neither
  fact authorizes publication or proves those additions were published. Existing
  public material cannot simply be promised as confidential.
- Choose the buyer hypothesis and authorize any matched pilot, its continuation
  criteria and proposed price. Decide support scope and cost responsibility only
  after recording setup/support effort and customer inference costs; no free
  subscription access, free support or profitable price is established.

## Buyer Hypotheses

These are three hypotheses, not validated demand or revenue forecasts. Any pilot,
customer contact or pricing experiment requires separate owner authorization.
Compare matched bounded tasks against each buyer's existing agent plus checklist;
include setup, failures and abandoned tasks, not only successes.

The differentiated workflow proposition is accepted intent linked to implementation,
actual verification results, fresh phase-specific review and retained continuation
evidence, as described in [the harness](harness-runtime.md). Multiple agents, BYO
models and a local UI alone are not differentiation. Less reconstruction/review
effort is a hypothesis to test, not a demonstrated advantage over Pi/OpenCode or
other existing workflows, nor an exclusive intellectual-property claim.

| Buyer and proposed value | Measurable pilot signal |
| --- | --- |
| Small consultancy technical lead: less reconstruction and review effort for maintenance fixes | Adoption: teams returning for a second task. Measure human review/reconstruction minutes, elapsed time to accepted change, seven-day reopenings/rework, setup/support minutes and customer inference cost per accepted task. |
| Solo professional maintaining several repositories: dependable interruption continuity | Adoption: weekly repeat use and successful return to a retained task. Measure human recovery/review minutes, time from reopening to useful work, duplicated work or lost-context rework, and total tool/compute cost versus the existing workflow. |
| Internal platform lead: clearer intent-to-evidence handoff for bounded team changes | Adoption: eligible tasks voluntarily routed through Noetic and reviewers returning. Measure human acceptance minutes, end-to-end lead time, material acceptance failures/rework, onboarding/support effort and total cost per accepted change. |

Agree continuation thresholds before an authorized pilot. Directional candidates:
lower median human effort without increased material failures or worse completion
time, repeat adoption and explicit willingness to pay a stated price. Small samples
do not establish general productivity or profitability. Net customer value uses
measured net hours saved at the buyer's agreed labor value, less added compute and
amortized setup; do not double-count review savings. Vendor contribution subtracts
measured support, delivery and vendor-paid infrastructure costs from actual revenue,
before fixed costs. No profit figures are assumed.

### Existing Cost And Effort Evidence

The earlier capacity report records **two concurrent real pattern runs**, **12
distinct actor sessions total**, and sampled completion windows of approximately
**6m14s and 4m04s**, with no remediation, return or failure in that pair. Twelve
sessions were not twelve simultaneous actors or twelve accepted customer tasks.
Development author subprocesses ranged from 23.806 to 136.368 seconds, QA from
9.575 to 68.733 seconds, and cognition operations from 39.405 to 88.289 seconds.
These are historical subprocess durations, not request latency, human labor time,
maximum throughput or fresh measurements of 0.3.0. No new model work was run here.

Price, customer subscription/API charges, local hardware/energy cost, onboarding,
human review/rework and vendor support effort remain **unknown / not measured**
for a commercial offering. BYO access moves responsibility; it does not make
inference or support free. Actor counts/timeouts are not request or monetary caps,
and absent cost fields in model configuration do not mean zero cost. The economic
worksheet above must remain unpopulated until actual evidence exists.

## Evidence Limits

Based on `/tmp/opencode/noetic-commercial-readiness.md`,
`/tmp/opencode/noetic-production-release.md` and
`/tmp/opencode/noetic-production-capacity.md` (2026-09-07 research), plus inspected
local license, package metadata and Telos bundle code. These temporary reports are
engineering source notes, not customer deliverables or permanent links. Telos's
actual `/home/dgk/workspace/telos/LICENSE.md` supplies the verbatim notice; its
`package.json` supplies component metadata. Reports' runtime findings are attributed,
not rerun here. No exhaustive provenance/transitive-license audit, legal opinion,
customer validation or production QA is claimed.

Later accepted reports reused without rerunning their operations (all 2026-09-07,
under `/tmp/opencode/`): `noetic-distribution-correction-qa.txt` for the earlier
document version correction; `noetic-release-archive-qa.txt` for its fixed-wheel
install/Telos/archive checks; `noetic-runtime-privacy-migration-qa.txt`;
`noetic-gui-service-qa.txt`; `noetic-focus-deployment-rollback-qa.txt`; and
`noetic-data-recovery-qa.txt`. Their explicit limits remain in force. Temporary
reports are not permanent customer evidence links; the deployment/recovery reports
identify retained private artifacts outside `/tmp`. No private payload is copied
into this documentation. Acceptance of earlier documents does not accept these edits.

Relevant legal-review references, not newly verified contract conclusions:
[OpenAI terms](https://openai.com/policies/terms-of-use/),
[business terms](https://openai.com/policies/business-terms/),
[Codex authentication](https://developers.openai.com/codex/auth/) and the
[U.S. Copyright Office AI copyrightability summary](https://www.copyright.gov/newsnet/2025/1060.html).
See [release requirements](release-requirements.md) for the bounded delivery gate.
