# Supplemental astronomy data — provenance and terms

Retrieved 17 September 2026. Application code remains MIT; these datasets retain their own terms.

## Stellarium

`stellarium-selected.tsv` is an unmodified-row extract of `nebulae/default/catalog.txt`, DSO catalog 3.23 standard, from Stellarium commit `04329a443d6827c2829bf45874f87243226673c2`. Rows with a nonzero M, Caldwell, Barnard, Sh2, VdB, RCW, LDN or LBN column are included. Original comments are retained. `stellarium-names.dat` is the original proper-name file from that commit.

Source: https://github.com/Stellarium/stellarium/tree/04329a443d6827c2829bf45874f87243226673c2/nebulae/default

Copyright Stellarium contributors; distributed under the upstream GPL-2.0-or-later terms, retained in STELLARIUM-COPYING. STELLARIUM-CREDITS.md is the complete original provenance/attribution file; its sections 3.9 and 3.10 identify the original catalogs and cross-identification sources. No Stellarium executable, rendering code or image textures are included. The extracted/converted Stellarium catalog data remain GPL-2.0-or-later, not MIT or OpenNGC's CC BY-SA license.

## Lynds / CDS

`ldn` and `LDN-ReadMe` are the original CDS VII/7A table and description:
https://cdsarc.cds.unistra.fr/ftp/cats/VII/7A/

Beverly T. Lynds, Catalogue of Dark Nebulae, ApJS 7, 1 (1962), bibcode 1962ApJS....7....1L; revised CDS edition, James Marcout and Francois Ochsenbein (1996). We acknowledge VizieR, CDS, Strasbourg, France, DOI 10.26093/cds/vizier.

These scientific data retain their original attribution and CDS rules of use (https://cds.unistra.fr/vizier-org/licences_vizier.html); they are not relicensed as MIT. VizieR permits scientific usage with attribution; commercial usage depends on the original data's terms. Consult the original notices for other reuse.

## Transformation and limits

Run `.venv/bin/python tools/update-supplement.py` to regenerate `catalog/supplement.json` and `supplement-source.json` from these bundled inputs. Existing OpenNGC records stay in a separate, unchanged file under CC BY-SA 4.0. The loader combines records at runtime; existing IDs and positions remain stable. Original source rows and build code are included here as the corresponding source for the converted supplement.

Matching uses explicit cross-identifications, never spatial proximity. Multiple components can share a catalog designation. The chosen source edition covers all 110 Messier and 109 Caldwell numbers, 343 Barnard, 313 Sh2, 158 VdB, 179 RCW, 1,787 numbered LDN and 1,118 LBN designations. These are coverage counts, not a claim that every historical catalog is complete. CDS VII/7A has 1,791 rows: 1,787 with original LDN numbers and four unnamed rows, retained as LDN-seq identifiers. Historical duplicate LDN numbers removed by CDS are not invented.

Stellarium coordinates are used as supplied (J2000/ICRS convention). CDS-only positions are converted from FK4/B1950 to ICRS with Astropy. The value 99 means unknown magnitude; dark-nebula opacity is never treated as a magnitude. For new objects with an LDN designation, area-derived source sizes are not presented as measured major/minor axes. Area in square degrees and opacity 1–6 are retained separately. No ellipse, FOV percentage or positional angle is invented. These broad cloud centers and boundaries are approximate.

This supplement is not an export of DWARFLAB or Seestar databases and does not certify exact app-catalog parity or photographic suitability.
