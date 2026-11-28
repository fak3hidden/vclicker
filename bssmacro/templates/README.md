# Templates

The detector recognises things by matching small cropped images ("templates")
against the live game. Drop PNG files in **this folder** and they are picked up
automatically on the next run.

## Naming

The file stem becomes the label the macro sorts by priority:

| File name            | Recognised as | Notes                                   |
|----------------------|---------------|-----------------------------------------|
| `honey.png`          | `honey`       | gold honey token                        |
| `treat__gumdrop.png`| `treat`       | double-underscore is just a disambiguator|
| `royal_jelly.png`    | `royal_jelly` |                                         |
| `stinger.png`        | `stinger`     | the dropped stinger (not the spider)    |
| `windy.png`          | `windy`       | the windy bee / wind puff               |
| `spider.png`         | `spider`      | a spider (stinger farming target)       |
| `hive.png`           | `hive`        | used as a navigation anchor if present   |

Any label in `bssmacro/catalog.py` works; unknown stems become their own label
and fall under the default priority weight.

## How to make good templates

1. Run `python run_bss.py calibrate` — it screenshots your Sober window and (with
   a display) lets you drag a box around each item.
2. Alternatively, screenshot the game yourself and crop tight around **one** item
   with no background. 24×24 to 64×64 px works best.
3. Keep templates on a transparent/consistent background; the matcher is
   scale-robust but not rotation-robust, so match the in-game orientation.

Templates are matched at several scales, so a single crop covers most zoom
levels. You do **not** need a template for every token — the colour fallback in
`bssmacro/vision/detector.py` still finds bright, saturated tokens and reports
them as `honey` / `treat` / `royal_jelly` / `star` / `bubble` / `glue` / `white`
by dominant hue.
