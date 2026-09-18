#!/bin/bash
set -eu
until curl --silent --fail --max-time 3 http://127.0.0.1:8080/api/health > /dev/null; do
    sleep 2
done
browser=$(command -v chromium || command -v chromium-browser)
# Read validated arguments separately; never evaluate profile text as shell code.
display_script="$(dirname "$0")/display.py"
python3 "$display_script" activate
display_flags=$(python3 "$display_script" kiosk-args)
mapfile -t display_args <<< "$display_flags"
python3 - <<'PY'
import json
from pathlib import Path
profile = Path.home() / '.config/astro-chromium/Default'
profile.mkdir(parents=True, exist_ok=True)
path = profile / 'Preferences'
try:
    prefs = json.loads(path.read_text())
except (FileNotFoundError, ValueError):
    prefs = {}
prefs.setdefault('translate', {})['enabled'] = False
prefs.setdefault('intl', {})['accept_languages'] = 'en-US,en,nl'
temporary = path.with_suffix('.tmp')
temporary.write_text(json.dumps(prefs))
temporary.replace(path)
PY
if [ -n "${WAYLAND_DISPLAY:-}" ]; then
    browser_platform=wayland
    browser_display_args=()
    for display_arg in "${display_args[@]}"; do
        case "$display_arg" in
            --window-size=*) ;;
            *) browser_display_args+=("$display_arg") ;;
        esac
    done
else
    browser_platform=x11
    browser_display_args=("${display_args[@]}")
fi
exec "$browser" --user-data-dir="$HOME/.config/astro-chromium" --kiosk --start-fullscreen --start-maximized "${browser_display_args[@]}" --noerrdialogs --disable-infobars --no-first-run --no-default-browser-check --disable-session-crashed-bubble --disable-features=Translate --lang=en-US --ozone-platform="$browser_platform" --password-store=basic --disable-pinch 'http://127.0.0.1:8080/?kiosk=1'
