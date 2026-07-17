#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 || $# -ne 3 ]]; then
  echo "usage: sudo $0 NOETIC_SOURCE NOETIC_SHA GENUS_SOURCE" >&2
  exit 2
fi

noetic_source=$1
noetic_sha=$2
genus_source=$3
genus_sha=f2b839b0cfc737c4c1f0a46d3d519d414529545c
root=/opt/noetic-dev-agent-review
release=$root/releases/$noetic_sha
router_release=$root/genus-router/$genus_sha

[[ $noetic_sha =~ ^[0-9a-f]{40}$ ]]
[[ $(git -C "$noetic_source" rev-parse "$noetic_sha^{commit}") == "$noetic_sha" ]]
[[ $(git -C "$genus_source" rev-parse "$genus_sha^{commit}") == "$genus_sha" ]]

genus_archive=$(mktemp -d)
trap 'rm -rf "$genus_archive"' EXIT
git -C "$genus_source" archive "$genus_sha" | tar -x -C "$genus_archive"

getent group noetic-agent-review >/dev/null || groupadd --system noetic-agent-review
id noetic-review-broker >/dev/null 2>&1 || useradd --system --gid noetic-agent-review --home /var/lib/noetic-agent-review --shell /usr/sbin/nologin noetic-review-broker
install -d -o root -g root -m 0755 "$root" "$root/releases" "$root/genus-router" "$root/runtime"
install -d -o noetic-review-broker -g noetic-agent-review -m 0750 /var/lib/noetic-agent-review

if [[ ! -d $release ]]; then
  install -d -o root -g root -m 0755 "$release"
  git -C "$noetic_source" archive "$noetic_sha" | tar -x -C "$release"
fi

if [[ ! -x $root/runtime/mcp/bin/python3 ]]; then
  python3 -m venv "$root/runtime/mcp"
fi
"$root/runtime/mcp/bin/python3" -m pip install --disable-pip-version-check -r "$release/deploy/requirements-agent-review.txt"

if [[ ! -x $router_release/bin/genus-router ]]; then
  python3 -m venv "$router_release"
  "$router_release/bin/python3" -m pip install --disable-pip-version-check "$genus_archive"
fi
install -d -o root -g root -m 0755 "$router_release/config"
install -d -o noetic-review-broker -g noetic-agent-review -m 0750 "$router_release/state"
install -o root -g root -m 0444 "$genus_archive/config/router.yaml" "$router_release/config/router.yaml"
install -o root -g root -m 0444 "$genus_archive/config/genus_models.csv" "$router_release/config/genus_models.csv"

command_sha=$(sha256sum "$router_release/bin/genus-router" | cut -d ' ' -f 1)
config_sha=$(sha256sum "$router_release/config/router.yaml" | cut -d ' ' -f 1)
table_sha=$(sha256sum "$router_release/config/genus_models.csv" | cut -d ' ' -f 1)
printf '{"command_sha256":"%s","component_sha":"%s","config_sha256":"%s","genus_table_sha256":"%s"}\n' \
  "$command_sha" "$genus_sha" "$config_sha" "$table_sha" >"$router_release/component-manifest.json"
chown root:root "$router_release/component-manifest.json"
chmod 0444 "$router_release/component-manifest.json"
chown -R root:root "$release" "$root/runtime/mcp" "$router_release/bin" "$router_release/lib" "$router_release/include" "$router_release/config"
chmod -R go-w "$release" "$root/runtime/mcp" "$router_release/bin" "$router_release/lib" "$router_release/include" "$router_release/config"

ln -sfn "$release" "$root/current.new"
mv -Tf "$root/current.new" "$root/current"
install -o root -g root -m 0644 "$release/deploy/systemd/noetic-dev-agent-review-broker.service" /etc/systemd/system/noetic-dev-agent-review-broker.service

if [[ -n ${LITELLM_API_KEY:-} ]]; then
  install -d -o root -g root -m 0700 /etc/credstore
  umask 0177
  printf '%s' "$LITELLM_API_KEY" >/etc/credstore/litellm_api_key
fi
[[ -s /etc/credstore/litellm_api_key ]]

systemctl daemon-reload
systemctl enable --now noetic-dev-agent-review-broker.service
