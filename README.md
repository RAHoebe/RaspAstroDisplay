# Astro Control Panel

Tap **ASTRO** in the upper-left corner for About: installed version, author, MIT license and links to the guide, release and sources. Current release: [Release 2 · v1.2](https://github.com/RAHoebe/RaspAstroDisplay/releases/tag/v1.2).

A local touchscreen dashboard for planning a night with a smart telescope. For **Raspberry Pi 4 with 4 GB RAM or newer**, the original Raspberry Pi 7-inch Touch Display and the 7-inch Touch Display 2. English (US) and Dutch, large touch controls, red night mode and automatic backlight dimming.

**[Website & showcase](https://rahoebe.github.io/RaspAstroDisplay/)** · **[Installation guide](https://rahoebe.github.io/RaspAstroDisplay/install.html)** · **[Sources & licenses](https://rahoebe.github.io/RaspAstroDisplay/sources.html)**

The English website lives in `doc/`, with 20 actual 800 × 480 application screenshots in `doc/screenshots/`. GitHub Actions publishes only `doc/`. Local working notes belong in the ignored `plan/` folder and private helper scripts in `toolslocal/`; distributable maintenance tools remain in `tools/`.

## Features

- **Tonight:** a compact home screen, shared sunrise-based night selection, full-night cloud blocks or the next eight hours, and a future two-hour weather window.
- **Moon:** phase, illumination, altitude, direction and upcoming events.
- **Weather:** hourly forecasts and animated Meteosat infrared cloud images.
- **Targets:** 15,438 catalog objects from OpenNGC, Stellarium and CDS (including LDN, LBN, Barnard, Sharpless, RCW, VdB and Caldwell), a permanent Moon shortcut and selected bright planets. Filter the coming night, current sky or next 24 hours; sort by smart-telescope recommendation, altitude, size or magnitude.
- **Field of view:** DWARF II and Seestar S50 Pro presets, plus 12 custom telescopes. Open an object for a survey image, telescope frame, target zoom and frame zoom. The last telescope selection is remembered.
- **Planning:** altitude and Moon tracks, a suggested imaging window, favorites and a “not captured with this telescope” filter. Favorites and capture counts are separate for each telescope.
- **Captures:** upload JPG/JPEG or PNG, browse by object/telescope, download originals and restore photos from Trash. Original image bytes are retained.
- **Compare:** local ASTAP star matching determines the actual field and rotation of a photograph. A survey reference is reprojected into the same frame, with swipe and blink comparison.
- **Display:** active/idle brightness, 10–3600 second timeout, backend-owned dimming and a first touch that only wakes the local kiosk. Remote browsers do not keep the screen awake.
- **Backup:** download a consistent ZIP of photographs, database, favorites and application settings.

This application does not control a telescope. Being above the horizon does not guarantee suitability for imaging. Recommendations are estimates, with reasons shown in the interface. See [SOURCES.md](SOURCES.md) for calculations and credits.

## Version 1.1

See [what changed](CHANGELOG.md) and the [upgrade guide](https://rahoebe.github.io/RaspAstroDisplay/install.html#v11). Existing active brightness, photographs, language and telescopes are preserved. The original display and its rotation remain supported.

## Install on a Raspberry Pi

Use **64-bit Raspberry Pi OS Desktop**, Python 3.11 or newer, and a working Wayfire or labwc session. Start with an updated OS supporting your display. Raspberry Pi OS Lite lacks the required desktop. Allow at least 5 GB free for installing the optional solver, plus space for photos and backup ZIPs. The app reserves 2 GiB for the system.

Run as your normal desktop user, in a terminal or SSH session:

```sh
sudo apt update
sudo apt install -y git
git clone https://github.com/RAHoebe/RaspAstroDisplay.git
cd RaspAstroDisplay
bash deploy/install.sh
```

The installer creates the Python environment, services and backlight permissions for the current user and checkout path. Its display wizard detects the panel and offers rotation, interface size and cursor visibility. Enable **desktop autologin** using `sudo raspi-config`, then reboot. Edited display configuration is backed up.

For local image comparison, also run:

```sh
bash deploy/install-solver.sh
```

This downloads official ASTAP CLI and the D50 star database to `~/.local/share/astap`. The database download is approximately 860 MB; archives remain in `~/.cache/astro-installer`. ASTAP has its own license.

Open `http://<your-pi-hostname>.local:8080/` on the same network, or use the Pi's IP address if name resolution is unavailable. The kiosk opens automatically on the Pi.

New installations start in **English (US)** at **Greenwich**. Set your location and language under **Settings → Location & language**. The saved language becomes the default for new browsers; each browser can retain its own language choice. Times use the observing location's time zone, and date/number formatting follows the language.

### Change display or rotation

Power off before changing a DSI display or ribbon cable. After booting with the new display:

```sh
python3 deploy/display.py wizard
sudo reboot
```

The wizard supports 0°, 90°, 180° and 270°, matching touch coordinates and kiosk sizing. See [DISPLAY.md](DISPLAY.md) for details and recovery. Physical testing of Touch Display 2 and the labwc adapter is pending.

## Photographs and comparison

Use **Add capture** inside an object or **Upload** in Captures. Choose a telescope and optionally a date and note. Accepted files: JPG/JPEG and PNG, up to **25 MiB and 32 megapixels per photograph**. Multiple files can be selected. Files come from the device running the browser; the dashboard does not automatically access telescope apps.

Counts exclude Trash. Removing a custom telescope preserves its photos and historical name. Exact duplicates at the same object and telescope are rejected. Previews respect EXIF orientation; downloadable originals are unchanged.

Open a photo and choose **Compare → Align locally**. Star matching runs on the Pi, one job at a time. Only sky coordinates and the reference projection go to CDS; your photograph stays on the Pi. Internet is needed for a new reference, and successful comparisons remain cached. One full-field DWARF II photo took about 41 seconds on the tested Pi 4, including download. Crops, sparse stars, blur or star removal can prevent matching; Moon/planet-only images are unsupported. Survey colors, sensitivity and resolution differ from your telescope.

## Backup and restore

Choose **Settings → System & backup → Create ZIP backup**, wait, then **Download ZIP**. Store the download on another device. The Pi retains the two most recent generated ZIPs.

The archive includes originals, previews and thumbnails (including Trash), a consistent SQLite snapshot, favorites, location, telescope profiles, language and brightness. A manifest records sizes and SHA-256 checksums. Generated comparisons, downloaded catalogs, sky caches, browser-only selections, desktop/boot configuration and the OS are excluded. This is an application backup, not a whole-card image.

Restore into a **new directory** first. Paths, checksums and database integrity are validated; an existing destination is never overwritten:

```sh
.venv/bin/python tools/restore-backup.py /path/to/astro-backup.zip "$HOME/astro-restored"
```

Then stop `astro-panel`, preserve the existing `~/.local/share/astro-panel` directory under a dated name, move the verified restore into its place, and restart `astro-panel`. Use the same desktop user that installed the application. The first subsequent start downloads missing sky caches again.

## Operation and updates

Installed state lives in `~/.local/share/astro-panel`, outside the checkout. Chromium uses `~/.config/astro-chromium`. Code updates preserve photographs and settings.

```sh
git pull --ff-only
.venv/bin/pip install -r requirements.txt
sudo systemctl restart astro-panel
systemctl --user restart astro-kiosk
```

Diagnostics:

```sh
systemctl status astro-panel
journalctl -u astro-panel -n 50 --no-pager
systemctl --user status astro-kiosk
python3 deploy/display.py status
```

The backend runs without sudo. This trusted-local-network application has no user accounts: anyone who can open it can view photos and change settings. Do not expose port 8080 directly to the internet. Same-origin checks and a per-process token protect against cross-site writes. Local hostnames and addresses are detected automatically. Set `ASTRO_HOSTS` (comma-separated names) in a systemd override for extra aliases. Restart after a changed IP if a numeric address is rejected.

Internet is needed for the first JPL ephemeris download (about 17 MB), weather, place search and new survey/satellite images. Astronomy then runs locally. Cached data carry timestamps and stale indicators. The satellite layer is primarily useful around Europe and Africa and shows infrared cloud-top temperatures, not precipitation radar or seeing.

## Development and licensing

Python 3.11+, no frontend build step and no JavaScript/font CDN. On Linux:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
ASTRO_BIND=127.0.0.1 OPENBLAS_NUM_THREADS=1 .venv/bin/python app.py
.venv/bin/python -m unittest discover -s tests -v
```

On Windows use `.venv/Scripts/python` and PowerShell environment variables. Development state defaults to `.runtime/`. Options: `ASTRO_STATE`, `ASTRO_BIND`, `ASTRO_PORT`, `ASTRO_HOSTS`, `ASTRO_SOLVER_HOME`, `ASTRO_SOLVER`. Translations are in `static/locales.json`. User notes and telescope names are kept as entered.

Application code: [MIT](LICENSE). OpenNGC-derived data: **CC BY-SA 4.0**. Third-party images, software and data retain their own credits and licenses in [SOURCES.md](SOURCES.md). See [TESTING.md](TESTING.md) for validation and hardware limitations.


Catalog search accepts identifiers such as `LDN 935`, `Lynds 935`, `Barnard 33`, `Caldwell 20` and `Sh2-155`, with exact identifiers listed first. Observing filters still apply in Targets; Add capture searches every catalog object, even outside the current night. Dark clouds have opacity/area where known, without invented magnitude or FOV dimensions. Supplemental data retain their [own licenses and source credits](catalog/sources/README.md).
