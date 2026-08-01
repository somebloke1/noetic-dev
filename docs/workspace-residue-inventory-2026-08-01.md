# Workspace retained-residue identity inventory - 2026-08-01

**Base inventory observed through:** 2026-08-01T08:59:49Z
**Synthesis status and stash subjects refreshed:** 2026-08-01T09:47:03Z

This is a read-only, local, non-secret identity appendix for `ROADMAP.md`. It
records retention identities; it does not judge content correct, commit work,
contact remotes, or authorize cleanup. All `origin/*` relationships are local
remote-tracking observations.

Notation:

- `R/P/NP`: registered, present, not prunable.
- `R/M/P`: registered, missing, reported prunable because the gitdir target is
  absent.
- `NA`: upstream is named but the local remote-tracking ref is absent.
- Dirty digests are SHA-256 over byte-sorted
  `XY<TAB>relative-path<LF>` rows from Git status, not file contents.
- Every row defaults to **retain until its issue, ownership, reachability, and
  exact implementation:QA gate says otherwise**.

## 1. Registered worktrees

```text
repo path | state | HEAD | registration | upstream | ahead/behind | status(count,digest)
syn /home/dgk/workspace/synthesis | main | 29196a67349537d6f8a8a711df11b86da0430857 | R/P/NP | origin/main | 0/0 | dirty(13,28b57b45407c541f02c213f00f8c927c5c59052c523541f3be72626f40418703)
syn /home/dgk/workspace/synthesis-worktrees/chore-opencode-project-agents | chore/opencode-project-agents | 29196a67349537d6f8a8a711df11b86da0430857 | R/P/NP | - | -/- | dirty(3,3ae6c6d83940792da1ba2276f74f58204e7187b90944120cb675cb082b286dea)
syn /home/dgk/workspace/synthesis-worktrees/issue-27-terra-canary | issue-27-terra-canary | 161b262b2321444d4fb322931b640483d0a14eb2 | R/P/NP | origin/issue-27-terra-canary | 0/0 | dirty(6,ed0c09f13bbfde717d6dcecad9962266e4bb76413054d8c3dae6cfba7536efa1)
syn /home/dgk/workspace/synthesis-worktrees/issue-29-routed-pi-recovery | issue-29-routed-governance-remediation | c60f8e48a17e88db5d00322f675a02a4b17ceeaa | R/P/NP | origin/issue-29-routed-governance-remediation | 0/0 | dirty(19,5ce958fed052870db2916a7104c8364b8940b64818ab887c6a3d49f582f95f63)
syn /home/dgk/workspace/synthesis-worktrees/issue-32-canonical-roadmap | issue-32-canonical-roadmap | 3d3c1d45d05de69d4f3cb1de6fb137dd6b2e0e6f | R/P/NP | origin/issue-32-canonical-roadmap | 1/0 | dirty(2,1edee4925746631b94660de06b2efc106f0ac91b7597518504a211a7ee6694b0)
syn /home/dgk/workspace/synthesis-worktrees/issue-65-opencode-spike | issue-65-opencode-spike | 8fcb1c509b14f10f1f7e2ef2363ffb98996fa46b | R/P/NP | origin/issue-65-opencode-spike | 0/0 | clean

cf /home/dgk/workspace/cf-controlplane | codex/issue-389-cf-catalog-service-truth | 834badb9f64371539e44a0f4f674c56b7ee7d0cf | R/P/NP | origin/codex/issue-389-cf-catalog-service-truth | 2/0 | dirty(33,7e777b556cb3382c87fdd1101bdf1df5c023c88d1a0e5c8f02c5b7f807321939)
cf /home/dgk/workspace/cf-controlplane-comprehensive-mcp-testing | codex/comprehensive-mcp-testing-superloop | 32144994a26094705d742987fe62471dd2b4b2e8 | R/P/NP | origin/codex/comprehensive-mcp-testing-superloop | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-155-governance-authority | codex/issue-155-governance-authority | fd02dc51f4872e7e6dbd391c45a0e69bf27359e1 | R/P/NP | origin/dev-root | 0/218 | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-187 | codex/issue-187-readiness-claim-linter | b734e9928209e1e74c45bf13b25567e9a517f791 | R/P/NP | origin/codex/issue-187-readiness-claim-linter | 0/0 | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-188 | codex/issue-188-model-id-evidence | e16a91065a7e83e0ee307743519291cf0d4e4be6 | R/P/NP | origin/codex/issue-188-model-id-evidence | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-189 | codex/issue-189-redacted-diagnostics-bundle | 36bc2f4271db83c6f816085c413715eb8dee1bae | R/P/NP | origin/codex/issue-189-redacted-diagnostics-bundle | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-190 | codex/issue-190-false-readiness-fixtures | daaf036323502a8f63a5458ab6d080c36dc71b64 | R/P/NP | origin/codex/issue-190-false-readiness-fixtures | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-198-interactive-pi-session | codex/issue-198-interactive-pi-session | dc92c77503963309ec126b73f5498b57a3669806 | R/P/NP | origin/codex/issue-198-interactive-pi-session | 0/0 | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-220-corrupt-project-state | codex/issue-220-corrupt-project-state | 42bfe1fdb83f6c6f6a49ac4d1934bb13d9229c88 | R/P/NP | origin/codex/issue-220-corrupt-project-state | 0/0 | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-223-unsafe-tool-policy | codex/issue-223-unsafe-tool-policy | 061ec7c2af0ead3f63a750403a6528b4430c406d | R/P/NP | origin/codex/issue-223-unsafe-tool-policy | 0/0 | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-228-absent-tool | codex/issue-228-absent-tool-guidance | 39bc41ae1db08d04f1c4224bf6f67e8af5f51844 | R/P/NP | origin/codex/issue-228-absent-tool-guidance | 0/0 | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-233-malformed-result | codex/issue-233-malformed-result-diagnostic | fd02dc51f4872e7e6dbd391c45a0e69bf27359e1 | R/P/NP | origin/dev-root | 0/218 | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-243-ordinary-init | codex/issue-243-ordinary-init | 2d70a0adf52caecad050335deed254ea43c84c9d | R/P/NP | origin/codex/issue-243-ordinary-init | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-270-259-260 | codex/issue-301-semantic-fixture-validation | 84eae4f13fd37325f9bd8cc039f6e1839981d5f5 | R/P/NP | origin/codex/issue-301-semantic-fixture-validation | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-284-successor-topology | codex/issue-284-successor-topology | 3da9a872f875a171bee6c406a7c42192e1ddaa67 | R/P/NP | origin/codex/issue-284-successor-topology | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-306-session-termination | codex/issue-306-session-termination | 624288cc85847be1f3d6d2f49f5961ae1468998e | R/P/NP | origin/codex/issue-306-session-termination | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-319-github-mcp-successor | codex/issue-319-github-mcp-successor | 0ae8d5058df1950ad20220fe8f18c8b0b79ffc6a | R/P/NP | origin/codex/issue-319-github-mcp-successor | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-issue-396-4445-required-families | codex/issue-396-4445-required-families | bb4e6a5974f2b22265c76b1e1bbef0883a6c1613 | R/P/NP | origin/dev-root | 42/0 | dirty(17,e8fb1c1fab8f771adc3c7ba595638b031c128fb605eab6f2058fbe6f0f6df73b)
cf /home/dgk/workspace/cf-controlplane-issue-52-serena-onboarding | codex/issue-52-serena-onboarding-record | 43962c2e11f1a1664d9631b3436a20576d5372d2 | R/P/NP | origin/codex/issue-52-serena-onboarding-record | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-pr-300 | codex/rework-issue-270-symbolic-dispatch | 3f86237c98b6d56e4d147b7c7b35fc9390595711 | R/P/NP | origin/codex/rework-issue-270-symbolic-dispatch | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-qa-035730f | detached | 035730f0afa4a89d3c70a95782d49dae62362814 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-14c9746 | detached | 14c974659833f224e7d82046f8f4164ac4d5371f | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-1e08dcc | detached | 1e08dcce5d46c094f3da51f9f8160098ac606244 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-1ed857b | detached | 1ed857b333d6114e00a46658c427c9650fa5ac55 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-3d26703 | detached | 3d2670350e77c79911913a0e527466279a23e84c | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-4ba6c5d | detached | 4ba6c5d35853a421f4f998b018876387bea6b390 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-4e51e4b | detached | 4e51e4b3545a1d1f5227c23fe0c568a92240fe5c | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-60afeb8 | detached | 60afeb826b8206dfbbb0a0a220f1276d10c0f8e8 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-61f4a7d | detached | 61f4a7d2ac09377bbf58ec2bec67b433379438be | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-661b9fc | detached | 661b9fc2c3eba752e644638cc15b40b1f892edb7 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-702e829 | detached | 702e82985579af3ac8152f1e2418706941b3ba2d | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-97122b4 | detached | 97122b4678e4c679af65075b2a67bfbcf08430b5 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-a2c815f | detached | a2c815f717a74299b1a0dec4888b847f07aed791 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-bff64e0 | detached | bff64e0fb7a8e8bf73023a01884f32ee4041bd8a | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-c08aa58 | detached | c08aa58927900a9684c9434aea1822220a5f1dff | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-qa-cec7ec9 | detached | cec7ec992e2021db4199a92b8913d422ffdf5657 | R/P/NP | - | -/- | clean
cf /home/dgk/workspace/cf-controlplane-strategic-pi-tdd | codex/strategic-pi-tdd-catalog | cfbed544edacf3300cd4f91b43921bb824711369 | R/P/NP | origin/codex/strategic-pi-tdd-catalog | 0/0 | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-superloop-skill | codex/issue-322-target-project-init-guidance | 51981b7dba571473d6c6ce8f8c5541f2c56b37af | R/P/NP | origin/codex/issue-322-target-project-init-guidance | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-testing-method-lessons | codex/issue-317-testing-method-lessons | f1ce287ee276a09b4ecd8b120f041515b856b78a | R/P/NP | origin/codex/issue-317-testing-method-lessons | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane-worker-144 | codex/issue-144-opencode-mentality-call-proof | 9c5c5aab75e16bedfb7a493f1d2157b43d6bdb81 | R/P/NP | origin/codex/issue-144-opencode-mentality-call-proof | NA | dirty(1,89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf)
cf /home/dgk/workspace/cf-controlplane/run/blind-onboarding/time-seed-trial | codex/blind-time-seed-trial | 2135d025bdcac23d4142851f6c1699a33a4ae812 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-2917644-opencode | detached | 2917644cc76085964e4e9659e0f328fd334718d1 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-778af10-worktree | detached | 778af103c6125908ba10dd65df0471ddc3a18118 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-c50cbb8 | detached | c50cbb8c9a08bf2b3eb9b5e180101c40f8dc9f68 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-d69ce7b-opencode | detached | d69ce7bfff083012489684b4409c766a61944c13 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-e01974c | detached | e01974c6d5672fff99ff78d29caa447c1149e330 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-e5552d0 | detached | e5552d0a46e9fad7f25881eb75adb0efcff7d084 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-e718437 | detached | e718437fa36603364e0b1aae5e1f27744255c7b7 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-e888331 | detached | e8883314e4e383709bcfdbafb3c462aa489f399f | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-eed5b28 | detached | eed5b287c723a442f2424d6069570f66a530e074 | R/P/NP | - | -/- | clean
cf /tmp/opencode/qa-fc2a60c | detached | fc2a60c07de60bb5b4a3cb19020d54fe01bb817e | R/P/NP | - | -/- | clean

npi /home/dgk/workspace/noetic-pi | public-export-launch-prep-20260430 | 683b53b06714d0aadd49c5852140b708c5abba69 | R/P/NP | origin/public-export-launch-prep-20260430 | 0/0 | dirty(184,e46c25f98d4c71f159e1eadd0b6b6a96b12fec4fdc4be96ceb4f69fef1c2646b)
npi /home/dgk/workspace/.noetic-pi-worktrees/08142343/variant-1 | public-export-launch-prep-20260430--orch-08142343-v01 | d9c271f684daa574a253f06458c14b4c3880406b | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/.noetic-pi-worktrees/08142343/variant-2 | public-export-launch-prep-20260430--orch-08142343-v02 | d9c271f684daa574a253f06458c14b4c3880406b | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/.noetic-pi-worktrees/08142343/variant-3 | public-export-launch-prep-20260430--orch-08142343-v03 | d9c271f684daa574a253f06458c14b4c3880406b | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/.noetic-pi-worktrees/583c45da/variant-1 | public-export-v02-closure-exec-20260430--orch-583c45da-v01 | 079574ee6666c9367dead4f4d52dd6db797d97e5 | R/P/NP | - | -/- | dirty(3,0360ff0b773c42c610393bf30d99613195b20f0b6c438cb0faf24bf97d022d09)
npi /home/dgk/workspace/.noetic-pi-worktrees/583c45da/variant-2 | public-export-v02-closure-exec-20260430--orch-583c45da-v02 | f20f19a34fbb62e4eb3f80a5482275203f80c310 | R/P/NP | - | -/- | dirty(5,e30f06dfb0a3d03e32c4c76525d447f34d70d35be8405b38128df02b4dbb1aac)
npi /home/dgk/workspace/.noetic-pi-worktrees/583c45da/variant-3 | public-export-v02-closure-exec-20260430--orch-583c45da-v03 | 759ccbc87134848379fdc6c446cf4f1e875f3766 | R/P/NP | - | -/- | dirty(3,125c703d6ea7e4fb736edf4b030eaa5f48281de5bfedb7833852a28017fc7d83)
npi /home/dgk/workspace/.noetic-pi-worktrees/b118bbac/variant-1 | public-export-launch-prep-20260430--orch-b118bbac-v01 | 69daaf5d0d2c3648a626c81a5599acd42f8a59f9 | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/.noetic-pi-worktrees/b118bbac/variant-2 | public-export-launch-prep-20260430--orch-b118bbac-v02 | 69556004cb553fdb28d9434945eec5307d03d32c | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/.noetic-pi-worktrees/b118bbac/variant-3 | public-export-launch-prep-20260430--orch-b118bbac-v03 | c03792f8c59bbac922bf888ecb62116e504d8bab | R/P/NP | - | -/- | dirty(22,f38e2230c4e75a493595b0c27ada3bf962c6654393cb121d589360449b3b6ec6)
npi /home/dgk/workspace/.noetic-pi-worktrees/d7c3389e/variant-1 | public-export-v02-closure-exec-20260430--orch-d7c3389e-v01 | 15ef7bf92c1af95ed876441a2035090f70880f47 | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/.noetic-pi-worktrees/d7c3389e/variant-2 | public-export-v02-closure-exec-20260430--orch-d7c3389e-v02 | 15ef7bf92c1af95ed876441a2035090f70880f47 | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/.noetic-pi-worktrees/d7c3389e/variant-3 | public-export-v02-closure-exec-20260430--orch-d7c3389e-v03 | 15ef7bf92c1af95ed876441a2035090f70880f47 | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/noetic-pi-ai0115-prep | detached | 8e89099a710b2635feff62cd4728da2b0753a7de | R/P/NP | - | -/- | clean
npi /home/dgk/workspace/noetic-pi-v02-closure-exec-20260430 | public-export-v02-closure-exec-20260430 | 9a065c9de6d6af086e53453b31cd66f426dd3722 | R/P/NP | - | -/- | clean
npi /tmp/wu2-stagecheck-KWxYUw | detached | c3aebed18b2b912a66cb724bb23e7029236d555d | R/M/P | - | -/- | unavailable

sae /home/dgk/workspace/saeproj | pi2-governance-adoption | fcc4bc465cd82256cec3d6cfc7e6958510291c9d | R/P/NP | - | -/- | dirty(27,e8ec071a5f984a2b5ed17b42f7cb4479e22ac568dd3df5be847bf86bdda32f52)
tel /home/dgk/workspace/telos | main | 951f3a9c1e9eec2e64848e44a61e050a9dc56464 | R/P/NP | origin/main | 6/0 | dirty(124,a0df7dbf063a0bb046d7642a2f8258e0a76b9bd49ff0b1e02256626c9a5c2f9d)
tel /tmp/opencode/telos-pi-live-sync-1252728 | detached | 12527284ab607146ddedb85ccb50317781988947 | R/M/P | - | -/- | unavailable
npd /home/dgk/workspace/noetic-pi-docker | main | 30de068b651c35a475a282e2c8dabe883b77c1a0 | R/P/NP | origin/main | 0/0 | dirty(10,f3a212ab44b35a4d2318440f0bc25f2c35004eca9f73c0068d80f3ae1272f31b)
pi2 /home/dgk/workspace/pi2 | main | 17cdb45b5711a6ae76888350ff5d89c5f2a24c89 | R/P/NP | origin/main | 86/0 | dirty(4,3a9a9fe7ccd956b143dbda4a6846d8c6928fc9f7d124b7176591de4b85e40063)
gr /home/dgk/workspace/genus-router | main | 4ff584e2e5d190b7e25dc0a4607c494a50069b83 | R/P/NP | origin/main | 0/1 | clean
gr /home/dgk/workspace/genus-router-worktrees/issue-11-loopback-litellm | issue-11-mcp-outcome-smoke | 896bab9b52feb0c113c17945c6f7e9a12a27d66d | R/P/NP | origin/issue-11-mcp-outcome-smoke | 0/0 | clean
gr /tmp/opencode/genus-router-6a6487f-gate-runtime | detached | 6a6487f2ccf69046e48ef7b38af2533e885ae7c4 | R/M/P | - | -/- | unavailable
cd /home/dgk/workspace/cognitive-disciplines | main | 923686521b78a4c0cb2e86a23a6eb5d4f9e0c5e4 | R/P/NP | origin/main | 0/0 | clean
```

