# pr-desk: turn raw GraphQL search nodes into INCOMING / MINE rows with deltas.
# Args: $me $now $since $first_run $ignore(json) $state(json) $mds(raw "mtime\tfile" lines)
#       $requested $reviewed $mine (slurped node arrays) $notifs (json array)
def ep: if . == null or . == "" then 0 else (sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601) end;
def human: (.author.__typename // "User") != "Bot"
  and ((.author.login // "") as $l | ($ignore | index($l)) == null)
  and (.author.login // "") != $me;
def k: "\(.repository.nameWithOwner)#\(.number)";
def mdfiles: $mds | split("\n") | map(select(length > 0) | split("\t") | {m: (.[0] | tonumber), f: .[1]});

def activity:
  [ (.comments.nodes[]? | select(human) | {kind: "comment", who: .author.login, at: .createdAt}),
    (.latestReviews.nodes[]? | select(human) | {kind: ("review " + (.state | ascii_downcase)), who: .author.login, at: .submittedAt}),
    (.reviewThreads.nodes[]? | .comments.nodes[]? | select(human) | {kind: "thread reply", who: .author.login, at: .createdAt}) ]
  | map(select(.at != null)) | sort_by(.at);

def base:
  (activity) as $act
  | ($state.prs[k] // null) as $seen
  | (.commits.nodes[0].commit.committedDate // null) as $lc
  | {
      key: k, repo: .repository.nameWithOwner, number, title, url,
      author: .author.login, draft: .isDraft,
      created: .createdAt, updated: .updatedAt,
      age_days: ((($now | ep) - (.createdAt | ep)) / 86400 | floor),
      idle_days: ((($now | ep) - ((($act | last | .at) // .createdAt) | ep)) / 86400 | floor),
      size: "+\(.additions)/-\(.deletions), \(.changedFiles) files",
      lines: (.additions + .deletions), files: .changedFiles,
      decision: (.reviewDecision // "NONE"), mergeable, ci: (.commits.nodes[0].commit.statusCheckRollup.state // "NONE"),
      head: .headRefOid, head_ref: .headRefName, base_ref: .baseRefName, last_commit: $lc,
      review_requests: [.reviewRequests.nodes[]?.requestedReviewer | (.login // .name) | select(. != null)],
      approved_by: [.latestReviews.nodes[]? | select(.state == "APPROVED" and human) | .author.login],
      changes_requested_by: [.latestReviews.nodes[]? | select(.state == "CHANGES_REQUESTED" and human) | .author.login],
      unresolved: [.reviewThreads.nodes[]? | select(.isResolved | not)] | length,
      unresolved_awaiting_me: [.reviewThreads.nodes[]? | select((.isResolved | not) and (.comments.nodes[0].author.login // $me) != $me)] | length,
      last_activity: (($act | last | .at) // null),
      last_activity_by: (($act | last | .who) // null),
      seen: ($seen != null),
      new_activity: [ $act[] | select(.at > ($seen.last_activity // "")) ] | .[-8:],
      delta: (if $seen == null then "new"
              elif .headRefOid != $seen.head then "new_commits"
              elif ((($act | last | .at) // "") > ($seen.last_activity // "")) then "new_activity"
              elif ((.commits.nodes[0].commit.statusCheckRollup.state // "NONE") != $seen.ci
                    or (.reviewDecision // "NONE") != $seen.decision
                    or .mergeable != $seen.mergeable) then "state_change"
              else "unchanged" end)
    };

def incoming_row:
  base as $b
  | (.myReviews.nodes[0].submittedAt // null) as $mine
  | ($b.repo | split("/")[1]) as $short
  | (mdfiles | map(select((.f | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}-")) and (.f | contains("-\($short)-\($b.number)-")) and (.f | contains("-walkthrough") | not)))
     | max_by(.m)) as $md
  | $b + {
      direct: ($b.review_requests | index($me) != null),
      my_last_review: $mine,
      rereview: ($mine != null and $b.last_commit != null and $b.last_commit > $mine),
      review_md: ($md.f // null),
      review_md_at: (if $md then ($md.m | todate) else null end),
      freshness: (if $b.draft then "draft"
                  elif $md == null then "new"
                  elif $md.m < ($b.last_commit | ep) then "stale"
                  else "current" end)
    }
  | . + {needs_review_agent: ((.freshness == "new" or .freshness == "stale") and (.draft | not))};

def mine_row:
  base
  | . + {
      flags: ([ (if (.changes_requested_by | length) > 0 then "changes_requested" else empty end),
                (if .unresolved_awaiting_me > 0 then "unresolved:\(.unresolved_awaiting_me)" else empty end),
                (if .ci == "FAILURE" or .ci == "ERROR" then "ci_failing" else empty end),
                (if .mergeable == "CONFLICTING" then "conflicts" else empty end),
                (if .decision == "APPROVED" and (.draft | not) and .mergeable != "CONFLICTING" and (.ci | IN("SUCCESS","NONE")) then "approved_unmerged" else empty end),
                (if (.new_activity | length) > 0 and .seen then "new_comments" else empty end) ])
    }
  | . + {
      needs_triage: (.delta != "unchanged"
                     and ((.changes_requested_by | length) > 0 or .unresolved_awaiting_me > 0
                          or ([.new_activity[] | select(.kind != "review approved")] | length) > 0))
    };

($requested | map(incoming_row)) as $req
| ($reviewed | map(incoming_row) | map(select(.rereview))) as $rev
| (($req + $rev) | unique_by(.key) | sort_by(.created)) as $incoming
| ($mine | map(mine_row) | sort_by(.updated) | reverse) as $mrows
| ([$incoming[].key, $mrows[].key]) as $keys
| {
    generated_at: $now, me: $me, since: $since, first_run: $first_run,
    incoming: $incoming,
    mine: $mrows,
    gone: [ $state.prs | to_entries[] | select((.key | startswith("ghe:") | not) and (.key as $x | $keys | index($x) == null))
            | {key, kind: .value.kind, title: .value.title, url: .value.url} ],
    notifications: [ $notifs[] | select(.key as $x | $keys | index($x) == null) ],
    counts: {
      incoming: ($incoming | length),
      incoming_need_agent: ([$incoming[] | select(.needs_review_agent)] | length),
      mine: ($mrows | length),
      mine_need_triage: ([$mrows[] | select(.needs_triage)] | length)
    }
  }
