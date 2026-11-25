#!/bin/zsh
# Print the preview-deployment URL your bot posted in a PR's comments. Prints nothing when none was posted.
# Usage: preview-url.sh <owner/repo> <pr-number>
# Env (both required: anyone can comment a link, and it opens in your logged-in browser):
#   PREVIEW_BOT     login of the account that posts previews, e.g. vercel
#   PREVIEW_URL_RE  extended regex for your project's own preview links, host included,
#                   e.g. 'https://my-project-[a-z0-9-]+\.vercel\.app(/[^ )"<>]*)?'
set -o pipefail
REPO=${1:?owner/repo}; N=${2:?pr number}
: ${PREVIEW_BOT:?set PREVIEW_BOT to the login that posts preview links}
: ${PREVIEW_URL_RE:?set PREVIEW_URL_RE to a regex matching your preview links}
[[ $PREVIEW_URL_RE == https://* ]] || { echo "PREVIEW_URL_RE must start with https://" >&2; exit 2 }
export PREVIEW_BOT
BODIES=$(gh pr view "$N" --repo "$REPO" --json comments \
  -q '.comments[] | select(.author.login == env.PREVIEW_BOT) | .body') || exit 1
grep -oE -e "$PREVIEW_URL_RE" <<<"$BODIES" | tail -1
exit 0