The three `R/M/P` rows are retained despite reported prunability. Resume requires
a dedicated reachability/ownership check; this inventory does not authorize
`git worktree prune`.

## 2. Stashes

No stash is to be applied, popped, dropped, rewritten, or used as integration
evidence before a stash-specific issue identifies ownership, base, intended
concern, and QA requirements.

```text
repository ref | stash OID | base | additional parents | subject
cf stash@{0} | 7da6ff47aa306c622547fe7575913754fd6c961b | 514f1be7c150beff83cede82b343bf74ff38fed7 | 7e19eaf163a8bf443e7f34cfdd37659b836babc0 | On codex/helper-visible-response-format: ux-helper-visible-response-formatting-clean-branch-state
cf stash@{1} | 77a9f44033a71f5c4c8bb8689a9fd6772b45109f | 4d576ac9f582fea434adda3703b89663057f90f2 | 6d1dd99420ed0b497c9a9fc344216ea4d1644bf1 | On codex/fix-wrapper-idle-timeouts: ux-helper-visible-response-formatting
cf stash@{2} | 22179e41f8d833da983797fca36703339853048b | 06110099089fd987665020d666841e670ecff65b | 2382f6062e63a0d0aa6564874823ee00cecd8630 69510b015f59e2dc26cf9c518be27f7da85be690 | On codex/issue-62-pi-activation-bindings: preserve issue-62 dirty split: symbolic dispatch, project-init wording, architecture map, local envrc
npi stash@{0} | bcf5a2568b17a68cb01b5727958a5e6f7904ba77 | be2e639083eb01c247b2c4fbcfdef5a733c62673 | 10264756a384e8c22f5fa54d4db8d1171b8d50ac d744c5b322e7406856c5ac5cfd90face0bc03d69 | On ai-0120-line-cap-relaunch-20260427-r2: implementer residue before main ff
npi stash@{1} | fee3ab641c7e8b7d372676c8e9bbf1cc3739aacc | 6fad46cdd8fb4aca69e56b5f9d9c250f28c54b84 | 19ef927d2ce90efb33adda68dbcd64dc55759b3a 229d706c7dbc3b3a778387509baec66cdedec508 | On implement-file-slicing: pipeline-validation-pre-impl-orch
npi stash@{2} | f0b7f194eda0b8eef29c1e4b6df5c0615d2a88b7 | 2ffc32949962c4e1203cb9183b0e980246c8b78b | adf980a92bf69a9e76b65587ad6107082eb8cbc5 61e3ada26b6b26055fd399e46aa5e64c4d6968e4 | On ai-0115-controller-hardening-impl-r1: pre-ai0084-root-neutralize-2026-04-20
npi stash@{3} | 03ed7d90436ec5571f7c745628cb020c4c8fae8b | e755731dcab748909c99f86f17d211220fcbcba7 | 8224fdf748d7a5299821d8422dfca08fe8e6b3d2 | On hermetic-worktree-enforcement-impl-r1: WIP before parser fix implementation
npi stash@{4} | fbf56d3e59f3a16019070964cc6271d6f475d1ef | 553b9d2f7d50006ac441a3357c24451e25a2c4bd | 1f630b179567a2e4f5fb0f64664b5c28145f12a8 | WIP on impl-resilience: 553b9d2 Wave 2: Circuit-breaker recovery logic for implementation pipeline: constants, recovery_failed status handling, and diagnostic escalation in handleImplementationRecovery, Circuit-breaker recovery logic for plan pipeline: constant, recovery_failed status handling, and diagnostic escalation in handlePlanRecovery\n\nWork units:\n- WU2: Circuit-breaker recovery logic for implementation pipeline: constants, recovery_failed status handling, and diagnostic escalation in handleImplementationRecovery\n- WU3: Circuit-breaker recovery logic for plan pipeline: constant, recovery_failed status handling, and diagnostic escalation in handlePlanRecovery\n\nImplementation: 75c45177
sae stash@{0} | 8641ab98e253c39d845034ef48e6d502e62b3aed | a74d3fdbb9504c55e661c6725bac9481a627471f | fc6eb923196acb31cdee12ab7910acab32d86e4c | WIP on governance-reconciliaton: a74d3fd docs(blueprint): mark candle-pattern-coverage as COMPLETE
npd stash@{0} | 1496a716cc1112a47ae7b23b611ea4db832114bd | 3ef7ad7fc714d1db7d08402cefa2331ef874f1e2 | bfd38a40696b991e79c66413b68242cda9af1040 b283d6c3570c19f26f376db1c541c3d204672f4e | On feat/deepseek-productionization: wip-unrelated-local-residue-before-github-cleanup-2026-07-02
pi2 stash@{0} | d58c28895081038ba6fe3e7b0dce0505c39e3a12 | 0f40f4137407e9afe76b4aa30ffcf1ce4ca42a4a | 3a63eebd8bc07687bccc6d1acaca769fdddfdaf7 | WIP on feature-phronesis-grounding: 0f40f41 chore: commit working tree before branch switch (LOG.md, phronesis index, census audit log)"
```

