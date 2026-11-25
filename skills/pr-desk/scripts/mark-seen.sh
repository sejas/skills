#!/usr/bin/env bash
# pr-desk mark-seen: after a run is reported, record every PR from last-gather.json
# (and optionally GHE rows) as seen, so the next run reports deltas only.
# PRs no longer open are pruned. Run it only after the report is shown.
# Usage: mark-seen.sh [ghe.json]
#   ghe.json: array of {key:"ghe:<owner/repo>#<n>", kind:"incoming|mine", title, url,
#             head, last_activity, ci, decision, mergeable}
set -euo pipefail
source "$(dirname "$0")/lib.sh"
GATHER="$STATE_DIR/last-gather.json"
[[ -s "$GATHER" ]] || { echo "pr-desk: run gather.sh first" >&2; exit 1; }
GHE_FILE="${1:-}"
GHE_JSON='[]'
if [[ -n "$GHE_FILE" ]]; then GHE_JSON=$(jq -c '.' "$GHE_FILE"); fi

jq --slurpfile g "$GATHER" --argjson ghe "$GHE_JSON" '
  ($g[0]) as $g
  | def row($kind): {(.key): {kind: $kind, title, url, head, last_activity, ci, decision, mergeable, seen_at: $g.generated_at}};
  {
    last_run: $g.generated_at,
    prs: (
      ([ $g.incoming[] | row("incoming") ] + [ $g.mine[] | row("mine") ]
       + [ $ghe[] | {(.key): (del(.key) + {seen_at: $g.generated_at})} ]) | add // {}
    )
  }
' "$STATE" > "$STATE.tmp"

# A partial gather (some github.com call failed) must not prune: overlay, keep the rest.
if [[ $(jq -r '.partial // false' "$GATHER") == true ]]; then
  jq --slurpfile old "$STATE" '.prs = ($old[0].prs + .prs) | .last_run = $old[0].last_run' "$STATE.tmp" > "$STATE.tmp2" && mv "$STATE.tmp2" "$STATE.tmp"
  echo "pr-desk: partial gather, nothing pruned" >&2
# Keep previous ghe:* entries when no GHE file was given (source unreachable this run).
elif [[ -z "$GHE_FILE" ]]; then
  jq --slurpfile old "$STATE" '.prs += ($old[0].prs | with_entries(select(.key | startswith("ghe:"))))' \
    "$STATE.tmp" > "$STATE.tmp2" && mv "$STATE.tmp2" "$STATE.tmp"
fi
mv "$STATE.tmp" "$STATE"
jq -r '"pr-desk state: \(.prs | length) PRs seen, last_run \(.last_run)"' "$STATE"
