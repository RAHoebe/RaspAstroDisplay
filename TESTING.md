# Validation

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
