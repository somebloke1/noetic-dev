# Worktree correction redacted evidence manifest

## Scope

This tracked manifest transcribes non-secret results from host-local correction
records created on the host's 2026-07-19 local calendar date, after UTC crossed
to 2026-07-20. It makes the reported checks and equality claims reviewable in
the repository. It is not a signature, independent runner attestation, or
substitute for the unavailable source archive.

The UTC evidence interval `2026-07-20T00:55:52Z` through
`2026-07-20T01:26:43Z` predates protected review run
[`29717393475`](https://github.com/somebloke1/noetic-dev/actions/runs/29717393475),
which began at `2026-07-20T04:39:05Z`. Thus the UTC date is not future-dated
relative to the public review event; it differs only from the host's local date.

Protected Governance run
[`29721803357`](https://github.com/somebloke1/noetic-dev/actions/runs/29721803357)
later succeeded for exact candidate
`d2e99712f02b1ee39cae0b696e77aa3bc92dfbab`. Its hosted workflow checkout set
`persist-credentials: false`, then `validate_repo.py` invoked the worktree doctor
successfully before the checkout post-job cleanup. This public integration result
is evidence that no temporary checkout `http.*.extraheader` remained for the
doctor; credential-bearing local headers intentionally remain forbidden.

Source directories at capture time:

- `/home/dgk/noetic-dev-recovery-20260720T005900Z`
- `/home/dgk/noetic-dev-recovery-20260720T011121Z`

## Timeline

| UTC | Reported operation |
|---|---|
| `00:55:52` | preflight and synchronization pause |
| `00:56:00` | three stable baselines begun for 42 registered worktrees |
| `00:57:16` | recovery archive creation begun |
| `00:57:54` | exact config sanitization and pointer quarantine begun |
| `00:58:53` | correction reported complete |
| `01:25:46` | archived index extraction and process quiescence begun |
| `01:25:54` | staged-semantic equality checked |
| `01:25:55` | archived index bytes restored and state rechecked |
| `01:26:31` | isolated archive extraction/comparison receipt recorded |
| `01:26:43` | index remediation reported complete |

## Redacted config delta

The pre-correction config contained these four additional records, omitted from
the post-correction config:

```text
core.worktree=/tmp/opencode/pr31-role-candidate-fpr9add1
user.email=test@example.invalid
user.name=Test User
filter.hostile.smudge=/tmp/tmpj17y957m/candidate/hostile-filter.sh
```

No credential values are included in this manifest.

## Equality results

The three pre-correction captures and first post-correction capture had identical
SHA-256 values for these redacted command outputs:

| Output | SHA-256 |
|---|---|
| refs | `1ebb793ebd7ae41d815d1bb1fd005cb2d20663034e56b7b56d35bcf7a4104448` |
| registered worktrees | `004ea87754b330f83633abfde41dcaccdbb24fda2f8a321d9dce451d8c851d8b` |
| synthetic index | `99b6d3d8f00fcb8ebc362c2d0bced3521dc8a4d01c7907a26a43bf3eae4eead8` |

Archived and restored staged-semantics outputs also matched:

| Index | Archived/current SHA-256 |
|---|---|
| primary | `8c3c977ae06fefdc9645b7f97e9d7062945d1ccff3b583935b81c9c9ede2254f` |
| issue-29 | `6df42240f203e85150515762c3f4af58494b5e758f07ca85a78055ee51c9dc2b` |

## Archive receipt

The host-local receipt recorded:

```text
schema_version=1
verified_at=2026-07-20T01:26:31Z
archive_sha256=3e0a67a6bf357c346e48fc9356f3997464d3dc51d08cc8f18e46f96f6e8dfd0e
isolated_live_git_hidden=true
full_extract_exit=0
full_compare_exit=0
```

The receipt file SHA-256 was
`79ed67c3e8b9d51cc9ba5f6952742cf4149791957bbd0da1cafdfe24fe1e0ac7`;
its stdout and stderr files were both empty, with the empty-file SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Limitations

The source archive and full outputs are not tracked or attached. This manifest
therefore supports review of the reported procedure, redacted delta, hashes, and
result relationships, but cannot prove source-file possession or independently
replay the correction. The preventive controls and adversarial tests are the
durable repository evidence produced by issue #72.
