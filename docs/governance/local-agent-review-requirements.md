# Local agent-review requirements

## Purpose

Provide one required semantic review check for an immutable noetic-dev pull-request snapshot. The broker obtains a mandatory genus-router decision, validates the LiteLLM-only model reference, invokes the selected model at high reasoning, records the outcome, and reroutes after a recorded failure. This check supplies review evidence; it does not merge, publish, deploy, or execute candidate code.

## Threat model

Untrusted inputs are the GitHub event fields, PR metadata, filenames, diff bytes, model output, LiteLLM response envelope, genus-router decision envelope, and bytes sent to the broker socket. Candidate repository content may contain prompt injection and hostile data, but is never executed or imported. The fixed host executables `git`, `gh`, Python, and Bubblewrap, the installed genus-router component, and the configured LiteLLM gateway are trusted dependencies. GitHub and the host kernel are trusted service boundaries.

The relevant threats are:

- a fork, unauthorized author, draft, closed PR, or changed snapshot reaching privileged local credentials;
- mutable or incomplete review material being represented as the reviewed candidate;
- candidate text becoming instructions or executable content;
- ambiguous input, model output, or HTTP framing being accepted;
- resource exhaustion through bounded request, diff, process, or output paths;
- another local user reaching the broker socket;
- an unavailable mandatory dependency leaving an apparently ready service;
- workflow policy being supplied by the candidate branch.

Compromise of a trusted host executable, the kernel, GitHub, or the model provider is outside this control's boundary. Filesystem and network confinement of the trusted executables is not required. Such observations are residual risks unless they demonstrate failure of a requirement below.

## Acceptance requirements

| ID | Requirement | Required evidence |
|----|-------------|-------------------|
| AR-01 | The protected workflow admits only an open, non-draft, same-repository PR by an explicitly allowed author and sends full base/head SHAs. The broker independently applies the same admission before and after material retrieval. | Workflow inspection plus accepted and rejected admission probes. |
| AR-02 | The runner checks out policy from the protected base SHA only, persists no checkout credential, has read-only GitHub permissions, and never checks out or executes candidate code. | Workflow inspection and action-ref pinning check. |
| AR-03 | Review material is fetched by exact base/head SHA and is the Git merge-base-to-head binary diff. The reported digest hashes the exact strict UTF-8 bytes included in the prompt. | Independent Git reconstruction and digest comparison. |
| AR-04 | PR title, body, filenames, and diff are marked untrusted data. The broker uses the fixed `review + complex + interface` classification, accepts only a genus-router decision for an allowed model behind `local-litellm`, and enacts high reasoning. One routed attempt consists of exactly one deterministic READY-probe phase followed by at most one substantive invocation under that decision; both use the validated reference and `report_outcome` records their aggregate result. No direct provider namespace, URL, or credential is accepted. | Decision/reference mutation tests, finite-attempt contract tests, and one real routed semantic invocation. |
| AR-05 | Request size, file count, diff size, Git command runtime, stdout, stderr, LiteLLM response, and model output are bounded. Limit violations terminate work and fail closed. The prompt is sent only in the authenticated LiteLLM request body, never argv. | Boundary and over-boundary probes, timeout probe, and maximum-size prompt probe. |
| AR-06 | Request JSON, GitHub response shape, model JSON, verdict, findings, paths, line numbers, and log text are strictly validated. Duplicate keys, non-finite numbers, unknown request fields, contradictory verdicts, traversal, absolute paths, and control/format line injection fail closed. | Null, NaN, wrong-type, duplicate, unknown, out-of-range, and contradictory probes. |
| AR-07 | The Unix socket is owned and permissioned for the dedicated broker/runner access group before listening. Request reads have a finite timeout and reject missing, duplicate, signed, conflicting, transfer-encoded, oversized, or short `Content-Length` framing. | Activation interception, mode/group check, and malformed/partial HTTP probes. |
| AR-08 | Each external command runs in a Bubblewrap PID namespace. Output overflow, timeout, clean leader exit, inherited pipes, and a descendant calling `setsid()` do not leave descendants running. | Marker/PID probes for each termination path. |
| AR-09 | Bubblewrap availability and PID-namespace operation are validated before the broker creates or activates its socket. A later spawn failure returns a controlled review failure. | Missing/broken dependency startup probes and injected spawn failure. |
| AR-10 | A successful result binds repository, PR number, exact base/head SHAs, the finite attempt contract, the shared schema-v1 route-evidence object, endpoint, model, reasoning, sophistication, availability, reviewed-diff digest, prompt digest, verdict, summary, and findings. Every attempt includes the complete routed decision, its separately captured READY-probe evidence, and one confirmed aggregate recorded outcome. `changes-needed` fails the workflow. | Result-schema, route-evidence mutation, failure-reroute, outcome, and requester exit-code tests. |
| AR-11 | Production uses dedicated broker and runner identities, a group-restricted socket under `/run/noetic-dev`, immutable releases under `/opt/noetic-dev-agent-review/releases/<commit>`, and persistent runner state under `/var/lib/noetic-dev-runner`. The runner identity cannot read the broker's model credentials. | Installed ownership/mode inspection, service definitions, credential-denial probe, and rollback probe. |
| AR-12 | GitHub branch protection requires the exact `agent-review` check only after a live exact-SHA run succeeds. Existing protections are not weakened merely to bootstrap the check. | GitHub protection API output and successful protected workflow run. |

## QA boundary

A candidate passes code-level QA when an independent reviewer attempts to falsify AR-01 through AR-10 against one exact commit and finds no requirement violation. AR-11 and AR-12 are deployment gates and are tested only after code-level QA passes.

A QA observation is blocking only when it provides a reproducible counterexample to a listed requirement or shows that a listed requirement is insufficient for a threat named above. Adjacent hardening ideas and risks outside the stated trust boundary are recorded as residual risks, not silently promoted to new acceptance requirements. Changing this boundary requires an explicit threat-model or governance decision, followed by a new implementation generation and its paired QA pass.

There is no defect quota and no presumption that every candidate is defective. `PASS` is the required result when the attempted counterexamples do not violate the acceptance requirements. A reviewer must not manufacture a finding from hypothetical trusted-component compromise, stylistic preference, an unstated ideal, or the mere possibility of additional hardening. Every blocking finding bears the burden of showing the exact requirement or named threat, the observed behavior, and a reproducible counterexample; otherwise it is an open question or residual risk.

Green evidence is stable across remediation generations unless the remediation changes the relevant control or a new reproducible counterexample directly falsifies it. Follow-up QA targets the failed requirement and regression risk from the changed lines; it does not reopen unaffected requirements merely to continue adversarial activity. The review stops when the bounded requirements pass.

## Completion

The local review path is complete only when:

1. AR-01 through AR-10 pass independent code-level QA for the final commit.
2. AR-11 passes on the installed production services and rollback is demonstrated.
3. A live PR run binds the expected immutable diff, genus-router decision/outcomes, and selected LiteLLM result.
4. AR-12 is applied and independently read back from GitHub.
5. Temporary runner and user-service artifacts are removed without removing the registered production runner.
