# Classic desktop brand and diagrams

Original instantKV artwork, MIT licensed with the repository.

| Asset | Size | Editable source |
|---|---|---|
| [Swarm topology PNG](swarm.png) | 1600 × 1040 | [swarm.tsrct](swarm.tsrct) |
| [Architecture and schema PNG](architecture.png) | 1600 × 1110 | [architecture.tsrct](architecture.tsrct) |
| [Compaction lifecycle PNG](lifecycle.png) | 1600 × 730 | [lifecycle.tsrct](lifecycle.tsrct) |
| [Distributed proposal PNG](distributed.png) | 1600 × 1140 | [distributed.tsrct](distributed.tsrct) |
| [Repository brand PNG](brand.png) | 1200 × 400 | [brand.tsrct](brand.tsrct) |
| [Logo PNG](logo.png) | 512 × 512 | [logo.tsrct](logo.tsrct) |
| [Transparent logo SVG](logo.svg) | scalable | Native SVG paths |

The memory-disk icon has three parked knowledge slots and a stepped K. Square
frames, beveled borders, navy title bars, teal desktop and pixel typography follow
the early desktop GUI brief. No rounded cards, modern gradients, or copied marks.
These are diagrams and original artwork, not an implemented graphical interface.

Tesseract compositions contain editable native shapes and text. Active type is
[VT323](https://github.com/phoikoi/VT323), distributed through
[Google Fonts](https://github.com/google/fonts/tree/main/ofl/vt323); its font and
[SIL Open Font License](fonts/VT323-OFL.txt) are included. Earlier compositions
also retain the licensed Space Grotesk asset, with [its license](fonts/OFL.txt).
PNG previews were visually inspected; the README embeds all four diagrams.

Navy title bars describe working single-node behavior. Brown title bars and the
explicit **FUTURE PROPOSAL** label distinguish the unimplemented distributed design.

Rebuild with Tesseract 0.3.0:

```sh
python3 scripts/render-design.py --tsrct /path/to/tsrct
```

Colors: navy `#000080`, teal `#008080`, gray `#c0c0c0`, white `#ffffff`,
black `#101010`, yellow `#ffff80`. All corners are square. PNG dimensions are
large enough for readable diagrams; the icon geometry follows a 16 × 16 grid.
