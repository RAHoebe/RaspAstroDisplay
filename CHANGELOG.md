# Changes

## Unreleased ? extended object catalogs

- Expand the catalog to 15,438 objects with Messier, Caldwell, Barnard, Sharpless, VdB, RCW, LDN and LBN designations and common-name aliases.
- Match spaces, punctuation, leading zeros and expanded catalog names; prioritize exact identifiers. Capture uploads search the complete catalog regardless of observing-night filters.
- Keep existing object IDs and capture links. Treat dark-nebula opacity separately from magnitude and avoid invented FOV sizes.
- Include reproducible data inputs, importer, source credits and separate dataset licenses.

## 1.2 — 14 September 2026 (Release 2)

- Tap ASTRO to open About with the installed version, author, MIT license and project/documentation/source links.
- About supports English/Dutch, red night mode, touchscreen controls and native keyboard focus restoration.
- A single VERSION file supplies the displayed version and release link.
- Updated documentation and added three original 800 × 480 screenshots of About.

## 1.1 — 14 September 2026

- Home fits the available display height, with short advice and no unused space above the panels. Long location names are shortened visually.
- Home, targets and altitude graphs share the same observing night. Selection advances at sunrise; midnight retains the current night. Polar locations use a labeled local-noon fallback. Advice only includes future intervals.
- Choose the full night or the next eight hours on Home and Weather. Night forecasts use at most eight weighted cloud blocks and a separate astronomical-darkness strip. Astronomy covers the entire selected night, including hours beyond the next 24 hours.
- The Pi now manages active and idle brightness with configurable automatic dimming. Existing active brightness is preserved; idle defaults to 10% after 60 seconds. The first touch only wakes the kiosk, including over dialogs. Remote browsers and background work do not extend the timer.
- Settings are split into four tabs, fetched once when opened, and protected against saving before loading. The display profile migrates automatically and is included in ZIP backup/restore; the legacy brightness API remains supported.
- Missing cloud values remain unknown. Stale or incomplete forecasts cannot produce confident weather advice.
- Altitude graphs and both comparison images follow red night mode without changing originals or downloads.
- Background refresh preserves unfinished search text, focus, selection and scroll position.
- Documentation and the 800×480 screenshot gallery are updated.

## 1.0 — 14 September 2026

Initial public release: local astronomy and weather, smart-telescope target ranking and FOV previews, personal captures, local ASTAP comparison, favorites, altitude tracks, ZIP backups, English/Dutch interface and display setup wizard.
