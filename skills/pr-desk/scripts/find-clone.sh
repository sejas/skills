#!/usr/bin/env bash
# pr-desk find-clone: print the path of a local clone whose origin is <owner/repo>
# (github.com or an enterprise host). Looks at the main repos behind
# ~/worktrees.nosync/* first, then up to 3 levels under ~/Documents and ~/projects.
# Exit 1 with no output when none is found (then clone with --filter=blob:none).
# Usage: find-clone.sh <owner/repo>
set -euo pipefail
WANT="${1:?usage: find-clone.sh owner/repo}"
match() { git -C "$1" remote get-url origin 2>/dev/null | grep -Eqi "[:/]${WANT}(\.git)?$"; }
for w in "$HOME"/worktrees.nosync/*/; do
  [[ -e "$w/.git" ]] || continue
  c=$(git -C "$w" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || continue
  main=$(dirname "$c")
  if match "$main"; then echo "$main"; exit 0; fi
done
while IFS= read -r g; do
  d=$(dirname "$g")
  if match "$d"; then echo "$d"; exit 0; fi
done < <(find "$HOME/Documents" "$HOME/projects" -maxdepth 4 -name .git -type d 2>/dev/null)
exit 1
