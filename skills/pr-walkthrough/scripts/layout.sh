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

osascript <<EOF
tell application "$APP"
  set w1 to make new window
  set URL of active tab of w1 to "http://127.0.0.1:$PORT/"
  set bounds of w1 to {0, $TOP, $HALF, $BOT}
  set w2 to make new window
  set URL of active tab of w2 to "${PR%/}/files"
  set bounds of w2 to {$HALF, $TOP, $W, $MID}
  if "$LIVE" is not "" then
    set w3 to make new window
    set URL of active tab of w3 to "$LIVE"
    set bounds of w3 to {$HALF, $MID, $W, $BOT}
  end if
  activate
end tell
EOF
echo "walkthrough http://127.0.0.1:$PORT/ (stops after 30 idle minutes)${LIVE:+ · live $LIVE}"
