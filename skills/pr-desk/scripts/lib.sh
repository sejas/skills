# shellcheck shell=bash
# Shared helpers for pr-desk scripts. Source it; don't run it.
SKILL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CFG="$SKILL_DIR/config.json"
xp() { local p="$1"; printf '%s\n' "${p/#\~/$HOME}"; }
cfg() { jq -r "$1" "$CFG"; }
command -v jq >/dev/null || { echo "pr-desk: jq is required" >&2; exit 2; }
command -v gh >/dev/null || { echo "pr-desk: gh is required" >&2; exit 2; }

ID_CFG=$(xp "$(cfg .identity_config)")
STATE_DIR=${PR_DESK_STATE_DIR:-$(xp "$(cfg .state_dir)")}   # env override for tests
REVIEWS_DIR=$(xp "$(cfg .reviews_dir)")
REPORT_DIR=$(xp "$(cfg .report_dir)")
mkdir -p "$STATE_DIR" "$REPORT_DIR"
STATE="$STATE_DIR/state.json"
[[ -s "$STATE" ]] || echo '{"last_run":null,"prs":{}}' > "$STATE"

# github.com login: identity config first (no API call), then gh.
ME=$(jq -r '.gh_user // empty' "$ID_CFG" 2>/dev/null || true)
[[ -n "$ME" ]] || ME=$(gh api user --jq .login)

days_ago()    { date -u -v-"$1"d +%F 2>/dev/null || date -u -d "-$1 days" +%F; }
minutes_ago() { date -u -v-"$1"M +%FT%TZ 2>/dev/null || date -u -d "-$1 minutes" +%FT%TZ; }
now_iso()     { date -u +%FT%TZ; }
mtime()       { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1"; }
