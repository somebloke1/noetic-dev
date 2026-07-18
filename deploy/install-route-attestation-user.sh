#!/bin/sh
set -eu
test -z "${BASH_ENV-}${ENV-}${LD_PRELOAD-}${LD_LIBRARY_PATH-}" || exit 2
PATH=/usr/local/bin:/usr/bin:/bin
export PATH

test "$#" -eq 1
case $1 in
    ''|0|0*|*[!0-9]*) exit 2 ;;
esac
after_run_id=$1
test "$after_run_id" -gt 0
home=$(/usr/bin/python3 -I -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)')
user=$(id -un)
test "$(loginctl show-user "$user" --property=Linger --value)" = yes
release=/opt/noetic-dev-agent-review/current
state_dir=$home/.local/state/noetic-dev/route-attestations
unit_dir=$home/.config/systemd/user
config_dir=$home/.config/noetic-dev

test -x /usr/bin/gh
test -x /usr/bin/git
test -x /usr/bin/python3
test -f "$release/scripts/governance/route_attestation.py"
test -f "$release/deploy/systemd/user/noetic-dev-route-attestation.service"
test -f "$release/deploy/systemd/user/noetic-dev-route-attestation.timer"
env -i HOME="$home" GH_CONFIG_DIR="$home/.config/gh" PATH=/usr/local/bin:/usr/bin:/bin /usr/bin/gh auth status --hostname github.com >/dev/null

install -d -m 0700 "$state_dir"
install -d -m 0700 "$unit_dir"
install -d -m 0700 "$config_dir"
temporary=$(mktemp "$config_dir/.route-attestation.env.XXXXXX")
trap 'rm -f "$temporary"' EXIT
printf 'NOETIC_ROUTE_AFTER_RUN_ID=%s\n' "$after_run_id" >"$temporary"
chmod 0600 "$temporary"
mv "$temporary" "$config_dir/route-attestation.env"
trap - EXIT
install -m 0644 "$release/deploy/systemd/user/noetic-dev-route-attestation.service" "$unit_dir/noetic-dev-route-attestation.service"
install -m 0644 "$release/deploy/systemd/user/noetic-dev-route-attestation.timer" "$unit_dir/noetic-dev-route-attestation.timer"

systemctl --user daemon-reload
systemctl --user enable --now noetic-dev-route-attestation.timer
systemctl --user start noetic-dev-route-attestation.service
