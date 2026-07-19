#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/bin:/bin

if [[ $EUID -ne 0 || $# -ne 2 ]]; then
  echo "usage: sudo bash $0 AUTHORIZED_DEV_SHA PROTECTED_AUTHORIZATION_RECEIPT_JSON" >&2
  exit 2
fi

authorized_sha=$1
authorization_receipt=$2
root=/opt/noetic-dev-main-publisher
release=$root/releases/$authorized_sha
canonical_remote=https://github.com/somebloke1/noetic-dev.git
verifier=/usr/local/libexec/noetic-dev/verify-delivery-attestation

[[ $authorized_sha =~ ^[0-9a-f]{40}$ ]]
[[ -f $authorization_receipt && ! -L $authorization_receipt ]]
[[ $(/usr/bin/stat -c %s "$authorization_receipt") -le 1048576 ]]
[[ -f $verifier && ! -L $verifier && -x $verifier ]]
[[ $(/usr/bin/stat -c %u "$verifier") -eq 0 ]]
verifier_mode=$((8#$(/usr/bin/stat -c %a "$verifier")))
(( (verifier_mode & 8#022) == 0 ))
challenge=$(
  /usr/bin/env -i PATH=/usr/bin:/bin HOME=/root /usr/bin/python3 -I -c '
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as source:
    receipt = json.load(source)
expected = {
    "authorized_dev_sha": sys.argv[2],
    "purpose": "install-main-publisher",
    "repository": "somebloke1/noetic-dev",
    "source_ref": "refs/heads/dev",
}
challenge = {"expected_claims": expected, "receipt": receipt, "schema_version": "1"}
sys.stdout.write(json.dumps(challenge, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
' "$authorization_receipt" "$authorized_sha"
)
/usr/bin/printf '%s' "$challenge" | /usr/bin/env -i PATH=/usr/bin:/bin "$verifier"
git_safe=(/usr/bin/env -i PATH=/usr/bin:/bin HOME=/root GIT_NO_REPLACE_OBJECTS=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 /usr/bin/git --no-replace-objects)
verify_git=$(/usr/bin/mktemp -d)
trap '/usr/bin/rm -rf "$verify_git"' EXIT
"${git_safe[@]}" --git-dir="$verify_git" init --bare --quiet
"${git_safe[@]}" --git-dir="$verify_git" fetch --no-tags --depth=1 \
  "$canonical_remote" refs/heads/dev:refs/heads/dev
[[ $("${git_safe[@]}" --git-dir="$verify_git" rev-parse refs/heads/dev) == "$authorized_sha" ]]
[[ $("${git_safe[@]}" --git-dir="$verify_git" rev-parse "refs/heads/dev^{commit}") == "$authorized_sha" ]]
expected_tree=$("${git_safe[@]}" --git-dir="$verify_git" rev-parse "$authorized_sha^{tree}")

install -d -o root -g root -m 0755 "$root" "$root/releases"
install -d -o root -g root -m 0755 /usr/local/libexec/noetic-dev
if [[ ! -d $release ]]; then
  install -d -o root -g root -m 0755 "$release"
  "${git_safe[@]}" --git-dir="$verify_git" archive "$authorized_sha" | /usr/bin/tar -x -C "$release"
fi
[[ -z $(/usr/bin/find "$release" -type l -print -quit) ]]
[[ -f $release/deploy/noetic-dev-promote-main && ! -L $release/deploy/noetic-dev-promote-main ]]
[[ -f $release/scripts/governance/promote_main.py && ! -L $release/scripts/governance/promote_main.py ]]
actual_tree=$(
  GIT_INDEX_FILE="$verify_git/index" "${git_safe[@]}" \
    --git-dir="$verify_git" --work-tree="$release" add -A >/dev/null &&
  GIT_INDEX_FILE="$verify_git/index" "${git_safe[@]}" \
    --git-dir="$verify_git" --work-tree="$release" write-tree
)
[[ $actual_tree == "$expected_tree" ]]
chown -R root:root "$release"
chmod -R go-w "$release"
install -o root -g root -m 0755 \
  "$release/deploy/noetic-dev-promote-main" \
  /usr/local/libexec/noetic-dev/promote-main
ln -sfn "$release" "$root/current.new"
mv -Tf "$root/current.new" "$root/current"
