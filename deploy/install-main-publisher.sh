#!/usr/bin/bash -p
if [[ $- != *p* || ( ${BASH_SOURCE[0]} != "$0" && ( $EUID -eq 0 || ${NOETIC_INSTALLER_TEST_MODE:-} != 1 ) ) ]]; then
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
PATH=/usr/bin:/bin
unset BASH_ENV ENV CDPATH GLOBIGNORE TMPDIR TMP TEMP NOETIC_INSTALLER_TEST_MODE
umask 077

stage0=/usr/local/sbin/noetic-dev-install-main-publisher
root=/opt/noetic-dev-main-publisher
canonical_remote=https://github.com/somebloke1/noetic-dev.git
verifier=/usr/local/libexec/noetic-dev/verify-delivery-attestation
launcher=/usr/local/libexec/noetic-dev/promote-main
publisher_key=/etc/noetic-dev/main-publisher/deploy-key
install_owner=0
install_group=0
git_executable=/usr/bin/git
trust_anchor=/
installation_lock=/run/noetic-dev-main-publisher/install.lock

trusted_executable_path() {
  local current=$1 mode owner
  while true; do
    [[ ! -L $current ]]
    owner=$(/usr/bin/stat -c %u "$current")
    mode=$((8#$(/usr/bin/stat -c %a "$current")))
    [[ $owner -eq 0 || $owner -eq $install_owner ]]
    (( (mode & 8#022) == 0 ))
    if [[ $current == "$1" ]]; then
      [[ -f $current && -x $current ]]
    else
      [[ -d $current ]]
    fi
    [[ $current == "$trust_anchor" || $current == / ]] && break
    current=$(/usr/bin/dirname "$current")
  done
}

trusted_private_key_path() {
  local current=$1 mode owner size
  while true; do
    [[ ! -L $current ]]
    owner=$(/usr/bin/stat -c %u "$current")
    mode=$((8#$(/usr/bin/stat -c %a "$current")))
    [[ $owner -eq 0 || $owner -eq $install_owner ]]
    (( (mode & 8#022) == 0 ))
    if [[ $current == "$1" ]]; then
      [[ -f $current && $mode -eq 8#400 ]]
      size=$(/usr/bin/stat -c %s "$current")
      (( size > 0 && size <= 16384 ))
    else
      [[ -d $current ]]
    fi
    [[ $current == "$trust_anchor" || $current == / ]] && break
    current=$(/usr/bin/dirname "$current")
  done
}

trusted_directory_path() {
  local current=$1 mode owner
  while true; do
    [[ ! -L $current ]]
    owner=$(/usr/bin/stat -c %u "$current")
    mode=$((8#$(/usr/bin/stat -c %a "$current")))
    [[ ( $owner -eq 0 || $owner -eq $install_owner ) && -d $current ]]
    (( (mode & 8#022) == 0 ))
    [[ $current == "$trust_anchor" || $current == / ]] && break
    current=$(/usr/bin/dirname "$current")
  done
}

trusted_or_absent_directory_path() {
  local current=$1
  while [[ ! -e $current && ! -L $current ]]; do
    [[ $current != "$trust_anchor" && $current != / ]]
    current=$(/usr/bin/dirname "$current")
  done
  trusted_directory_path "$current"
}

sha256_file() {
  /usr/bin/sha256sum "$1" | /usr/bin/cut -d ' ' -f 1
}

install_main_publisher() (
local policy_sha=$1
local authorized_sha=$2
local authorization_receipt=$3
local release=$root/policy-releases/$policy_sha/$authorized_sha
local launcher_parent current_new launcher_staging
local release_created=false current_new_created=false installation_complete=false
local lock_parent lock_owner lock_mode installation_lock_fd

[[ $policy_sha =~ ^[0-9a-f]{40}$ ]]
[[ $authorized_sha =~ ^[0-9a-f]{40}$ ]]
[[ $policy_sha != "$authorized_sha" ]]
[[ -f $authorization_receipt && ! -L $authorization_receipt ]]
[[ $(/usr/bin/stat -c %s "$authorization_receipt") -le 1048576 ]]
trusted_executable_path "$stage0"
trusted_executable_path /usr/bin/bash
trusted_executable_path "$verifier"
trusted_private_key_path "$publisher_key"
/usr/bin/env -i PATH=/usr/bin:/bin HOME=/root \
  /usr/bin/ssh-keygen -y -P '' -f "$publisher_key" </dev/null >/dev/null

git_safe=(/usr/bin/env -i PATH=/usr/bin:/bin HOME=/root GIT_NO_REPLACE_OBJECTS=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 "$git_executable" --no-replace-objects)
verify_git=$(/usr/bin/mktemp -d)
installation_staging=$(/usr/bin/mktemp -d)
staging=$installation_staging/repository
/usr/bin/install -d -o "$install_owner" -g "$install_group" -m 0700 "$staging"
claims_file=$(/usr/bin/mktemp)
installation_file=$(/usr/bin/mktemp)
receipt_snapshot=$(/usr/bin/mktemp)
cleanup_installation() {
  local status=$?
  /usr/bin/rm -rf "$verify_git" "$installation_staging" "$claims_file" \
    "$installation_file" "$receipt_snapshot"
  [[ -z ${launcher_staging:-} ]] || /usr/bin/rm -f "$launcher_staging"
  [[ $current_new_created == false ]] || /usr/bin/rm -f "$current_new"
  if [[ $release_created == true && $installation_complete == false ]]; then
    /usr/bin/rm -rf -- "$release"
  fi
  return "$status"
}
trap cleanup_installation EXIT
/usr/bin/install -o "$install_owner" -g "$install_group" -m 0600 "$authorization_receipt" "$receipt_snapshot"
[[ $(/usr/bin/stat -c %s "$receipt_snapshot") -le 1048576 ]]
"${git_safe[@]}" --git-dir="$verify_git" init --bare --quiet
"${git_safe[@]}" --git-dir="$verify_git" fetch --no-tags \
  "$canonical_remote" refs/heads/dev:refs/heads/dev
[[ $("${git_safe[@]}" --git-dir="$verify_git" rev-parse refs/heads/dev) == "$authorized_sha" ]]
[[ $("${git_safe[@]}" --git-dir="$verify_git" rev-parse "refs/heads/dev^{commit}") == "$authorized_sha" ]]
"${git_safe[@]}" --git-dir="$verify_git" cat-file -e "$policy_sha^{commit}"
"${git_safe[@]}" --git-dir="$verify_git" merge-base --is-ancestor "$policy_sha" "$authorized_sha"
policy_tree=$("${git_safe[@]}" --git-dir="$verify_git" rev-parse "$policy_sha^{tree}")
candidate_tree=$("${git_safe[@]}" --git-dir="$verify_git" rev-parse "$authorized_sha^{tree}")

# Extract only the separately protected policy ancestor. Candidate bytes are never installed.
"${git_safe[@]}" --git-dir="$verify_git" archive "$policy_sha" | /usr/bin/tar -x -C "$staging"
[[ -z $(/usr/bin/find "$staging" -type l -print -quit) ]]
critical_files=(
  deploy/install-main-publisher.sh
  deploy/noetic-dev-promote-main
  scripts/governance/promote_main.py
  scripts/governance/check_delivery_gate.py
  scripts/governance/check_evidence_manifest.py
  scripts/governance/hash_tree.py
  scripts/governance/json_schema.py
  scripts/governance/route_evidence.py
)
for relative in "${critical_files[@]}"; do
  [[ -f $staging/$relative && ! -L $staging/$relative ]]
done
GIT_INDEX_FILE="$verify_git/index" "${git_safe[@]}" \
  --git-dir="$verify_git" read-tree --empty
actual_tree=$(
  GIT_INDEX_FILE="$verify_git/index" "${git_safe[@]}" \
    --git-dir="$verify_git" --work-tree="$staging" add -A >/dev/null &&
  GIT_INDEX_FILE="$verify_git/index" "${git_safe[@]}" \
    --git-dir="$verify_git" --work-tree="$staging" write-tree
)
[[ $actual_tree == "$policy_tree" ]]

installer_sha256=$(sha256_file "$stage0")
verifier_sha256=$(sha256_file "$verifier")
receipt_sha256=$(sha256_file "$receipt_snapshot")
[[ $(sha256_file "$staging/deploy/install-main-publisher.sh") == "$installer_sha256" ]]
policy_digest_args=()
for relative in "${critical_files[@]}"; do
  policy_digest_args+=("$relative" "$(sha256_file "$staging/$relative")")
done

challenge=$(
  /usr/bin/env -i PATH=/usr/bin:/bin HOME=/root /usr/bin/python3 -I -c '
import json, sys
claims_path, receipt_path = sys.argv[1:3]
policy_sha, candidate_sha, policy_tree, candidate_tree = sys.argv[3:7]
installer_path, installer_digest, verifier_path, verifier_digest = sys.argv[7:11]
digest_fields = sys.argv[11:]
if len(digest_fields) % 2:
    raise SystemExit("invalid policy digest arguments")
policy_files = dict(zip(digest_fields[::2], digest_fields[1::2]))
claims = {
    "candidate_sha": candidate_sha,
    "candidate_source_ref": "refs/heads/dev",
    "candidate_tree_sha": candidate_tree,
    "installer": {"path": installer_path, "sha256": installer_digest},
    "policy_files_sha256": policy_files,
    "policy_sha": policy_sha,
    "policy_source_ref": "refs/heads/dev",
    "policy_tree_sha": policy_tree,
    "purpose": "install-main-publisher",
    "repository": "somebloke1/noetic-dev",
    "verifier": {"path": verifier_path, "sha256": verifier_digest},
}
with open(claims_path, "w", encoding="utf-8") as target:
    json.dump(claims, target, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
with open(receipt_path, "r", encoding="utf-8") as source:
    receipt = json.load(source)
challenge = {"expected_claims": claims, "receipt": receipt, "schema_version": "1"}
sys.stdout.write(json.dumps(challenge, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
' "$claims_file" "$receipt_snapshot" "$policy_sha" "$authorized_sha" \
    "$policy_tree" "$candidate_tree" "$stage0" "$installer_sha256" \
    "$verifier" "$verifier_sha256" "${policy_digest_args[@]}"
)
/usr/bin/printf '%s' "$challenge" | /usr/bin/env -i PATH=/usr/bin:/bin "$verifier"

/usr/bin/env -i PATH=/usr/bin:/bin HOME=/root /usr/bin/python3 -I -c '
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as source:
    claims = json.load(source)
installation = {
    "authorization_receipt_sha256": sys.argv[3],
    "expected_claims": claims,
    "schema_version": "1",
}
with open(sys.argv[2], "w", encoding="utf-8") as target:
    json.dump(installation, target, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
' "$claims_file" "$installation_file" "$receipt_sha256"

lock_parent=$(/usr/bin/dirname "$installation_lock")
trusted_or_absent_directory_path "$lock_parent"
/usr/bin/install -d -o "$install_owner" -g "$install_group" -m 0755 "$lock_parent"
trusted_directory_path "$lock_parent"
if [[ ! -e $installation_lock && ! -L $installation_lock ]]; then
  ( set -o noclobber; : > "$installation_lock" ) 2>/dev/null || true
fi
[[ -f $installation_lock && ! -L $installation_lock ]]
lock_owner=$(/usr/bin/stat -c %u "$installation_lock")
lock_mode=$((8#$(/usr/bin/stat -c %a "$installation_lock")))
[[ $lock_owner -eq 0 || $lock_owner -eq $install_owner ]]
(( (lock_mode & 8#022) == 0 ))
exec {installation_lock_fd}<>"$installation_lock"
/usr/bin/flock -x "$installation_lock_fd"
launcher_parent=$(/usr/bin/dirname "$launcher")
trusted_or_absent_directory_path "$launcher_parent"
/usr/bin/install -d -o "$install_owner" -g "$install_group" -m 0755 "$launcher_parent"
trusted_directory_path "$launcher_parent"
if [[ -e $launcher || -L $launcher ]]; then
  [[ -f $launcher && ! -L $launcher ]]
fi
current_new=$root/current.new
[[ ! -e $current_new && ! -L $current_new ]]
[[ ! -e $root/current || -L $root/current ]]
trusted_or_absent_directory_path "$root"
trusted_or_absent_directory_path "$root/policy-releases"
trusted_or_absent_directory_path "$root/policy-releases/$policy_sha"
trusted_or_absent_directory_path "$release"
/usr/bin/install -d -o "$install_owner" -g "$install_group" -m 0755 "$root" "$root/policy-releases" \
  "$root/policy-releases/$policy_sha"
trusted_directory_path "$root"
trusted_directory_path "$root/policy-releases"
trusted_directory_path "$root/policy-releases/$policy_sha"
[[ ! -e $release && ! -L $release ]]
launcher_staging=$(/usr/bin/mktemp "$launcher_parent/.promote-main.XXXXXX")
/usr/bin/install -o "$install_owner" -g "$install_group" -m 0700 \
  "$installation_staging/repository/deploy/noetic-dev-promote-main" \
  "$launcher_staging"
/usr/bin/ln -sT "$release" "$current_new"
current_new_created=true
/usr/bin/install -o "$install_owner" -g "$install_group" -m 0600 "$installation_file" "$installation_staging/publisher-installation.json"
/usr/bin/install -o "$install_owner" -g "$install_group" -m 0600 "$receipt_snapshot" "$installation_staging/publisher-installation-receipt.json"
/usr/bin/chown -R "$install_owner:$install_group" "$installation_staging"
/usr/bin/chmod -R go-w "$installation_staging"
trusted_directory_path "$root/policy-releases/$policy_sha"
/usr/bin/mv "$installation_staging" "$release"
release_created=true
trusted_directory_path "$release"
trusted_directory_path "$release/repository"
trusted_directory_path "$root"
/usr/bin/mv -fT "$launcher_staging" "$launcher"
launcher_staging=
/usr/bin/mv -Tf "$current_new" "$root/current"
current_new_created=false
installation_complete=true
)

main() {
  if [[ $- != *p* || $EUID -ne 0 || $# -ne 3 || $(/usr/bin/readlink -f "$0") != "$stage0" ]]; then
    echo "usage: sudo $stage0 PROTECTED_POLICY_SHA AUTHORIZED_DEV_SHA PROTECTED_AUTHORIZATION_RECEIPT_JSON" >&2
    exit 2
  fi
  install_main_publisher "$@"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
