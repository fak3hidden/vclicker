# bssmacro — Bee Swarm Simulator macro for Linux

A single, integrated **Bee Swarm Simulator** automation macro for **Linux**,
in the spirit of Revolution/Natro, built to drive the game through **Sober**
(Roblox on Linux). Works on **X11, XWayland and native Wayland**.

> Full documentation lives in [`bssmacro/README.md`](bssmacro/README.md) —
> setup, Wayland permissions, priorities, config reference, architecture.

## Highlights

- **AI collector** — template matching + colour vision finds tokens, creatures
  and hazards every frame and ranks them by *your* priorities
  (stingers > royal jellies > treats > …), avoiding what you tell it to avoid.
- **Objectives** — field gathering, windy bees, stinger farming (spider hunts),
  or a mix of all three.
- **Honey → hive conversion** with an HSV honey-bar reader.
- **Discord webhook** reporting, Natro-style: heartbeat embeds (uptime, honey
  %, tokens/min, stingers, top items, optional screenshot) + event pings.
- **Linux-native input** — XTest on X11/XWayland; `/dev/uinput` virtual device
  or `ydotool` on native Wayland; no display-server lock-in.
- **Safety** — focus checking, error budget, max runtime.

## Quick start

```bash
git clone https://github.com/fak3hidden/vclicker.git
cd vclicker
python3 -m venv .venv
.venv/bin/pip install -r bssmacro/requirements.txt

.venv/bin/python run_bss.py selftest       # sanity check
.venv/bin/python run_bss.py config         # write ~/.config/bssmacro/config.json
.venv/bin/python run_bss.py webhook-test   # verify Discord
.venv/bin/python run_bss.py calibrate      # crop templates from your Sober window
.venv/bin/python run_bss.py run --fake     # dry run: vision only, no clicks
.venv/bin/python run_bss.py run            # farm!
```

Or install as a package: `pip install .` (provides the `bssmacro` command).

## Repository layout

```
bssmacro/            the macro (package + tests + templates + docs)
run_bss.py           convenience launcher: python run_bss.py <subcommand>
```