Synthesis, Telos, genus-router, and cognitive-disciplines had no stash refs.

## 3. Additional retained branch heads

These locally retained heads have no registered active worktree row above or add
material ancestry context. They are not current remote claims.

```text
npi public-export-v02-closure-exec-20260430 | 9a065c9de6d6af086e53453b31cd66f426dd3722 | no upstream
sae governance-reconciliaton | a74d3fdbb9504c55e661c6725bac9481a627471f | no upstream
sae main | c0fdf147bed2104d980e2bb19e6d6b822e3dfec8 | no upstream
sae omo-dev | f482421d6717974e95cb25d7faf7406c77ed94f4 | no upstream
pi2 context-addressed-routing | cd5852f75be5b4b9748c8ef5aa98c09b10e95919 | no upstream
pi2 feature-phronesis-grounding | 0f40f4137407e9afe76b4aa30ffcf1ce4ca42a4a | origin/feature-phronesis-grounding, ahead 3
pi2 phronesis | 8dc1ca3b8bd290b55eb8daf8afdee11e397f1395 | no upstream
syn issue-29-broker-lifecycle-evidence | 9172b1e13c5ed54eac8b4af6e700c17c282c193c | upstream 0/0
syn issue-29-modality-evidence-record | cd915566154097735e1c33d260b01c7d8210f456 | upstream 0/0
syn issue-29-modality-readiness | 43861367d2199143aa4d5e8f7aa347fd62a2ae4c | upstream 0/0
syn issue-29-routed-pi-recovery | 4177a9d9b6f9e39ee3dd831ccef354ddaf1f5d68 | upstream 0/0
syn unreferenced candidate object | 627f2b5d484ea9d2fb745646debe5104f332a362 | no containing local ref/worktree
```

