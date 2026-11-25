#!/bin/zsh
# Print the preview-deployment URL a bot posted in a PR's comments. Prints nothing when none was posted.
# Usage: preview-url.sh <owner/repo> <pr-number>
# Env: PREVIEW_URL_RE - extended regex matching your preview links (required),
#      e.g. 'https://[a-z0-9-]+\.vercel\.app[^ )"<>]*'
REPO=${1:?owner/repo}; N=${2:?pr number}
: ${PREVIEW_URL_RE:?set PREVIEW_URL_RE to a regex matching your preview links}
gh pr view "$N" --repo "$REPO" --json comments -q '.comments[].body' |
  grep -oE "$PREVIEW_URL_RE" | tail -1
exit 0
