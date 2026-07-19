#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 || $# -ne 2 ]]; then
  echo "usage: sudo bash $0 NOETIC_SOURCE AUTHORIZED_DEV_SHA" >&2
  exit 2
fi

source_root=$1
authorized_sha=$2
root=/opt/noetic-dev-main-publisher
release=$root/releases/$authorized_sha

[[ $authorized_sha =~ ^[0-9a-f]{40}$ ]]
[[ $(/usr/bin/git -C "$source_root" rev-parse "$authorized_sha^{commit}") == "$authorized_sha" ]]

install -d -o root -g root -m 0755 "$root" "$root/releases"
install -d -o root -g root -m 0755 /usr/local/libexec/noetic-dev
if [[ ! -d $release ]]; then
  install -d -o root -g root -m 0755 "$release"
  /usr/bin/git -C "$source_root" archive "$authorized_sha" | /usr/bin/tar -x -C "$release"
fi
chown -R root:root "$release"
chmod -R go-w "$release"
install -o root -g root -m 0755 \
  "$release/deploy/noetic-dev-promote-main" \
  /usr/local/libexec/noetic-dev/promote-main
ln -sfn "$release" "$root/current.new"
mv -Tf "$root/current.new" "$root/current"
