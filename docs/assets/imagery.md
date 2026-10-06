# Website imagery

Created 4 October 2026 with the built-in imagegen tool. All images are conceptual
editorial photography. They do not document benchmark hardware, a shipped phone
integration or a running product UI. Original PNGs remain in the local generation
folder. Website copies use WebP, maximum width 1,400 pixels and quality 82.

| Asset | Prompt |
| --- | --- |
| `local-devices-hero.webp` | Wide photoreal studio image. Unbranded silver compact desktop computer and black phone on a light warm-gray desk. Screens off; no text or logos. Soft daylight, restrained monochrome, plausible hardware. Local-device direction; do not imply software runs on the phone. |
| `arm-board.webp` | Wide editorial photograph. Small unbranded black ARM board on a pale grey desk next to a disconnected white cable. Soft daylight, precise realistic electronics, monochrome, no text or logos. Future device-validation target, not a measured benchmark. |
| `local-storage.webp` | Wide studio close-up. Small unbranded aluminium external solid state drive and short black cable on light grey paper. Natural daylight and shadows, brushed metal, monochrome. No text, logos or fake screens. Concept of local persistent storage. |

`blueprint-social.svg` is an editable, code-native social card. Its PNG is generated
from the SVG. Benchmark charts render numeric data from committed reports; imagegen
does not draw quantitative charts.

The service-site redesign on 6 October 2026 removed the concept photographs from
the homepage and research article. The files remain as historical artwork.
The social card now matches the installation-first copy. Rebuild its PNG with:

```sh
rsvg-convert docs/assets/blueprint-social.svg -o docs/assets/blueprint-social.png
```
