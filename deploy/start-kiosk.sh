#!/bin/bash
set -eu
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_RUNTIME_DIR XAUTHORITY
systemctl --user restart astro-kiosk.service
