# Brand and architecture assets

Original instantKV artwork, MIT licensed with the repository.

| Asset | Size | Editable source |
|---|---|---|
| [Architecture PNG](architecture.png) | 1600 × 1100 | [architecture.tsrct](architecture.tsrct) |
| [Repository brand PNG](brand.png) | 1200 × 420 | [brand.tsrct](brand.tsrct) |
| [Logo PNG](logo.png) | 512 × 512 | [logo.tsrct](logo.tsrct) |
| [Transparent logo SVG](logo.svg) | scalable | Native SVG paths |

Tesseract compositions contain editable native shapes and text, with an embedded
Space Grotesk font. The redistributable font and its SIL Open Font License are
included in [fonts](fonts/OFL.txt). The logo does not copy another project's mark.

Rebuild with Tesseract 0.3.0:

```sh
python3 scripts/render-design.py --tsrct /path/to/tsrct
```

Colors: forest `#182d27`, green `#267d60`, paper `#f5f3ed`, lime `#d8ed9b`.
