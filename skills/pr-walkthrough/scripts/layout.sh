#!/bin/zsh
# Tile the browser for one PR review on the main screen:
#   left half: walkthrough (served with Ask) | right: PR files (top) + the preview deployment (bottom).
# Without a live URL the PR takes the whole right half.
# Usage: layout.sh <workdir> <walkthrough.html> <pr-url> [<live-url>]
# Env: REVIEW_BROWSER (default "Brave Browser"; any Chromium browser with AppleScript works).
set -e
WORKDIR=${1:?workdir}; HTML=${2:?walkthrough.html}; PR=${3:?pr url}; LIVE=${4:-}
APP=${REVIEW_BROWSER:-Brave Browser}
SERVE=${0:A:h}/serve.py

# URLs can come from PR comments: accept plain https only, and pass them to AppleScript as
# arguments (never inside the script text). The app name must be literal there, so restrict it.
valid_url() { [[ $1 =~ '^https://[A-Za-z0-9.-]+(:[0-9]+)?([/?#][]A-Za-z0-9._~:/?#@!$&()*+,;=%[-]*)?$' ]] }
[[ $APP =~ '^[A-Za-z0-9 ]+$' ]] || { echo "layout.sh: bad REVIEW_BROWSER" >&2; exit 2 }
valid_url "$PR" || { echo "layout.sh: bad PR url" >&2; exit 2 }
[[ -z $LIVE ]] || valid_url "$LIVE" || { echo "layout.sh: bad live url" >&2; exit 2 }

N=${PR##*/pull/}; N=${N%%[^0-9]*}
PORT=$(( 40000 + N % 10000 ))   # stable per PR: #12345 -> 42345
if ! lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  nohup python3 -I "$SERVE" "$WORKDIR" "$HTML" --port $PORT >"$WORKDIR/serve.log" 2>&1 &
  for _ in {1..20}; do lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1 && break; sleep 0.25; done
fi

read W H <<<"$(osascript -l JavaScript -e 'ObjC.import("AppKit"); const f=$.NSScreen.mainScreen.visibleFrame; `${f.size.width} ${f.size.height}`')"
TOP=$(( $(osascript -l JavaScript -e 'ObjC.import("AppKit"); $.NSScreen.mainScreen.frame.size.height') - H ))
HALF=$(( W / 2 )); BOT=$(( TOP + H )); MID=$(( TOP + H / 2 ))
[[ -z $LIVE ]] && MID=$BOT

osascript - "http://127.0.0.1:$PORT/" "${PR%/}/files" "$LIVE" <<EOF
on run argv
set {walkUrl, prUrl, liveUrl} to argv
tell application "$APP"
  set w1 to make new window
  set URL of active tab of w1 to walkUrl
  set bounds of w1 to {0, $TOP, $HALF, $BOT}
  set w2 to make new window
  set URL of active tab of w2 to prUrl
  set bounds of w2 to {$HALF, $TOP, $W, $MID}
  if liveUrl is not "" then
    set w3 to make new window
    set URL of active tab of w3 to liveUrl
    set bounds of w3 to {$HALF, $MID, $W, $BOT}
  end if
  activate
end tell
end run
EOF
echo "walkthrough http://127.0.0.1:$PORT/ (stops after 30 idle minutes)${LIVE:+ · live $LIVE}"
