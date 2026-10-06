# Skykaart source data

- `hipparcos.tsv`: ESA Hipparcos Main Catalogue (1997), VizieR I/239/hip_main.
  Retrieved 1 October 2026 from the CDS ASU service with Johnson V magnitude <6.5.
  Fields: HIP, ICRS RA/Dec at J1991.25, V magnitude, and proper motions.
  Proper motions are propagated by Skyfield from epoch JD 2448349.0625.
  Source: https://cdsarc.cds.unistra.fr/viz-bin/cat/I/239
  Data rights: https://cds.unistra.fr/vizier-org/licences_vizier.html
- `western.json`: official Stellarium western sky culture, retrieved 1 October
  2026 from https://github.com/Stellarium/stellarium-skycultures/tree/master/western.
  Only constellation lines and names are used; no constellation illustrations.
  The unmodified source is retained. See the bundled description for attribution
  and upstream licensing, and the project's existing Stellarium credits.
- Named bright stars in `skykaart_stars.py` use their common astronomical names.

The poster's computed sky uses a horizon panorama at a labelled reference time.
The close-up is a gnomonic projection, north up and east left, with a 2° tangent
scale near the center. The dashed gold path shows the target at different times,
while the stars are held at the labelled reference time. Stars below the horizon
are excluded from the panorama; the close-up shows celestial context regardless
of the horizon. The terrain is an illustrative generated asset, not a survey of
the observing location. No fabricated stars or constellation lines are drawn.

The background was generated with the built-in ImageGen tool. Prompt: wide,
photorealistic, deep navy starless night sky above a low Dutch forest horizon;
subtle blue haze and a few distant warm ground lights; no text, stars, nebulae,
Moon, Sun, logos or telescopes. Asset: `static/skykaart-landscape.png`.
