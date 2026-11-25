#!/usr/bin/env bash
# pr-desk board: every open non-draft PR in a repo, newest update first.
# Read-only. Prints JSON rows; drafts are only counted.
# Usage: board.sh <owner/repo> [pages=2]
set -euo pipefail
source "$(dirname "$0")/lib.sh"
REPO="${1:?usage: board.sh owner/repo [pages]}"
PAGES="${2:-2}"
OWNER="${REPO%%/*}"; NAME="${REPO##*/}"
Q='query($owner:String!,$name:String!,$cursor:String){
  repository(owner:$owner,name:$name){
    pullRequests(states:OPEN,first:50,after:$cursor,orderBy:{field:UPDATED_AT,direction:DESC}){
      pageInfo{hasNextPage endCursor}
      nodes{
        number title isDraft url createdAt updatedAt author{__typename login} reviewDecision
        additions deletions changedFiles
        labels(first:10){nodes{name}}
        reviewRequests(first:10){nodes{requestedReviewer{... on User{login} ... on Team{name}}}}
        comments(last:20){totalCount nodes{author{__typename login}}}
        reviews(first:50){totalCount nodes{author{login} state}}
        reviewThreads(first:100){nodes{isResolved isOutdated}}
      }}}}'
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cursor=""
for ((i = 0; i < PAGES; i++)); do
  gh api graphql -f query="$Q" -F owner="$OWNER" -F name="$NAME" ${cursor:+-F cursor="$cursor"} > "$TMP/p$i.json"
  [[ $(jq -r '.data.repository.pullRequests.pageInfo.hasNextPage' "$TMP/p$i.json") == true ]] || break
  cursor=$(jq -r '.data.repository.pullRequests.pageInfo.endCursor' "$TMP/p$i.json")
done
jq -s --arg repo "$REPO" --arg me "$ME" --argjson ignore "$(cfg .ignore_logins)" --arg now "$(now_iso)" '
  def ep: sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601;
  def days($t): ((($now | ep) - ($t | ep)) / 86400 | floor);
  [ .[].data.repository.pullRequests.nodes[] ] as $all
  | {
      repo: $repo,
      drafts_skipped: ([ $all[] | select(.isDraft) ] | length),
      rows: [ $all[] | select(.isDraft | not) | {
        number, title, url, author: .author.login,
        bot: (.author.__typename == "Bot" or (.author.login | test("dependabot|renovate"))),
        mine: (.author.login == $me),
        created: .createdAt[:10], created_days: days(.createdAt),
        updated: .updatedAt[:10], updated_days: days(.updatedAt), stale: (days(.updatedAt) > 30),
        review_requested: [ .reviewRequests.nodes[].requestedReviewer | (.login // .name) | select(. != null) ],
        unresolved: [ .reviewThreads.nodes[] | select(.isResolved | not) ] | length,
        human_comments: [ .comments.nodes[] | select(.author.__typename != "Bot" and ((.author.login // "") as $l | $ignore | index($l)) == null) ] | length,
        review_states: [ .reviews.nodes[].state ] | group_by(.) | map("\(.[0])×\(length)"),
        decision: (.reviewDecision // "NONE"),
        size: "+\(.additions)/-\(.deletions), \(.changedFiles) files",
        labels: [ .labels.nodes[].name ],
        merge_candidate: (.reviewDecision == "APPROVED" and ([ .reviewThreads.nodes[] | select(.isResolved | not) ] | length) == 0)
      } ]
    }' "$TMP"/p*.json
