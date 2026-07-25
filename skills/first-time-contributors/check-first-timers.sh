#!/usr/bin/env bash
set -euo pipefail
# Usage: check-first-timers.sh [--days N] [owner/repo ...]
# Defaults: last 7 days, current repo (gh repo view).
# Finds authors whose first-ever merged PR in the repo landed inside the window.
# ponytail: GitHub search API is rate-limited to 30 req/min; add sleep between
# authors if a repo has >25 distinct authors in the window.

DAYS=7
repos=()
while [[ $# -gt 0 ]]; do
	case $1 in
		--days)
			DAYS=$2
			shift 2
			;;
		*)
			repos+=( "$1" )
			shift
			;;
	esac
done

if [[ ${#repos[@]} -eq 0 ]]; then
	repos=( "$(gh repo view --json nameWithOwner -q .nameWithOwner)" )
fi

SINCE=$(date -v-"${DAYS}"d +%F 2>/dev/null || date -d "-${DAYS} days" +%F)

for repo in "${repos[@]}"; do
	echo "== $repo — PRs merged since $SINCE =="
	authors=$(gh pr list --repo "$repo" --state merged \
		--search "merged:>=$SINCE" --limit 200 --json author -q '.[].author.login' |
		sort -u | grep -v -e '^app/' -e '\[bot\]$' || true)

	if [[ -z "$authors" ]]; then
		echo "no merged PRs in window"
		continue
	fi

	found=0
	for a in $authors; do
		prior=$(gh api "search/issues?q=repo:$repo+is:pr+is:merged+author:$a+merged:<$SINCE" --jq '.total_count')
		if [[ "$prior" -eq 0 ]]; then
			found=1
			echo "🎉 FIRST-TIME CONTRIBUTOR: $a"
			gh pr list --repo "$repo" --state merged \
				--search "merged:>=$SINCE author:$a" --json number,title,url \
				-q '.[] | "   #\(.number) \(.title)\n   \(.url)"'
		else
			echo "   $a — $prior prior merged PRs"
		fi
	done
	[[ "$found" -eq 0 ]] && echo "→ no first-time contributors in window"
done