ContextForge root's two locally ahead commits are
`b2eb799a08d372f559eaf034a730219d9fee9f85` and
`834badb9f64371539e44a0f4f674c56b7ee7d0cf`. Telos's six exact commits are
recorded in `ROADMAP.md` section 4.

## 4. Repeated ContextForge configuration status

Twenty-three worktrees report ` M .codex/config.toml`. No configuration was
opened or content-hashed. The SHA-256 over byte-sorted
`absolute-worktree<TAB>XY<TAB>.codex/config.toml<LF>` rows is
`ea5fa0c00da360a4f4a542a9f828934506e081a1178dcc57467d436cded83d6e`.
Every single status/path manifest is
`89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf`.

```text
/home/dgk/workspace/cf-controlplane
/home/dgk/workspace/cf-controlplane-comprehensive-mcp-testing
/home/dgk/workspace/cf-controlplane-issue-155-governance-authority
/home/dgk/workspace/cf-controlplane-issue-187
/home/dgk/workspace/cf-controlplane-issue-188
/home/dgk/workspace/cf-controlplane-issue-189
/home/dgk/workspace/cf-controlplane-issue-190
/home/dgk/workspace/cf-controlplane-issue-198-interactive-pi-session
/home/dgk/workspace/cf-controlplane-issue-220-corrupt-project-state
/home/dgk/workspace/cf-controlplane-issue-223-unsafe-tool-policy
/home/dgk/workspace/cf-controlplane-issue-228-absent-tool
/home/dgk/workspace/cf-controlplane-issue-233-malformed-result
/home/dgk/workspace/cf-controlplane-issue-243-ordinary-init
/home/dgk/workspace/cf-controlplane-issue-270-259-260
/home/dgk/workspace/cf-controlplane-issue-284-successor-topology
/home/dgk/workspace/cf-controlplane-issue-306-session-termination
/home/dgk/workspace/cf-controlplane-issue-319-github-mcp-successor
/home/dgk/workspace/cf-controlplane-issue-52-serena-onboarding
/home/dgk/workspace/cf-controlplane-pr-300
/home/dgk/workspace/cf-controlplane-strategic-pi-tdd
/home/dgk/workspace/cf-controlplane-superloop-skill
/home/dgk/workspace/cf-controlplane-testing-method-lessons
/home/dgk/workspace/cf-controlplane-worker-144
```

