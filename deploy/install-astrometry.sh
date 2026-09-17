#!/bin/bash
# Optional second local solver; upstream recommended Tycho-2 indexes.
set -eu
sudo apt-get update
sudo apt-get install -y --no-install-recommends astrometry.net
solver_home="${ASTRO_ASTROMETRY_HOME:-$HOME/.local/share/astrometry}"
mkdir -p "$solver_home"
available=$(df --output=avail -B1 "$solver_home" | tail -1)
if [ "$available" -lt 3000000000 ]; then
    echo 'Leave at least 3 GB free for indexes and system reserve.' >&2
    exit 1
fi
for scale in 4107 4108 4109 4110; do
    file="$solver_home/index-$scale.fits"
    if [ ! -s "$file" ]; then
        curl --fail --location --retry 3 --connect-timeout 20 --max-time 1800 \
            "https://data.astrometry.net/4100/index-$scale.fits" -o "$file.part"
        python3 - "$file.part" <<'PY'
from astropy.io import fits
import sys
with fits.open(sys.argv[1]) as hdus:
    hdus.verify('exception')
    assert len(hdus) > 1
PY
        mv "$file.part" "$file"
    fi
done
printf 'add_path %s\nautoindex\ninparallel\ncpulimit 180\n' "$solver_home" > "$solver_home/astrometry.cfg"
echo 'Astrometry.net ready. Index coverage is intended for roughly 0.5-8 degree fields.'
