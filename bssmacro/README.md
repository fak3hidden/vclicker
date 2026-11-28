# bssmacro — Bee Swarm Simulator macro for Linux (Sober)

A single, integrated Bee Swarm Simulator automation macro for **Linux**, in the
spirit of Revolution/Natro, built to drive the game through **Sober**
(Roblox on Linux). Works on **X11, XWayland *and* native Wayland**.

Everything runs from one process:

* **Screen capture** of the Sober window — `mss` + X11 window lookup on
  X11/XWayland, or the compositor's own screenshot tool (`grim`, `spectacle`,
  `gnome-screenshot`, …) on native Wayland.
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
cd vclicker
python3 -m venv .venv
.venv/bin/pip install -r bssmacro/requirements.txt   # numpy, opencv, mss, requests, pillow
```

Input backend depends on your display server (see the Wayland section below):

| Session            | Input                                    | Capture                          |
|--------------------|------------------------------------------|----------------------------------|
| X11                | XTest (`libXtst`)                        | `mss`                            |
| XWayland (Sober under XWayland) | XTest — usually all you need | `mss` (X11 windows only)         |
| Native Wayland     | `uinput` virtual device or `ydotool`     | `grim`/`spectacle`/`gnome-screenshot` |

## Native Wayland support

Wayland, by design, does **not** let programs inject input into other windows —
XTest is an X11-only trick, and `mss` can only see X11 windows. The macro
therefore switches to two kernel/compositor-level paths when there is no usable
X display:

**Input — `uinput` virtual device** (default on Wayland, `input_kind = "uinput"`).
A virtual keyboard + touchscreen-style pointer is created directly through
`/dev/uinput` with zero extra Python packages. The kernel treats it as real
hardware, so *every* Wayland compositor (GNOME, KDE, sway, Hyprland, …)
processes its events like physical input: WASD reaches the game and taps land
at exact screen coordinates. One-time setup:

```bash
sudo modprobe uinput
echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' \
    | sudo tee /etc/udev/rules.d/70-uinput.rules
sudo udevadm control --reload && sudo udevadm trigger
sudo usermod -aG input "$USER"    # then log out and back in
```

Already running `ydotoold`? Set `input_kind = "ydotool"` instead — the macro
will drive the game through the ydotool CLI (same keycodes, no second virtual
device).

**Capture — compositor screenshot CLI** (`capture.method = "cli"`). Frames are
grabbed with whichever tool your desktop ships, tried in this order until one
succeeds: `grim` → `wayshot` → `spectacle` → `gnome-screenshot` → `scrot` →
`maim` → `import`. It uses the compositor's own screenshot interface (the same
thing PrintScreen uses). Force a specific one with `capture.shot_tool`.

Window lookup: `hyprctl clients -j` on Hyprland, `swaymsg -t get_tree -r` on
sway/wlroots. **GNOME and KDE have no CLI window query** — on those desktops
put Sober in **fullscreen** so the whole output is the game (recommended on
every compositor; it also makes click coordinates pixel-exact). Focus is
handled by clicking the window centre (click-to-focus) — Wayland won't let us
raise windows programmatically.

Recommended Wayland config snippet:

```json
{
  "input_kind": "uinput",
  "capture": { "method": "cli", "shot_tool": "" }
}
```

Notes & limits on native Wayland:

* Screenshot-per-frame is slower than `mss` (~100–400 ms per frame). Fine for
  token farming; lower `capture.downscale` if needed.
* Keyboard movement is rock-solid everywhere; absolute taps are scaled from the
  captured frame size (the engine feeds the live resolution to the device).
* If your compositor mangles absolute pointer positions, use `ydotool`.
* Single-monitor setups align perfectly; with multiple monitors prefer
  fullscreen Sober or `capture.fixed_region`.

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
| `input_kind`   | `auto` (X11 → uinput → fake), `x11`, `uinput`/`wayland`, `ydotool`, `fake`.       |
| `move_*`       | WASD key bindings, deadzone/arrive radii, click-to-move fallback.                  |
| `gather_cps`   | Auto-collect click rate while standing on tokens (0 = off).                        |
| `objective`    | `field` / `windy` / `stinger` / `mixed`.                                          |
| `capture`      | Downscale factor, capture FPS, `method` (`auto`/`mss`/`cli`), `shot_tool`, fixed region. |
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
├── capture/            Sober window finder (X11 + Wayland IPC), mss + screenshot-CLI capture
├── input/              XTest (X11), uinput virtual device (Wayland), ydotool, FakeInput
├── vision/             Template store, detector (template+colour), collector, HUD reader
├── farming/            Field / Windy / Stinger / Mixed objectives
├── webhook/            Discord webhook client
└── tests/              Headless unittest suite (85 tests)
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
* On native Wayland, GNOME/KDE users should fullscreen Sober (no CLI window
  query there); screenshot-based capture is slower than mss.
* Using macros violates Roblox ToS and can get your account banned. This is
  for educational/personal automation experimentation. You assume all risk.
