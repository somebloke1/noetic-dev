#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/bin:/bin

if [[ $EUID -ne 0 || $# -ne 2 ]]; then
  echo "usage: sudo bash $0 NOETIC_SOURCE AUTHORIZED_DEV_SHA" >&2
  exit 2
fi

source_root=$1
authorized_sha=$2
root=/opt/noetic-dev-main-publisher
release=$root/releases/$authorized_sha

[[ $authorized_sha =~ ^[0-9a-f]{40}$ ]]
git_safe=(/usr/bin/env -u GIT_DIR -u GIT_WORK_TREE -u GIT_OBJECT_DIRECTORY -u GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_NO_REPLACE_OBJECTS=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null /usr/bin/git --no-replace-objects)
source_objects=$("${git_safe[@]}" -C "$source_root" rev-parse --path-format=absolute --git-path objects)
source_objects=$(/usr/bin/realpath "$source_objects")
[[ -d $source_objects && $source_objects != *$'\n'* ]]
verify_git=$(/usr/bin/mktemp -d)
trap '/usr/bin/rm -rf "$verify_git"' EXIT
"${git_safe[@]}" --git-dir="$verify_git" init --bare --quiet
/usr/bin/printf '%s\n' "$source_objects" >"$verify_git/objects/info/alternates"
[[ $("${git_safe[@]}" --git-dir="$verify_git" rev-parse "$authorized_sha^{commit}") == "$authorized_sha" ]]
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
