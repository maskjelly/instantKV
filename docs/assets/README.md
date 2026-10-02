# Monolith identity and diagrams

Original instantKV artwork, MIT licensed with the repository.

| Asset | Size | Editable source |
|---|---|---|
| [Swarm topology PNG](swarm.png) | 1600 × 1090 | [swarm.tsrct](swarm.tsrct) |
| [Architecture and schema PNG](architecture.png) | 1600 × 1200 | [architecture.tsrct](architecture.tsrct) |
| [Compaction lifecycle PNG](lifecycle.png) | 1600 × 730 | [lifecycle.tsrct](lifecycle.tsrct) |
| [Distributed proposal PNG](distributed.png) | 1600 × 1200 | [distributed.tsrct](distributed.tsrct) |
| [Repository brand PNG](brand.png) | 1200 × 400 | [brand.tsrct](brand.tsrct) |
| [Logo PNG](logo.png) | 512 × 512 | [logo.tsrct](logo.tsrct) |
| [Transparent logo SVG](logo.svg) | scalable | Native SVG paths |
| [Live demo architecture SVG](live-demo.svg) | 1120 × 700 | Native SVG shapes, connectors and text |

**Monolith** is the project's original minimal metal theme. Three separated metal
planes form a K; the gap keeps the silhouette distinct at small sizes. Chrome
reflections belong to the mark. Diagrams use flat graphite surfaces, silver text,
fine borders, square geometry and generous space.

This repository identity superseded the earlier retro desktop theme. The public
website now follows the later white technical blueprint brief, while the README
keeps its original metal artwork. The live-demo diagram describes its browser
interface and real storage path.

The website's [flat blue split-K](blueprint-mark.svg),
[social preview SVG](blueprint-social.svg) and [PNG export](blueprint-social.png)
use white paper, blue ink and square geometry. Web diagrams are native SVG
components styled by `site/src/styles/global.css`; see the [website guide](../website.md).

Tesseract compositions contain editable native shapes and text. Active type is
[Space Grotesk](https://github.com/floriankarsten/space-grotesk), embedded with
[its SIL Open Font License](fonts/OFL.txt). Headings use medium weight; body text
uses regular weight. The earlier licensed VT323 font remains in the asset
archives, with [its license](fonts/VT323-OFL.txt).
PNG previews were visually inspected; the README embeds all four diagrams.

Each diagram explicitly labels **IMPLEMENTED** or **FUTURE PROPOSAL**. Status
depends on words rather than color, so the monochrome theme preserves that boundary.

| Role | Color |
|---|---|
| Background | Graphite `#0B0D10` |
| Diagram surface | `#12161B` |
| Border and rule | `#303640` |
| Primary text | Silver white `#EDF0F5` |
| Secondary text | Steel `#9EA7B5` |
| Connectors | Silver `#C6CEDB` |

Keep chrome confined to the logo. Use one-pixel borders, two-pixel connectors,
square corners and a 72px outer margin on 1600px diagrams. Titles lead the reading
order; annotations sit beside the connection they explain. Avoid decorative
controls, textures or extra accent colors. Export large PNGs for the README and
keep their editable sources beside them.

Rebuild with Tesseract 0.3.0:

```sh
python3 scripts/render-design.py --tsrct /path/to/tsrct
```

Use `--only brand logo` to render selected assets. The transparent SVG uses the
same three planes and chrome stops; Tesseract stores the reflections as editable
clipped shape bands. Intermediate JSON stays in the ignored `.tesseract-work` directory.
