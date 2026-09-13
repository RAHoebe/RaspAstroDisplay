#!/bin/bash
# Run as the desktop user (not as root) on 64-bit Raspberry Pi OS Desktop.
set -eu
if [ "$(id -u)" -eq 0 ]; then
    echo 'Run this script as your normal desktop user; it uses sudo where needed.' >&2
    exit 1
fi
cd "$(dirname "$0")/.."
python3 - <<'PY'
import platform
from pathlib import Path
if platform.machine() not in ('aarch64','x86_64'):
    raise SystemExit('A 64-bit OS is required. Raspberry Pi 4 with 4 GB RAM or newer is recommended.')
memory=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))
if memory<3300000:
    raise SystemExit('At least a 4 GB Raspberry Pi is required for this installation.')
PY
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip chromium curl wlr-randr
python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.txt
sudo groupadd --system -f astrodisplay
sudo install -m 644 deploy/90-astro-backlight.rules /etc/udev/rules.d/90-astro-backlight.rules
sudo udevadm control --reload-rules
for file in /sys/class/backlight/*/brightness; do
    [ -e "$file" ] || continue
    sudo chgrp astrodisplay "$file"
    sudo chmod g+w "$file"
done
python3 deploy/setup.py
python3 deploy/display.py wizard
echo 'Optional local capture comparison: bash deploy/install-solver.sh'
echo 'Enable desktop autologin in raspi-config, then reboot to start the kiosk.'