Each row remains retained until its owning issue establishes whether the repeated
status is intended project configuration, stale residue, or a cleanly removable
worktree. No row is a cleanup candidate merely because its digest repeats.

## 5. Non-secret client/runtime snapshot

Only executable paths, version output, config-path presence, process names/PIDs,
and system unit names were observed. No config values, arguments, environments,
or credentials were read.

```text
Pi | /home/dgk/.nvm/versions/node/v24.12.0/bin/pi | 0.80.3
OpenCode | /home/dgk/.opencode/bin/opencode | 1.18.9
Claude | /home/dgk/.local/bin/claude | 2.1.207 (Claude Code)
Codex | /home/dgk/.nvm/versions/node/v24.12.0/bin/codex | codex-cli 0.144.3
Goose | /home/dgk/.local/bin/goose | 1.41.0
VS Code | /usr/bin/code | 1.123.0; 6a44c352bd24569c417e530095901b649960f9f8b; x64
tmux | /home/dgk/.local/bin/tmux | tmux 3.6b
Kilo | /home/dgk/.nvm/versions/node/v24.12.0/bin/kilo | 7.0.27
Kilo alias | /home/dgk/.nvm/versions/node/v24.12.0/bin/kilocode | 7.0.27
```

Present, unopened configuration paths:

