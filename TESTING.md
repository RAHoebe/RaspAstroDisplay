# Validation

Run `python -m unittest discover -s tests -v` in the project environment. Tests cover astronomical selection, recommendation calculations, FOV geometry, capture validation/duplicates, origin/host controls, favorites, language settings, ZIP backup/restore and corrupt archives, observing-window continuity, WCS reprojection (rotation, reflection, RA wrap), and display configuration preservation.

Release checks on 13 September 2026:

- Pi 4, 4 GB, 64-bit Bookworm, Wayfire 0.7.5, original official 800×480 display at 180°.
- Kernel 6.12.96+rpt-rpi-v8. Native KMS touch and hidden initial pointer confirmed after reboot.
- ASTAP CLI 2026.09.01 / D50 with a real DWARF II photo: 3.01°×1.70°, 118.1° rotation, aligned DSS2 reference in 41.2 seconds.
- Original photos preserved; ZIP restore checked in a new directory with checksums and SQLite integrity.
- English/Dutch browser checks and the 800×480 kiosk layout.

Touch Display 2 and labwc have not been physically tested. Presets are nominal fields; real captures can be cropped or rotated. A successful solve does not guarantee every processed image will solve.
