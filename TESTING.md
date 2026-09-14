# Validation

## Post-v1.2 presentation fixes — 14 September 2026

- Added an explicit Best 2 hours label to distinguish the recommended interval from the full astronomical darkness period. English/Dutch and 800 × 480, 853 × 480, 720 × 1280 and mobile layouts were checked without Home overflow.
- Reordered all showcase categories around the main observing and capture workflows. One About image remains, last in All screens and Make it yours. The other two remain in the historical v1.2 release.
- Recaptured the normal English/Dutch and red Home images on the Pi without a cursor. Website validation covers 21 screenshots, seven HTML pages and 182 local references.

## v1.2 checks — 14 September 2026

- All 82 existing tests pass locally. The updated app runs on the Pi 4.
- About opens from ASTRO and shows version 1.2, Ron Hoebe, MIT and the correct guide/release/source links. English and Dutch were checked.
- The native modal closes using its cross and Escape; keyboard focus returns to ASTRO. The popup fits at 800 × 480, 853 × 480, 1280 × 720, 720 × 1280 and 390 × 844.
- Red night colors were checked. Three new 800 × 480 screenshots were captured from the Pi and visually inspected without the automation cursor.

## v1.1 checks — 14 September 2026

- 82 tests pass locally and on the Pi 4 (the original 61 plus 21 regression cases). The Pi test run takes about 33 seconds. Development-only `ephem` supplies independent astronomy checks.
- Night selection is checked immediately before/at sunrise, at midnight, in summer without astronomical darkness, in polar day/night and across both DST changes. Hour coverage extends beyond 24 hours when required. Today's Moon rise is not skipped when the selected night advances.
- Forecast tests cover complete, missing, null, non-finite and stale values, partial-hour weighting and full-night coverage. Target advice rejects past windows and gaps.
- Fake-clock tests cover migration, validation, fade timing, restart, missing/failed hardware, unchanged settings files during activity, legacy brightness input and ZIP restoration. API tests reject remote and forwarded-address activity requests and missing tokens.
- Browser geometry checks found no Home overflow in English/Dutch at 800×480, 853×480, 1024×576, 1280×720, 720×1280, 480×853, 360×640, 390×844 and 1440×1000. Long names, unknown weather, stale data and the polar notice were also exercised. Other views may scroll.
- Browser interaction checks with the real frontend and a simulated backlight confirmed that the first click only wakes, including over a modal close button, and a second click operates the control. Settings makes one GET per opening and initially disables storage controls. A live background refresh retained unfinished capture search text, focus and selection.
- On the actual Pi, the physical backlight was measured at 26/255 idle and 166/255 active: it reached active within 0.3 seconds of a local wake request, stayed active at 59.5 seconds, faded through 142 and 90 after the 60-second timeout, and returned to 26 by 61.2 seconds. The settings-file timestamp did not change. Remote browsing and ZIP creation did not keep it awake. Backend/kiosk restart and migration retained the 65/10/60 profile and Dutch preference.
- The original two photo checksums were unchanged. A newly downloaded Pi ZIP was restored into a separate directory; both original checksums and the complete display profile matched.
- Red-mode SVG strokes and both loaded comparison-image filters were checked in the browser. All 20 screenshots were captured from the running Pi at 800×480 and inspected without the browser automation cursor. All website gallery images retain 5:3 geometry at desktop/mobile widths and in the enlarged viewer; seven HTML pages and 177 internal references validate.

Ron confirmed the physical finger-tap checks on the Pi: the first touch only wakes, the second opens Settings, and the first touch over an open dialog does not close it. Touch Display 2 hardware and labwc remain untested physically.

Run `python -m unittest discover -s tests -v` in the project environment. Tests cover astronomical selection, recommendation calculations, FOV geometry, capture validation/duplicates, origin/host controls, favorites, language settings, ZIP backup/restore and corrupt archives, observing-window continuity, WCS reprojection (rotation, reflection, RA wrap), and display configuration preservation.

Release checks on 13 September 2026:

- Pi 4, 4 GB, 64-bit Bookworm, Wayfire 0.7.5, original official 800×480 display at 180°.
- Kernel 6.12.96+rpt-rpi-v8. Native KMS touch and hidden initial pointer confirmed after reboot.
- ASTAP CLI 2026.09.01 / D50 with a real DWARF II photo: 3.01°×1.70°, 118.1° rotation, aligned DSS2 reference in 41.2 seconds.
- Original photos preserved; ZIP restore checked in a new directory with checksums and SQLite integrity.
- English/Dutch browser checks and the 800×480 kiosk layout.

Touch Display 2 and labwc have not been physically tested. Presets are nominal fields; real captures can be cropped or rotated. A successful solve does not guarantee every processed image will solve.

## v1.0 website and release checks — 14 September 2026

- All 61 application tests passed on the development environment.
- All 17 showcase images measured at 5:3 on desktop (1440-pixel viewport) and mobile (390-pixel viewport), including the enlarged viewer. Responsive images use automatic height instead of retaining the HTML height attribute while their width shrinks.
- Original screenshot files remain 800×480. The complete screenshot set was recaptured on 14 September without the browser automation cursor; capture dates and credits are recorded in the website manifest.
- Local website validation checked seven HTML pages, internal links and anchors, image dimensions and alt text. CSS and refreshed screenshot URLs have cache revisions so returning visitors receive the correction.
