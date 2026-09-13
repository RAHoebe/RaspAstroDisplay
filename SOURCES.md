# Beeldveld en doelbeelden

Application code is MIT-licensed (see `LICENSE`). This does not relicense the third-party catalog or images described below.

## Local comparison and observing windows

[ASTAP](https://www.hnsky.org/astap.htm), by Han Kleijn, supplies the separately installed local plate solver and D50 star database. The tested CLI identifies its license as **Mozilla Public License 2.0**. The installer downloads from the official SourceForge project; no solver executable or database is bundled in this repository. Original photographs stay on the device. A resized, EXIF-normalized copy is solved with an approximate catalog position and telescope-height hint, followed by automatic scale search when necessary.

[Astropy WCS](https://docs.astropy.org/en/stable/wcs/) reads the solution. CDS hips2fits supplies a north-up TAN survey cutout, reprojected locally through the solved WCS with bilinear sampling, including rotation and reflection. The original is never resampled or overwritten; comparison uses a separate copy up to 1600 pixels along its longest edge. The displayed angle describes this solved image, not a command to rotate a telescope camera. Survey credits below apply equally to comparisons.

Per-target altitude graphs use topocentric apparent positions in ten-minute samples through the next 24 hours. The displayed observing night is the first continuous period with Sun below −6°. Suggested 30–120 minute windows require every sample to have the target at least 30° high and Sun below −12°. Scores combine mean altitude, duration, Moon altitude/separation/illumination and available cloud forecasts. Missing forecast coverage is neutral (50% for scoring) and explicitly marked as uncertain; it is not treated as clear sky. These estimates do not model buildings, trees, local light pollution, seeing or transparency.

Specificaties gecontroleerd op 13 september 2026. Alle kaders zijn **één tele-opname**, zonder mozaïek. Het dashboard stuurt geen telescoop aan. De stand van het kader is illustratief: de werkelijke camerastand hangt af van de opstelling en het tijdstip. Er is geen knop voor camerarotatie en er wordt geen actuele alt-az- of EQ-oriëntatie berekend.

## Telescopen

- **DWARF II: ongeveer 3,19° × 1,79°**. Afgeleid met `2 atan(sensorzijde / (2 brandpuntsafstand))` uit 100 mm brandpuntsafstand, Sony IMX415, 3840 × 2160 opnamepixels en 1,45 µm pixelpitch. [DWARFLAB productpagina](https://checkout.dwarflab.com/en-de/products/dwarf-2-smart-telescope), [Sony IMX415 datasheet](https://www.sony-semicon.com/files/62/flyer_security/IMX415-AAQR_Flyer.pdf). De marketingwaarde van DWARFLAB is afgerond tot 3°.
- **Seestar S50 Pro: ongeveer 1,37° × 2,44°**. Afgeleid van de officiële **2,8° diagonale** beeldhoek en 2160 × 3840 beeldverhouding. Verdeling via de tangens van de halve beeldhoek, niet door 2,8° als breedte te gebruiken. [ZWO productpagina](https://us.zwoastro.com/products/seestar-s50-pro), [Seestar officiële vergelijking, inclusief definitie diagonale FOV](https://eu.seestar.com/de/blogs/seestar-guide/seestar-s30-pro-vs-s50-pro-which-pro-model-is-right-for-you).

Dit zijn nominale optische velden. Stabilisatie, stacking en uitsnijden kunnen de bruikbare randen verkleinen. Eigen telescopen worden opgeslagen met expliciete breedte en hoogte in graden (0,01–20° per zijde).

## Doelafmetingen

Catalogusgegevens: [OpenNGC, Mattia Verga](https://github.com/mattiaverga/OpenNGC), `NGC.csv` en `addendum.csv`, opgehaald 13 september 2026 uit [commit da90466031b0372c896588b85be6016c617e205b](https://github.com/mattiaverga/OpenNGC/tree/da90466031b0372c896588b85be6016c617e205b). De geselecteerde en naar decimale graden omgerekende catalogusdata in `catalog/deepsky.json` blijven beschikbaar onder [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). `tools/update-catalog.py` bewaart coördinaten, maten, positiehoek, bekende V-magnitude en aliassen, en voegt soortgroepen en enkele Nederlandse namen toe. Bronmetadata staat in `catalog/source.json`.

De selectie bevat 12.160 objecten: 433 nevels, 935 sterrenhopen/sterassociaties en 10.792 sterrenstelsels/groepen. Dubbele catalogusvermeldingen, niet-bestaande objecten en losse sterren zijn uitgesloten. Bij ontbrekende kleine as gebruiken we de opgegeven diameter als cirkelmaat. Bij ontbrekende grootte staat **maat onbekend**, zonder verzonnen beeldveldpercentage; doelzoom gebruikt dan een expliciet aangegeven contextveld. Er wordt geen precieze nevelcontour gesuggereerd.

| Object | Catalogusmaat (boogminuten) |
|---|---|
| M31 / NGC224 | 177,83 × 69,66; positiehoek 35° |
| M42 / NGC1976 | 90 × 60; positiehoek onbekend |
| M45 / Mel022 | 150 × 150 |
| M13 / NGC6205 | diameter 16,5 |
| M57 / NGC6720 | diameter 1,27 |
| M27 / NGC6853 | diameter 6,7 |

De zichtbare omvang hangt af van belichting, golflengte en welke zwakke buitengebieden een catalogus meet. De percentages zijn **grootste doelmaat / lange beeldrand**, geen oppervlaktepercentage en geen garantie dat een object in elke oriëntatie past.

## Nachtselectie en hoogte

Huidige hoogten komen uit Skyfield/JPL met topocentrische schijnbare posities. Voor vaste objecten gebruiken de vooruitberekeningen schijnbare RA/Dec van het huidige tijdstip en lokale sterrentijd in stappen van tien minuten tot 24 uur vooruit. De eerste aaneengesloten periode met zon onder −6° vormt de komende of resterende nacht. Deep-skyobjecten worden opgenomen bij een berekende hoogte boven 0° in die periode en gesorteerd op huidige hoogte. Een korte passage vlak boven de horizon kan tussen twee stappen vallen. Venus, Jupiter en Saturnus vereisen minstens 15° hoogte en minstens 20° afstand tot de zon; de maan blijft altijd bereikbaar. Er wordt niet op magnitude gefilterd: ook zwakke catalogusobjecten blijven beschikbaar.

De maanschijf gebruikt 1737,4 km straal en de actuele topocentrische afstand. De viewer tekent de berekende maanfase schematisch, zonder oppervlaktestructuur of libratie. Dit is geen actuele maanfoto.

Voor planeten wordt de schijfdiameter elke minuut opnieuw bepaald uit `2 asin(equatoriale straal / afstand)` met Skyfield/JPL DE421 en topocentrische afstand. Stralen: Venus 6051,8 km, Mars 3396,19 km, Jupiter 71492 km, Saturnus 60268 km. [NASA/JPL fysieke parameters](https://ssd.jpl.nasa.gov/planets/phys_par.html). Bij Saturnus betekent het percentage de planeetschijf, zonder de ringen.

## Rangschikking voor smart telescopen

`ranking.py` gebruikt een expliciete, niet wetenschappelijk gekalibreerde heuristiek: 40% hoogte/duur, 30% beeldvulling, 30% helderheid, gevolgd door extra afwaardering voor lage en heel kleine doelen. Hoogte loopt van 10° tot 65°; voor de nacht telt de hoogste stand 70% en het langste aaneengesloten venster boven 30° tot twee uur 30%. De duur is conservatief tussen tienminutenpunten bepaald. Voor ‘Nu’ telt huidige hoogte; bij 24 uur blijft het aanbevelingsadvies gericht op de komende nacht.

Beeldvulling vergelijkt lange en korte objectas met lange en korte beeldrand, geeft voorkeur aan minstens circa 18% lengte en ruimte tot circa 90% randvulling, en waardeert overschrijding af. Dit is een indicatie zonder actuele camerastand. Totale V-magnitude loopt voor deze heuristiek van magnitude 5 tot 13; bij nevels/stelsels met afmetingen wordt tevens de benaderde gemiddelde V-oppervlaktehelderheid `m + 2,5 log10(π × major × minor × 900)` gebruikt (assen in boogminuten, resultaat per vierkante boogseconde). Dit is een afgeleide schatting over catalogusoppervlak, geen gemeten profiel of contour. De bron kan sterren en nevel samen meten; bij sterrenhopen met nevel is dit dus geen afzonderlijke meting van het gas. Donkere nevels worden niet via een gewone lichtmagnitude beoordeeld. Ontbrekende waarden krijgen een neutrale tussenwaarde met expliciete melding, geen nullicht. Het B-bandveld SurfBr van OpenNGC wordt niet gemengd met V-magnitudes.

De sortering toont geen succespercentage. Weer, lichtvervuiling, gebruikte filters, belichting, camerastand en oppervlaktestructuur kunnen de praktische voorkeur veranderen. De lijst geeft redenen; het doelvenster toont de volledige uitleg. Planeten krijgen een lage deep-skyvoorkeur; de maan blijft apart.

## Beelden en schaal

Diepe-hemelbeelden: **DSS2/color**, via [CDS hips2fits](https://alasky.cds.unistra.fr/hips-image-services/hips2fits). Dit project maakt gebruik van hips2fits, een dienst van CDS. DSS is geproduceerd door het Space Telescope Science Institute, gebaseerd op fotografische hemelplaten van onder andere Palomar en UK Schmidt. [DSS acknowledgments](https://archive.stsci.edu/dss/acknowledging.html).

Voor M57 gebruiken we **Pan-STARRS DR1/color** via dezelfde dienst, omdat de Ringnevel in DSS2 verzadigd is. [CDS Pan-STARRS DR1](https://aladin.cds.unistra.fr/AladinLite/showcase/PanSTARRS-DR1/). Archiefbeelden hebben hun eigen resolutie, kleurcombinatie en verzadiging; inzoomen voegt geen detail toe. Credit: Pan-STARRS1 Surveys / Institute for Astronomy, University of Hawaii en het PS1 Science Consortium; kleuren-HiPS door CDS.

De uitsneden worden met een expliciete ICRS/TAN-WCS aangevraagd: 900 × 540 pixels, noord boven, oost links, centrum op de cataloguspositie. Kader en afbeelding gebruiken dezelfde tangentiële schaal per pixel. FITS-pixelcentrum `(450,5; 270,5)` correspondeert met SVG-centrum `(450; 270)`. Doelzoom omvat de catalogusmaat met marge; bij bekende positiehoek wordt de omhullende ellips gebruikt. Beeldveldzoom omvat het volledige kader met marge. Eén netwerkverzoek tegelijk en maximaal 120 lokaal bewaarde uitsneden; bij bronuitval blijft een schematische maatweergave beschikbaar, met een expliciete foutmelding en opnieuw-ladenknop.

Planeten gebruiken lokaal meegeleverde, ongewijzigde NASA-referentiebeelden. Het weergegeven beeld wordt op de huidige schijfdiameter geschaald aan de hand van gemeten/afgelezen schijfgrenzen in de foto; dit is een benadering. **Fase, oppervlak en ringstand zijn niet actueel.** Bij Venus toont een SVG-uitsnede alleen het linker paneel van de originele vergelijkingsplaat. Er wordt geen historisch sterrenveld als actuele planeetopname gepresenteerd.

- [Venus, Mariner 10 (1974)](https://science.nasa.gov/photojournal/venus-from-mariner-10/): NASA/JPL-Caltech; verwerking Kevin M. Gill, PIA23791. Kleurcombinatie van oranje en ultravioletfilters.
- [Mars, Hubble (2016)](https://science.nasa.gov/image-detail/hs-2016-15-a-full_tif/): NASA, ESA, Hubble Heritage Team (STScI/AURA), J. Bell (ASU), M. Wolff (Space Science Institute).
- [Jupiter, Hubble (2019)](https://science.nasa.gov/asset/hubble/jupiter-2019/): NASA, ESA, A. Simon (GSFC), M.H. Wong (UC Berkeley).
- [Saturnus, Hubble (2019)](https://science.nasa.gov/asset/hubble/saturn-2019/): NASA, ESA, A. Simon (GSFC), M.H. Wong (UC Berkeley), OPAL Team.
