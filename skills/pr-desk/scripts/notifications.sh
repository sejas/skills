#!/usr/bin/env bash
# pr-desk notifications: participating GitHub
# notifications across ALL repos since a point in time, as a JSON array.
# Read-only: never PATCHes/marks anything read.
# Usage: notifications.sh [SINCE_ISO]
#   No arg: first run of the morning (<10:00) covers the overnight gap
#   (Mon: since Fri 15:00, else since yesterday 15:00); otherwise last 65 minutes.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if [[ -n "${1:-}" ]]; then
  SINCE="$1"
elif (( 10#$(date +%H) < 10 )); then
  [[ $(date +%u) == 1 ]] && SINCE=$(minutes_ago 4200) || SINCE=$(minutes_ago 1320)
else
  SINCE=$(minutes_ago 65)
fi

# Reasons that mean "someone wants something from you". `subscribed`/`ci_activity` are noise.
gh api "notifications?all=true&participating=true&since=${SINCE}&per_page=100" --paginate \
  --jq '.[] | select(.reason | IN("review_requested","mention","team_mention","comment","author","state_change","assign"))
        | (.subject.url // "") as $u
        | ($u | split("/") | last) as $n
        | {
            reason, repo: .repository.full_name, type: .subject.type, title: .subject.title,
            updated_at, number: $n,
            key: (if (.subject.type | IN("PullRequest","Issue")) then "\(.repository.full_name)#\($n)" else null end),
            url: ($u | sub("^https://api\\.github\\.com/repos/"; "https://github.com/") | sub("/pulls/"; "/pull/"))
          }' \
  | jq -s 'unique_by([.key, .reason]) | sort_by(.updated_at) | reverse'