```text
Pi: /home/dgk/.pi, /home/dgk/.pi/agent, /home/dgk/.pi/agent/settings.json
OpenCode: /home/dgk/.config/opencode, /home/dgk/.config/opencode/opencode.json
Claude: /home/dgk/.claude, /home/dgk/.claude/settings.json, /home/dgk/.claude.json
Codex: /home/dgk/.codex, /home/dgk/.codex/config.toml
Goose: /home/dgk/.config/goose, /home/dgk/.config/goose/config.yaml
VS Code: /home/dgk/.config/Code/User/settings.json
tmux: /home/dgk/.tmux.conf
Kilo: /home/dgk/.config/kilo
```

Observed process PIDs were: `code` 612461, 612505, 612562, 613591, 614440,
618521, 624194, 1171510, 1171520, 3962752, 3962755, 3962756, 3962769,
3962806, 3962810, 3962815, 3962840, 3962888, 3962908, 3962922, 3962991,
3963013, 3963572, 3963966, 3964806, 3965349; `codex` 613062, 3040363,
3963571; `opencode` 358238, 1423967; and `pi` 7439, 3371651. System units
observed without elevation were `claude-code-adapter.service` and
`litellm.service`; user-service enumeration was unavailable.

This runtime snapshot is explicitly retained outside Step-4 Git integration.
Resume requires an isolated adapter/runtime issue with its own home, configuration,
version, effect, cleanup, and QA contract. It never authorizes editing user-global
configuration.

## 6. Scope and refresh rules

- The ContextForge common Git directory has a stale `core.worktree`; observations
  used explicit worktree paths. No topology was repaired.
- No file/config/stash contents, credential values, process arguments,
  environments, or user-service state were inspected.
- No fetch, pull, push, branch move, stash action, worktree prune, provider call,
  build, or test occurred.
- Remote relationships and process/service identities are point-in-time local
  observations. Before any item-specific mutation, refresh only that item's
  remote/policy/status identity and create a new inventory row if it changed.
- Dirty rows resume only through their owning issue and a new bounded
  implementation/remediation generation. Clean detached rows resume only through
  reachability and ownership adjudication. Missing registrations remain retained
  until a dedicated cleanup check proves no unique evidence or active process.
- This appendix's file SHA-256, recorded by `ROADMAP.md`, is its immutable report
  identity. Status-manifest digests can be independently recomputed without
  opening file contents.
