#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 077

if [[ $EUID -ne 0 || $# -ne 3 ]]; then
  echo "usage: sudo $0 NOETIC_SOURCE NOETIC_SHA OPENCODE_BINARY" >&2
  exit 2
fi
[[ -z ${BASH_ENV:-}${ENV:-}${LD_PRELOAD:-}${LD_LIBRARY_PATH:-} ]]

noetic_source=$1
noetic_sha=$2
opencode_source=$3
component_sha=f2b839b0cfc737c4c1f0a46d3d519d414529545c
opencode_sha=373af49ceba30c1b64e964463a64f8065103f942f240933a955f6c461e1a67f6
root=/opt/noetic-dev-agent-review
runtime=$root/opencode-spike-runtime
opencode_runtime=$root/opencode/1.17.20
spike_home=/var/lib/noetic-opencode-spike
state=$spike_home/state
router_state=$spike_home/router-state
router=$root/genus-router/$component_sha

[[ $noetic_sha =~ ^[0-9a-f]{40}$ ]]
[[ $(git -C "$noetic_source" rev-parse "$noetic_sha^{commit}") == "$noetic_sha" ]]
[[ -f $opencode_source && ! -L $opencode_source ]]
[[ -x /usr/bin/bwrap && -x /usr/bin/python3 && -x /usr/sbin/ip ]]
[[ -x $router/bin/python3 && -x $router/bin/genus-router && -f $router/config/router.yaml ]]
[[ -f $router/component-manifest.json ]]
[[ -f /etc/credstore/litellm_api_key && ! -L /etc/credstore/litellm_api_key && -s /etc/credstore/litellm_api_key ]]
[[ $(stat -c %U /etc/credstore/litellm_api_key) == root ]]
credential_mode=$(stat -c %a /etc/credstore/litellm_api_key)
[[ $credential_mode == 400 || $credential_mode == 600 ]]

staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
archive=$staging/repository
staged_opencode=$staging/opencode
install -d -o root -g root -m 0700 "$archive"
install -o root -g root -m 0555 "$opencode_source" "$staged_opencode"
[[ $(sha256sum "$staged_opencode" | cut -d ' ' -f 1) == "$opencode_sha" ]]
version_home=$staging/version-home
install -d -o root -g root -m 0700 "$version_home"
[[ $(env -i HOME="$version_home" XDG_CONFIG_HOME="$version_home/config" XDG_DATA_HOME="$version_home/data" XDG_CACHE_HOME="$version_home/cache" XDG_STATE_HOME="$version_home/state" PATH=/usr/bin:/bin "$staged_opencode" --version) == 1.17.20 ]]
git -C "$noetic_source" archive "$noetic_sha" | tar -x -C "$archive"

for artifact in route.claim route.json execute.claim result.json outcome.claim; do
  [[ ! -e $state/$artifact ]]
done
for artifact in decisions.jsonl outcomes.jsonl; do
  [[ ! -e $router_state/$artifact ]]
done
[[ ! -L $root && ! -L $runtime && ! -L $opencode_runtime && ! -L $spike_home && ! -L $state && ! -L $router_state ]]

getent group noetic-opencode-spike >/dev/null || groupadd --system noetic-opencode-spike
id noetic-opencode-spike >/dev/null 2>&1 || useradd --system --gid noetic-opencode-spike --home "$spike_home" --no-create-home --shell /usr/sbin/nologin noetic-opencode-spike
[[ $(id -gn noetic-opencode-spike) == noetic-opencode-spike ]]
[[ $(getent passwd noetic-opencode-spike | cut -d: -f6) == "$spike_home" ]]
[[ $(getent passwd noetic-opencode-spike | cut -d: -f7) == /usr/sbin/nologin ]]

install -d -o root -g root -m 0755 "$root" "$runtime" "$root/opencode" "$opencode_runtime"
install -d -o noetic-opencode-spike -g noetic-opencode-spike -m 0700 "$spike_home" "$state" "$router_state"
install -o root -g root -m 0555 "$archive/scripts/governance/run_opencode_spike.py" "$runtime/run_opencode_spike.py"
install -o root -g root -m 0444 "$archive/scripts/governance/genus_router_mcp.py" "$runtime/genus_router_mcp.py"
install -o root -g root -m 0555 "$staged_opencode" "$opencode_runtime/opencode"
install -o root -g root -m 0700 "$archive/deploy/run-opencode-spike.sh" /usr/local/sbin/noetic-dev-opencode-spike

for unit in route execute outcome; do
  install -o root -g root -m 0644 \
    "$archive/deploy/systemd/noetic-dev-opencode-spike-$unit.service" \
    "/etc/systemd/system/noetic-dev-opencode-spike-$unit.service"
done

[[ $(sha256sum "$opencode_runtime/opencode" | cut -d ' ' -f 1) == "$opencode_sha" ]]
controller_sha=$(sha256sum "$runtime/run_opencode_spike.py" | cut -d ' ' -f 1)
router_client_sha=$(sha256sum "$runtime/genus_router_mcp.py" | cut -d ' ' -f 1)
printf '{"component_sha":"%s","controller_sha256":"%s","noetic_sha":"%s","opencode_sha256":"%s","opencode_version":"1.17.20","router_client_sha256":"%s"}\n' \
  "$component_sha" "$controller_sha" "$noetic_sha" "$opencode_sha" "$router_client_sha" >"$runtime/manifest.json"
chown root:root "$runtime/manifest.json"
chmod 0444 "$runtime/manifest.json"

systemctl daemon-reload
printf '%s\n' "Installed inert OpenCode spike units; no phase was started or enabled."
