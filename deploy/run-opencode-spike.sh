#!/bin/sh
set -eu

test "$(id -u)" -eq 0 || {
    printf '%s\n' "OpenCode spike orchestration requires root" >&2
    exit 2
}
test "$#" -eq 0 || exit 2
test -z "${BASH_ENV-}${ENV-}${LD_PRELOAD-}${LD_LIBRARY_PATH-}" || exit 2
test -z "${CREDENTIALS_DIRECTORY-}${LITELLM_API_KEY-}${OPENAI_API_KEY-}${ANTHROPIC_API_KEY-}${GITHUB_TOKEN-}${GH_TOKEN-}${USER_PROVIDED_PASSWORD-}" || {
    printf '%s\n' "refusing ambient credentials in the orchestrator" >&2
    exit 2
}
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

state=/var/lib/noetic-opencode-spike/state
execute_state=/var/lib/noetic-opencode-spike/execute-state
router_state=/var/lib/noetic-opencode-spike/non-evidence-router-state
route_unit=noetic-dev-opencode-spike-route.service
execute_unit=noetic-dev-opencode-spike-execute.service
outcome_unit=noetic-dev-opencode-spike-outcome.service

exec 9>/run/lock/noetic-dev-opencode-spike.lock
/usr/bin/flock -n 9 || {
    printf '%s\n' "OpenCode spike orchestration is already active" >&2
    exit 1
}

for artifact in route.claim route.json execute.claim result.json outcome.claim; do
    test ! -e "$state/$artifact" || {
        printf '%s\n' "OpenCode spike is irreversible; existing state blocks replay" >&2
        exit 1
    }
done
for artifact in route.json execute.claim result.json; do
    test ! -e "$execute_state/$artifact" || {
        printf '%s\n' "OpenCode spike execute state blocks replay" >&2
        exit 1
    }
done
for artifact in decisions.jsonl outcomes.jsonl; do
    test -f "$router_state/$artifact" && test ! -s "$router_state/$artifact" || {
        printf '%s\n' "OpenCode spike router state blocks replay" >&2
        exit 1
    }
done

/usr/bin/systemctl reset-failed "$route_unit" "$execute_unit" "$outcome_unit"
/usr/bin/systemctl start "$route_unit"
test -f "$state/route.claim"
test -f "$state/route.json"
/usr/bin/install -o llm-svc -g llm-svc -m 0600 "$state/route.json" "$execute_state/route.json"
/usr/bin/cmp -s "$state/route.json" "$execute_state/route.json"

execute_status=0
/usr/bin/systemctl start "$execute_unit" || execute_status=$?
test -f "$execute_state/result.json"
/usr/bin/install -o noetic-opencode-spike -g noetic-opencode-spike -m 0600 "$execute_state/result.json" "$state/result.json"
/usr/bin/cmp -s "$execute_state/result.json" "$state/result.json"
if test -f "$execute_state/execute.claim"; then
    /usr/bin/install -o noetic-opencode-spike -g noetic-opencode-spike -m 0600 "$execute_state/execute.claim" "$state/execute.claim"
    /usr/bin/cmp -s "$execute_state/execute.claim" "$state/execute.claim"
fi

outcome_status=0
/usr/bin/systemctl start "$outcome_unit" || outcome_status=$?

if test "$execute_status" -ne 0 || test "$outcome_status" -ne 0; then
    exit 1
fi
