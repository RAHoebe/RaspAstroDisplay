#!/bin/bash
set -eu
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_RUNTIME_DIR
systemctl --user restart astro-kiosk.service
