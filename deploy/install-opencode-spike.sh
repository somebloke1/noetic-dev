#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 077

if [[ $EUID -ne 0 || $# -ne 4 ]]; then
  echo "usage: sudo $0 NOETIC_SOURCE NOETIC_SHA OPENCODE_BINARY REVIEW_RUN_ID" >&2
  exit 2
fi
[[ -z ${BASH_ENV:-}${ENV:-}${LD_PRELOAD:-}${LD_LIBRARY_PATH:-} ]]

noetic_source=$1
noetic_sha=$2
opencode_source=$3
review_run_id=$4
component_sha=f2b839b0cfc737c4c1f0a46d3d519d414529545c
opencode_sha=373af49ceba30c1b64e964463a64f8065103f942f240933a955f6c461e1a67f6
bwrap_sha=52231e1caf55bcbc667b269f49c63599a6f7db4767ae6a039580d0ff853db712
root=/opt/noetic-dev-agent-review
runtime=$root/opencode-spike-runtime
opencode_runtime=$root/opencode/1.17.20
spike_home=/var/lib/noetic-opencode-spike
state=$spike_home/state
execute_state=$spike_home/execute-state
handoff_state=$spike_home/handoff-state
router_state=$spike_home/non-evidence-router-state
router=$root/genus-router/$component_sha
litellm_unit=/etc/systemd/system/litellm.service
litellm_launcher=/opt/litellm/.venv/bin/litellm
litellm_config=/etc/litellm/config.yaml
attestor=$root/current/scripts/governance/route_attestation.py
repository=https://github.com/somebloke1/noetic-dev.git

[[ $noetic_sha =~ ^[0-9a-f]{40}$ ]]
[[ $review_run_id =~ ^[1-9][0-9]*$ ]]
[[ $(git --no-replace-objects -C "$noetic_source" rev-parse "$noetic_sha^{commit}") == "$noetic_sha" ]]
[[ $(git -C "$noetic_source" remote get-url origin) == "$repository" ]]
[[ -f $opencode_source && ! -L $opencode_source ]]
[[ -x /usr/bin/bwrap && -x /usr/bin/python3 && -x /usr/bin/dd ]]
[[ $(sha256sum /usr/bin/bwrap | cut -d ' ' -f 1) == "$bwrap_sha" ]]
[[ -x $router/bin/python3 && -x $router/bin/genus-router && -f $router/config/router.yaml ]]
[[ -f $router/component-manifest.json ]]
[[ -f $litellm_unit && ! -L $litellm_unit && -x $litellm_launcher && ! -L $litellm_launcher && -f $litellm_config && ! -L $litellm_config ]]
[[ -f $attestor && ! -L $attestor && $(stat -c %U "$attestor") == root && $((8#$(stat -c %a "$attestor") & 8#022)) -eq 0 ]]
for artifact in "$litellm_unit" "$litellm_launcher" "$litellm_config"; do
  [[ $(stat -c %U "$artifact") == root ]]
  [[ $((8#$(stat -c %a "$artifact") & 8#022)) -eq 0 ]]
done
litellm_python=$(readlink -f /opt/litellm/.venv/bin/python)
[[ $litellm_python == /usr/bin/python3.12 && -x $litellm_python && ! -L $litellm_python ]]
[[ $(stat -c %U "$litellm_python") == root ]]
[[ $((8#$(stat -c %a "$litellm_python") & 8#022)) -eq 0 ]]
if find /opt/litellm/.venv -xdev \( -type f -o -type d \) \( ! -user root -o -perm /022 \) -print -quit | grep -q .; then
  printf '%s\n' "LiteLLM runtime contains an untrusted writable artifact" >&2
  exit 1
fi
systemctl is-active --quiet litellm.service
[[ -f /etc/credstore/litellm_api_key && ! -L /etc/credstore/litellm_api_key && -s /etc/credstore/litellm_api_key ]]
[[ $(stat -c %U /etc/credstore/litellm_api_key) == root ]]
credential_mode=$(stat -c %a /etc/credstore/litellm_api_key)
[[ $credential_mode == 400 || $credential_mode == 600 ]]

[[ -n ${SUDO_USER:-} && $SUDO_USER != root ]]
review_group=$(id -gn "$SUDO_USER")
attestation=$(mktemp -d)
staging=$(mktemp -d)
trap 'rm -rf "$attestation" "$staging"' EXIT
chown "$SUDO_USER:$review_group" "$attestation"
/usr/sbin/runuser -u "$SUDO_USER" -- /usr/bin/python3 -I "$attestor" --run-id "$review_run_id" --state-dir "$attestation"
receipt=$staging/protected-review-receipt.json
/usr/bin/dd if="$attestation/run-$review_run_id-attempt-1.json" of="$receipt" bs=262145 count=1 iflag=nofollow,nonblock,fullblock oflag=excl,nofollow conv=fsync status=none
chmod 0400 "$receipt"
archive=$staging/repository
staged_opencode=$staging/opencode
install -d -o root -g root -m 0700 "$archive"
install -o root -g root -m 0555 "$opencode_source" "$staged_opencode"
[[ $(sha256sum "$staged_opencode" | cut -d ' ' -f 1) == "$opencode_sha" ]]
version_home=$staging/version-home
install -d -o root -g root -m 0700 "$version_home"
[[ $(env -i HOME="$version_home" XDG_CONFIG_HOME="$version_home/config" XDG_DATA_HOME="$version_home/data" XDG_CACHE_HOME="$version_home/cache" XDG_STATE_HOME="$version_home/state" PATH=/usr/bin:/bin "$staged_opencode" --version) == 1.17.20 ]]
git --no-replace-objects -C "$noetic_source" archive "$noetic_sha" | tar -x -C "$archive"
router_identity=$(/usr/bin/python3 -I "$archive/scripts/governance/run_opencode_spike.py" verify-router \
  --genus-router-command "$router/bin/genus-router" \
  --genus-router-config "$router/config/router.yaml" \
  --genus-router-sha "$component_sha")
[[ $router_identity =~ ^[0-9a-f]{64}$ ]]

for artifact in route.claim route.json execute.claim result.json outcome.claim; do
  [[ ! -e $state/$artifact ]]
done
for artifact in execute.claim result.json; do
  [[ ! -e $execute_state/$artifact ]]
done
for artifact in route.json result.json; do
  [[ ! -e $handoff_state/$artifact ]]
done
for artifact in classification.json decisions.jsonl outcomes.jsonl; do
  [[ ! -e $router_state/$artifact ]]
done
[[ ! -L $root && ! -L $runtime && ! -L $opencode_runtime && ! -L $spike_home && ! -L $state && ! -L $execute_state && ! -L $handoff_state && ! -L $router_state ]]

getent group noetic-opencode-spike >/dev/null || groupadd --system noetic-opencode-spike
id noetic-opencode-spike >/dev/null 2>&1 || useradd --system --gid noetic-opencode-spike --home "$spike_home" --no-create-home --shell /usr/sbin/nologin noetic-opencode-spike
[[ $(id -gn noetic-opencode-spike) == noetic-opencode-spike ]]
[[ $(getent passwd noetic-opencode-spike | cut -d: -f6) == "$spike_home" ]]
[[ $(getent passwd noetic-opencode-spike | cut -d: -f7) == /usr/sbin/nologin ]]
[[ $(getent passwd llm-svc | cut -d: -f7) == /usr/sbin/nologin ]]

install -d -o root -g root -m 0755 "$root" "$runtime" "$root/opencode" "$opencode_runtime"
install -d -o root -g root -m 0755 "$spike_home"
install -d -o noetic-opencode-spike -g noetic-opencode-spike -m 0700 "$state"
install -d -o root -g root -m 0755 "$handoff_state"
install -d -o root -g root -m 0755 "$router_state"
printf '%s\n' '{"evidence_class":"non-evidence","policy_status":"contract-only","runtime_adapter_ready":false,"schema_version":"1","storage_scope":"isolated-spike-only"}' >"$router_state/classification.json"
chown root:root "$router_state/classification.json"
chmod 0444 "$router_state/classification.json"
for artifact in decisions.jsonl outcomes.jsonl; do
  install -o noetic-opencode-spike -g noetic-opencode-spike -m 0600 /dev/null "$router_state/$artifact"
done
install -d -o llm-svc -g llm-svc -m 0700 "$execute_state"
install -o root -g root -m 0555 "$archive/scripts/governance/run_opencode_spike.py" "$runtime/run_opencode_spike.py"
install -o root -g root -m 0444 "$archive/scripts/governance/genus_router_mcp.py" "$runtime/genus_router_mcp.py"
install -o root -g root -m 0444 "$receipt" "$runtime/protected-review-receipt.json"
install -o root -g root -m 0555 "$staged_opencode" "$opencode_runtime/opencode"
install -o root -g root -m 0700 "$archive/deploy/run-opencode-spike.sh" /usr/local/sbin/noetic-dev-opencode-spike

litellm_uid=$(id -u llm-svc)
litellm_gid=$(id -g llm-svc)
unit_sha=$(sha256sum "$litellm_unit" | cut -d ' ' -f 1)
launcher_sha=$(sha256sum "$litellm_launcher" | cut -d ' ' -f 1)
config_sha=$(sha256sum "$litellm_config" | cut -d ' ' -f 1)
python_sha=$(sha256sum "$litellm_python" | cut -d ' ' -f 1)
printf '{"cgroup":"/system.slice/litellm.service","cmdline":["/opt/litellm/.venv/bin/python","/opt/litellm/.venv/bin/litellm","--config","/etc/litellm/config.yaml","--host","0.0.0.0","--port","3333"],"config":"%s","config_sha256":"%s","gid":%s,"host":"172.22.10.160","launcher":"%s","launcher_sha256":"%s","port":3333,"python":"%s","python_sha256":"%s","schema_version":"1","service_unit":"%s","service_unit_sha256":"%s","uid":%s}\n' \
  "$litellm_config" "$config_sha" "$litellm_gid" "$litellm_launcher" "$launcher_sha" "$litellm_python" "$python_sha" "$litellm_unit" "$unit_sha" "$litellm_uid" \
  >"$runtime/litellm-peer-manifest.json"
chown root:root "$runtime/litellm-peer-manifest.json"
chmod 0444 "$runtime/litellm-peer-manifest.json"
peer_identity=$(/usr/bin/python3 -I "$runtime/run_opencode_spike.py" verify-peer)
[[ $peer_identity =~ ^[0-9a-f]{64}$ ]]

for unit in route execute outcome; do
  install -o root -g root -m 0644 \
    "$archive/deploy/systemd/noetic-dev-opencode-spike-$unit.service" \
    "/etc/systemd/system/noetic-dev-opencode-spike-$unit.service"
done

[[ $(sha256sum "$opencode_runtime/opencode" | cut -d ' ' -f 1) == "$opencode_sha" ]]
controller_sha=$(sha256sum "$runtime/run_opencode_spike.py" | cut -d ' ' -f 1)
router_client_sha=$(sha256sum "$runtime/genus_router_mcp.py" | cut -d ' ' -f 1)
peer_manifest_sha=$(sha256sum "$runtime/litellm-peer-manifest.json" | cut -d ' ' -f 1)
approval_sha=$(sha256sum "$runtime/protected-review-receipt.json" | cut -d ' ' -f 1)
printf '{"approval_sha256":"%s","bwrap_sha256":"%s","component_sha":"%s","controller_sha256":"%s","litellm_peer_identity_sha256":"%s","litellm_peer_manifest_sha256":"%s","noetic_sha":"%s","opencode_sha256":"%s","opencode_version":"1.17.20","repository":"somebloke1/noetic-dev","review_run_id":%s,"router_client_sha256":"%s","router_identity_sha256":"%s"}\n' \
  "$approval_sha" "$bwrap_sha" "$component_sha" "$controller_sha" "$peer_identity" "$peer_manifest_sha" "$noetic_sha" "$opencode_sha" "$review_run_id" "$router_client_sha" "$router_identity" >"$runtime/manifest.json"
chown root:root "$runtime/manifest.json"
chmod 0444 "$runtime/manifest.json"
/usr/bin/python3 -I "$runtime/run_opencode_spike.py" verify-runtime >/dev/null

systemctl daemon-reload
printf '%s\n' "Installed inert OpenCode spike units; no phase was started or enabled."
