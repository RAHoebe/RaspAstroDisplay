#!/bin/bash
# Official ASTAP CLI and D50 database, installed for the current user.
set -eu
case "$(uname -m)" in
    aarch64) arch=aarch64 ;;
    x86_64) arch=amd64 ;;
    *) echo 'ASTAP installation requires 64-bit ARM or x86 Linux.' >&2; exit 1 ;;
esac
solver_home="${ASTRO_SOLVER_HOME:-$HOME/.local/share/astap}"
download_home="${XDG_CACHE_HOME:-$HOME/.cache}/astro-installer"
mkdir -p "$solver_home" "$download_home"
available=$(df --output=avail -B1 "$solver_home" | tail -1)
if [ "$available" -lt 5000000000 ]; then
    echo 'Please leave at least 5 GB free for installation and system reserve.' >&2
    exit 1
fi
curl --fail --location --retry 3 --connect-timeout 20 --max-time 1800 \
    "https://downloads.sourceforge.net/project/astap-program/linux_installer/astap_command-line_version_Linux_${arch}.zip" \
    -o "$download_home/astap-cli.zip"
curl --fail --location --retry 3 --connect-timeout 20 --max-time 3600 \
    'https://downloads.sourceforge.net/project/astap-program/star_databases/d50_star_database.zip' \
    -o "$download_home/d50.zip"
python3 - "$download_home" "$solver_home" <<'PY'
import hashlib
from pathlib import Path
import sys
import zipfile
source, dest = map(Path, sys.argv[1:])
for name in ('astap-cli.zip', 'd50.zip'):
    archive = source / name
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            target = (dest / info.filename).resolve()
            if not target.is_relative_to(dest.resolve()) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Invalid archive member')
        z.extractall(dest)
    with archive.open('rb') as source_file:
        print(name, hashlib.file_digest(source_file, 'sha256').hexdigest())
binary = next(dest.rglob('astap_cli'))
binary.chmod(0o755)
print('Solver:', binary)
print('Database:', dest)
PY
echo 'ASTAP is installed. The dashboard will detect it on the next comparison.'
