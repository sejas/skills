#!/usr/bin/env bash
# pr-desk week: Monday / `week` section. Read-only. Needs a fresh last-gather.json.
# Prints JSON: merged/closed last 7 days (mine), PRs I reviewed, PRs of mine waiting
# on others > waiting_nudge_days, and the oldest review debt.
# Usage: week.sh [days=7]
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/lib.sh"
DAYS="${1:-7}"
SINCE=$(days_ago "$DAYS")
NUDGE=$(cfg .waiting_nudge_days)
GATHER="$STATE_DIR/last-gather.json"
[[ -s "$GATHER" ]] || { echo "pr-desk: run gather.sh first" >&2; exit 1; }

Q='query($q:String!,$endCursor:String){search(query:$q,type:ISSUE,first:50,after:$endCursor){
  pageInfo{hasNextPage endCursor}
  nodes{... on PullRequest{number title url state createdAt mergedAt closedAt author{login} repository{nameWithOwner}}}}}'
list() { # query -> JSON array, or {"error":..} on failure
  local out
  if out=$(gh api graphql --paginate -f query="$Q" -F q="$1" --jq '.data.search.nodes[]' 2>&1); then
    jq -s 'map({key: "\(.repository.nameWithOwner)#\(.number)", title, url, author: .author.login,
                created: .createdAt, merged: .mergedAt, closed: .closedAt})' <<<"$out"
  else
    jq -n --arg e "$(tail -1 <<<"$out")" '{error: $e}'
  fi
}

MERGED=$(list "is:pr author:$ME is:merged merged:>=$SINCE")
CLOSED=$(list "is:pr author:$ME is:closed is:unmerged closed:>=$SINCE")
REVIEWED=$(list "is:pr reviewed-by:$ME -author:$ME updated:>=$SINCE")

jq -n --arg since "$SINCE" --argjson nudge "$NUDGE" --slurpfile g "$GATHER" \
  --argjson merged "$MERGED" --argjson closed "$CLOSED" --argjson reviewed "$REVIEWED" '
  $g[0] as $g | {
    since: $since,
    merged_mine: $merged,
    closed_unmerged_mine: $closed,
    reviewed_by_me: $reviewed,
    waiting_on_others: [ $g.mine[]
      | select((.draft | not) and .decision != "APPROVED" and (.changes_requested_by | length) == 0
               and .unresolved_awaiting_me == 0 and .idle_days >= $nudge)
      | {key, url, title, idle_days, age_days, review_requests, last_activity_by} ],
    review_debt: [ $g.incoming[] | select(.draft | not) | {key, url, title, author, age_days, freshness, review_md} ]
      | sort_by(-.age_days) | .[:5]
  }'
