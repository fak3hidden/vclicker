# bssmacro — Bee Swarm Simulator macro for Linux (Sober)

A single, integrated Bee Swarm Simulator automation macro for **Linux**, in the
spirit of Revolution/Natro, built to drive the game through **Sober**
(Roblox on Linux) via X11/XWayland.

Everything runs from one process:

* **Screen capture** of the Sober window (`mss` + X11 window lookup).
* **"AI collector" vision** — template matching *plus* a colour fallback finds
  tokens (honey, treats, royal jellies, stars, gifts, bubbles…), creatures
  (spiders, mantis, werewolves, king beetles…) and hazards on screen.
* **Priority picking** — you decide what matters. A weighted, distance-aware
  collector ranks everything visible each frame and walks to the best target;
  creatures/hazards are *avoided* instead of collected.
* **Objectives** — field gathering, **windy bees** (approach + optional vial
  usage), **stinger farming** (hunt spiders/creatures and mash your kill key),
  or a mix of all three.
* **Honey → hive conversion** — watches the honey bar (HSV fill analysis) and
  walks back to the hive to convert when full.
* **Discord webhook reporting** — Natro-style embeds: uptime, mode, honey %,
  tokens/min, conversions, windy spawns, stinger counts, top collected items,
  optional screenshots, heartbeat on an interval, event pings on
  start/stop/convert/windy/stinger.
* **Safety** — focus checking (only clicks while Sober is focused), error
  budget, max runtime.

## Install (Linux)

```bash
# System deps: X11 + XTest come with your desktop; Python 3.10+ assumed.
cd vclicker
python3 -m venv .venv
.venv/bin pip install -r bssmacro/requirements.txt   # numpy, opencv, mss, requests, pillow
```

No display-server gymnastics needed: if you run Sober through XWayland (the
default on most distros), everything works — the macro locates the Sober window
via X11 and injects keys/clicks with XTest.

## Quick start

```bash
# 0) sanity-check the install (headless unit tests)
python run_bss.py selftest

# 1) write a default config
python run_bss.py config                       # -> ~/.config/vclicker/bssmacro/config.json

# 2) point it at your Discord webhook (edit the JSON) and test it
python run_bss.py webhook-test

# 3) capture the Sober window and crop templates for the items you care about
python run_bss.py calibrate

# 4) dry-run first — full pipeline, NO real input injected
python run_bss.py run --fake

# 5) go farm
python run_bss.py run                          # field objective
python run_bss.py run --objective windy        # windy bee focus
python run_bss.py run --objective stinger      # stinger/spider farming
python run_bss.py run --objective mixed        # everything at once
```

## Configuration

`python run_bss.py config` writes a fully-commented-by-example JSON to
`~/.config/vclicker/bssmacro/config.json`. Highlights:

| Section        | What it controls                                                                 |
|----------------|----------------------------------------------------------------------------------|
| `window_*`     | How the Sober/Roblox window is found (title/process substrings).                  |
| `input_kind`   | `auto` (X11 when available), `x11`, or `fake` (testing).                          |
| `move_*`       | WASD key bindings, deadzone/arrive radii, click-to-move fallback.                  |
| `gather_cps`   | Auto-collect click rate while standing on tokens (0 = off).                        |
| `objective`    | `field` / `windy` / `stinger` / `mixed`.                                          |
| `capture`      | Downscale factor, capture FPS, fixed region override.                             |
| `collector`    | **Priority rules** (see below), global `min_score`, avoid list.                    |
| `detector`     | Template-match threshold, scales, colour-bucket fallback toggles.                  |
| `hud`          | Honey-bar region + HSV so the macro knows when to convert.                        |
| `convert`      | Hive region, conversion threshold, optional convert key.                           |
| `field`        | Field name hint, wander region, random walk when nothing is visible.               |
| `windy`        | Spawn key (cloud vial), spawn interval, collect key, approach radius.             |
| `stinger`      | Target field, kill key + mash rate + kill radius.                                 |
| `safety`       | Max runtime, require-focus, error budget.                                         |
| `webhook`      | URL, username/avatar, heartbeat interval, screenshot toggle, event list.          |

### Pickup priorities (the "AI collector")

Priorities are a list of rules — higher `weight` wins; ties go to the *closer*
target. Defaults:

```
stinger 100 > royal_jelly 90 > treat 85 > star 80 > gift 78 > field_boost 72
> magnet 70 > honey 60 > coconut 55 > pinecone 50 > ... > token 5
```

Creatures and hazards (spider, mantis, rhino beetle, scorpion, werewolf, king
beetle…) are **avoided** by default — except when the *objective* is stinger
farming, which deliberately hunts them.

To customise, edit `collector.priorities` in the config JSON:

```json
"collector": {
  "priorities": [
    {"label": "stinger",     "weight": 100, "enabled": true},
    {"label": "star",        "weight": 95,  "enabled": true},
    {"label": "field_boost", "weight": 90,  "enabled": true},
    {"label": "treat",       "weight": 10,  "enabled": false}
  ],
  "avoid": ["spider", "scorpion"],
  "min_score": 0.55
}
```

Any label not listed falls back to the catalog default, so you only need to
override what you care about.

### Templates

`bssmacro/templates/` ships with a README explaining naming. In short: crop a
small PNG of each item you want recognised (24–64 px, tight crop), name it by
label (`stinger.png`, `windy.png`, `spider.png`, …) and drop it in the folder —
or just run `python run_bss.py calibrate` with Sober open. Matching is
multi-scale; a colour fallback still finds bright tokens with no template at
all.

## Discord webhook

Configure `webhook.url` (Server Settings → Integrations → Webhooks) and you get
Natro-style progress embeds:

* **Heartbeat** every `interval_sec` (default 300 s): uptime, mode, honey %,
  tokens/min, total clicks, conversions, windy spawns, stingers collected, top
  8 collected item counts, optional screenshot.
* **Events**: `start`, `stop`, `convert`, `windy`, `stinger`, `error` — filter
  with `webhook.on_events`.

Test with `python run_bss.py webhook-test`.

## Architecture

```
bssmacro/
├── types.py            Rect / Frame / Detection / Target / HudState / Stats
├── catalog.py          Known labels, categories, default priorities
├── config.py           MacroConfig + all leaf configs (JSON load/save/validate)
├── engine.py           The orchestrator: detect → choose → move → act → report
├── calibrate.py        Screenshot + interactive template cropping
├── cli.py / __main__.py  `python -m bssmacro …` (also `python run_bss.py …`)
├── capture/            Sober window finder (X11) + mss screen capture
├── input/              X11Input (XTest) with FakeInput test double
├── vision/             Template store, detector (template+colour), collector, HUD reader
├── farming/            Field / Windy / Stinger / Mixed objectives
├── webhook/            Discord webhook client
└── tests/              Headless unittest suite (47 tests)
```

The engine loop (`Engine.loop_once`) is deliberately side-effect-light and
driven entirely through `InputController` + `Capture` interfaces, so the whole
pipeline is tested headlessly with synthetic frames (`bssmacro/tests/`).

## Honesty section (read this)

* Vision is template + colour based — it is *not* a neural net. It works well
  with good templates; calibrate per field/zoom level for best results.
* Movement is WASD dead-reckoning: the macro presses keys toward the target's
  screen position and re-checks every frame. Roblox camera angle affects this;
  keep your camera in a consistent position.
* Using macros violates Roblox ToS and can get your account banned. This is
  for educational/personal automation experimentation. You assume all risk.
