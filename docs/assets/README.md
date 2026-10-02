# Monolith identity and diagrams

Original instantKV artwork, MIT licensed with the repository.

| Asset                                           | Size        | Editable source                          |
| ----------------------------------------------- | ----------- | ---------------------------------------- |
| [Swarm topology PNG](swarm.png)                 | 1600 × 1090 | [swarm.tsrct](swarm.tsrct)               |
| [Architecture and schema PNG](architecture.png) | 1600 × 1200 | [architecture.tsrct](architecture.tsrct) |
| [Compaction lifecycle PNG](lifecycle.png)       | 1600 × 730  | [lifecycle.tsrct](lifecycle.tsrct)       |
| [Distributed proposal PNG](distributed.png)     | 1600 × 1200 | [distributed.tsrct](distributed.tsrct)   |
| [Repository brand PNG](brand.png)               | 1200 × 400  | [brand.tsrct](brand.tsrct)               |
| [Logo PNG](logo.png)                            | 512 × 512   | [logo.tsrct](logo.tsrct)                 |
| [Transparent logo SVG](logo.svg)                | scalable    | Native SVG paths                         |
| [Live demo architecture SVG](live-demo.svg)     | 1120 × 700  | Native SVG shapes, connectors and text   |

Monolith is the original metal identity. Three separate planes form a K.
Chrome reflections appear only on the mark.
The original diagrams use graphite surfaces, silver text, square geometry and fine borders.

The metal identity replaced an earlier desktop theme.
The current website uses a minimal white design.
The README uses the current social preview and a retained lifecycle diagram.
The live-demo diagram shows its browser interface and storage path.

The current [split-K mark](blueprint-mark.svg) is black.
The [social preview](blueprint-social.svg) uses white surfaces, black type and neutral accents.
A [PNG export](blueprint-social.png) is available.
Web diagrams use native components styled by `site/src/styles/global.css`.
[Website guide](../website.md).

Tesseract files contain editable shapes and text.
The original artwork embeds [Space Grotesk](https://github.com/floriankarsten/space-grotesk) with its [SIL license](fonts/OFL.txt).
Earlier archives retain VT323 and its [license](fonts/VT323-OFL.txt).
The website serves Geist locally with its [license](fonts/Geist-OFL.txt).
PNG previews were visually inspected.

Diagrams label implemented behavior and future proposals in text.
Status does not depend on color.

| Role            | Color                  |
| --------------- | ---------------------- |
| Background      | Graphite `#0B0D10`     |
| Diagram surface | `#12161B`              |
| Border and rule | `#303640`              |
| Primary text    | Silver white `#EDF0F5` |
| Secondary text  | Steel `#9EA7B5`        |
| Connectors      | Silver `#C6CEDB`       |

Keep chrome reflections on the original metal logo.
Use one-pixel borders, two-pixel connectors and square corners for its diagrams.
Keep a 72px outer margin on 1600px diagrams.
Place annotations beside the relevant connection.
Keep editable sources beside PNG exports.

These rules describe retained metal artwork. The website follows the minimal design in the [website guide](../website.md).

Rebuild with Tesseract 0.3.0:

```sh
python3 scripts/render-design.py --tsrct /path/to/tsrct
```

Use `--only brand logo` to render selected assets.
The transparent SVG uses the same three planes and chrome reflections.
Tesseract stores the reflections as editable clipped bands.
Intermediate JSON stays in the ignored `.tesseract-work` directory.
