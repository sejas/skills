#!/usr/bin/env bash
# pr-desk gather: github.com INCOMING (review requested + re-review) and MINE (my open PRs)
# with deltas vs state.json, plus participating notifications not covered by either.
# Read-only against GitHub. Prints JSON; also saves it to $STATE_DIR/last-gather.json.
# GHE is NOT covered here — the skill fetches it separately (prompts.md §5).
# Usage: gather.sh            full JSON
#        gather.sh --summary  one line per PR (human check)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/lib.sh"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ERRORS="$TMP/errors.jsonl"; : > "$ERRORS"
err() { jq -nc --arg src "$1" --arg msg "$2" '{source:$src, error:$msg}' >> "$ERRORS"; }

NOW=$(now_iso)
LAST_RUN=$(jq -r '.last_run // empty' "$STATE")
FIRST_RUN=$([[ -z "$LAST_RUN" ]] && echo true || echo false)
LOOKBACK=$(cfg .rereview_lookback_days)

search() { # name query
  local out="$TMP/$1.json"
  if ! gh api graphql --paginate -F q="$2" -F me="$ME" -F query=@"$DIR/search.graphql" \
       --jq '.data.search.nodes[] | select(.number != null)' > "$TMP/$1.raw" 2> "$TMP/$1.err"; then
    err "github.com search: $1" "$(tail -1 "$TMP/$1.err")"
    : > "$TMP/$1.raw"
  fi
  jq -s '.' "$TMP/$1.raw" > "$out"
}

search requested "is:pr is:open archived:false review-requested:$ME" &
search reviewed  "is:pr is:open archived:false reviewed-by:$ME -author:$ME -review-requested:$ME updated:>=$(days_ago "$LOOKBACK")" &
search mine      "is:pr is:open archived:false author:$ME" &
# First run: look back a day (Monday: since Friday morning) instead of the 65-minute tick window.
NOTIF_SINCE=${LAST_RUN:-$( [[ $(date +%u) == 1 ]] && minutes_ago 4200 || minutes_ago 1440 )}
if ! "$DIR/notifications.sh" "$NOTIF_SINCE" > "$TMP/notifs.json" 2> "$TMP/notifs.err"; then
  err "github.com notifications" "$(tail -1 "$TMP/notifs.err")"; echo '[]' > "$TMP/notifs.json"
fi
wait

# Enrich PR notifications with open/closed state and drop
# closed/merged ones unless they are a direct mention.
jq -r '.[] | select(.type == "PullRequest") | "\(.repo) \(.number)"' "$TMP/notifs.json" | sort -u \
  | xargs -P 6 -L 1 sh -c 'gh pr view "$1" -R "$0" --json state,isDraft,author \
      --jq "{key: \"$0#$1\", state: (.state | ascii_downcase), draft: .isDraft, author: .author.login}" 2>/dev/null || true' \
  | jq -s 'map({(.key): .}) | add // {}' > "$TMP/notif_states.json"
jq --slurpfile st "$TMP/notif_states.json" '
  map(. + ($st[0][.key // ""] // {}))
  | map(select((.state // "open") == "open" or (.reason | IN("mention","team_mention"))))' \
  "$TMP/notifs.json" > "$TMP/notifs2.json" && mv "$TMP/notifs2.json" "$TMP/notifs.json"

# Saved review docs: "mtime<TAB>filename", newest-first not required.
: > "$TMP/mds.tsv"
if [[ -d "$REVIEWS_DIR" ]]; then
  for f in "$REVIEWS_DIR"/20*.md; do
    [[ -e "$f" ]] && printf '%s\t%s\n' "$(mtime "$f")" "$(basename "$f")" >> "$TMP/mds.tsv"
  done
fi

jq -n \
  --arg me "$ME" --arg now "$NOW" --arg since "${LAST_RUN:-}" --argjson first_run "$FIRST_RUN" \
  --argjson ignore "$(cfg '.ignore_logins')" \
  --slurpfile state_f "$STATE" \
  --rawfile mds "$TMP/mds.tsv" \
  --slurpfile requested_f "$TMP/requested.json" \
  --slurpfile reviewed_f "$TMP/reviewed.json" \
  --slurpfile mine_f "$TMP/mine.json" \
  --slurpfile notifs_f "$TMP/notifs.json" \
  --slurpfile errors_f <(jq -s '.' "$ERRORS") \
  -f <( printf '%s\n' \
    '$state_f[0] as $state | $requested_f[0] as $requested | $reviewed_f[0] as $reviewed' \
    '| $mine_f[0] as $mine | $notifs_f[0] as $notifs |' ; cat "$DIR/annotate.jq"; echo '| . + {errors: $errors_f[0]} | if (.errors | length) > 0 then .gone = [] | .partial = true else .partial = false end' ) \
  > "$STATE_DIR/last-gather.json"

if [[ "${1:-}" == "--summary" ]]; then
  jq -r '
    "# pr-desk gather \(.generated_at) user=\(.me) since=\(.since // "first run")",
    "errors: \(.errors | length)", (.errors[] | "  ! \(.source): \(.error)"),
    "## INCOMING (\(.counts.incoming), agent needed: \(.counts.incoming_need_agent))",
    (.incoming[] | "- \(.key) [\(.freshness)\(if .rereview then ", re-review" else "" end)\(if .direct then "" else ", team" end)] delta=\(.delta) age=\(.age_days)d \(.size) ci=\(.ci) by \(.author): \(.title)"),
    "## MINE (\(.counts.mine), triage needed: \(.counts.mine_need_triage))",
    (.mine[] | "- \(.key) delta=\(.delta) decision=\(.decision) ci=\(.ci) merge=\(.mergeable) flags=\(.flags | join(",")) idle=\(.idle_days)d triage=\(.needs_triage): \(.title)"),
    "## GONE since last run (\(.gone | length))", (.gone[] | "- \(.key) \(.title)"),
    "## OTHER NOTIFICATIONS (\(.notifications | length))", (.notifications[:15][] | "- [\(.reason)] \(.repo)#\(.number) (\(.type)) \(.title)")
  ' "$STATE_DIR/last-gather.json"
else
  cat "$STATE_DIR/last-gather.json"
fi
