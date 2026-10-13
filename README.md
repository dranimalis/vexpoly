# VEXPOLY

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)"  srcset="docs/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/logo-light.svg">
    <img src="docs/logo-dark.svg" alt="VEXPOLY" width="420">
  </picture>
</p>

<h3 align="center">NO ENGINE. NO SHORTCUTS. JUST POLYGONS.</h3>

<p align="center">
  A first-person arena shooter powered by a custom software renderer.
  <br>
  Built from scratch with Python and Pygame. No conventional 3D engine. No OpenGL rendering pipeline.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Rendering-Software-555555?style=flat-square" alt="Software rendering">
  <img src="https://img.shields.io/badge/Engine-Custom-222222?style=flat-square" alt="Custom engine">
  <img src="https://img.shields.io/badge/License-MIT-D9C15A?style=flat-square" alt="MIT License">
</p>

---

## Overview

**VEXPOLY** is an experimental first-person arena shooter that explores a simple question:

*How far can you push 3D graphics without a conventional graphics engine?*

Rather than delegating 3D rendering to an established engine, VEXPOLY implements its own CPU-based rendering pipeline in Python. Three-dimensional geometry is transformed into camera space, clipped, projected, shaded, fog-blended, sorted, and drawn as two-dimensional polygons.

The result is a playable FPS featuring multiple weapons, distinct enemy archetypes, procedural combat encounters, themed arenas, and screen-space effects — all built around a renderer you can inspect, understand, and modify.

**Python handles the game. Pygame handles the window, input, audio, and drawing. VEXPOLY handles the rest.**

## Features

| System | Capabilities |
|---|---|
| **Software renderer** | Camera transforms, near-plane clipping, perspective projection, backface culling, lighting, and fog |
| **Texture pipeline** | UV-based sampling, nearest and bilinear filtering, and mipmapped sampling |
| **Adaptive rendering** | Dynamic render resolution, polygon budgets, and visibility culling |
| **Combat** | Three weapons, four enemy archetypes, recoil, reloads, headshots, and pickups |
| **Arena themes** | Industrial, Void, Crimson, Arctic, and Toxic |
| **Game modes** | Survival, Endless, and Time Attack |
| **Difficulty** | Easy, Normal, Hard, and Nightmare |
| **Post-processing** | Bloom, color grading, vignette, scanlines, and damage effects |
| **Combat feedback** | Hitmarkers, kill feed, directional damage indicators, and screen shake |
| **Progression** | Combo scoring, streaks, twelve achievements, and power-ups |
| **Customization** | FOV, sensitivity, crosshair, HUD colors, inverted Y-axis, and audio volume |

## Gameplay

### Weapons

- **Pistol** — a reliable sidearm for straightforward engagements.
- **Rifle** — automatic fire for sustained damage.
- **Shotgun** — spread-based damage for close-range encounters.

Each weapon has its own firing behavior, ammunition capacity, reload timing, recoil, and spread.

### Enemies

- **Grunt** — the baseline combatant.
- **Runner** — a fast-moving opponent.
- **Brute** — a durable enemy that can withstand more damage.
- **Spitter** — a ranged attacker.

In Survival mode, bosses appear every fifth wave and introduce ground-slam attacks.

### Game modes

| Mode | Objective |
|---|---|
| **Survival** | Survive increasingly difficult enemy waves and defeat periodic bosses. |
| **Endless** | Keep fighting for as long as possible. |
| **Time Attack** | Maximize your score against the clock. |

### Arena themes

<details>
<summary><strong>Industrial</strong></summary>

Steel, machinery, and utilitarian environments.

</details>

<details>
<summary><strong>Void</strong></summary>

Dark, atmospheric spaces with a minimal visual identity.

</details>

<details>
<summary><strong>Crimson</strong></summary>

Aggressive red-toned combat environments.

</details>

<details>
<summary><strong>Arctic</strong></summary>

Cold, pale environments with high-contrast visuals.

</details>

<details>
<summary><strong>Toxic</strong></summary>

Unnatural green tones and hazardous-looking surroundings.

</details>

## The renderer

VEXPOLY's defining feature is its custom software-rendering pipeline.

Instead of relying on a conventional 3D engine to process and render world geometry, the game performs these operations directly in Python.

### Rendering pipeline

```text
World geometry
      |
      v
Camera transformation
      |
      v
Near-plane clipping
      |
      v
Perspective projection
      |
      v
Frustum and backface culling
      |
      v
Lighting and distance fog
      |
      v
Depth sorting and polygon budgeting
      |
      v
pygame.draw.polygon
      |
      v
Screen-space post-processing
      |
      v
Final frame
```

### Geometry generation

The renderer builds its scene using a small set of geometry primitives:

- `queue_ground` — generates visible ground tiles, subdivides nearby surfaces, and skips distant tiles beyond the visibility range.
- `add_cube` — constructs box geometry, handles face orientation and texture coordinates, rejects backfaces, and applies face lighting.
- `add_color_quad` — generates colored geometry for decals and ground details.
- `add_billboard` — creates camera-facing polygons for particles, projectiles, and power-ups.

Generated polygons are passed to `Game._emit_poly` for further processing before being added to the render queue.

### Rendering techniques

| Technique | Purpose |
|---|---|
| Camera transforms | Convert world-space vertices into camera space |
| Near-plane clipping | Prevent geometry crossing the camera plane from projecting incorrectly |
| Perspective projection | Convert 3D coordinates into screen coordinates |
| Frustum culling | Reject geometry outside the viewing area |
| Backface culling | Skip faces directed away from the camera |
| Texture sampling | Apply UV-based textures with supported filtering methods |
| Directional lighting | Shade surfaces according to face orientation |
| Distance fog | Blend distant geometry into the environment |
| Depth sorting | Draw queued polygons back-to-front |
| Polygon budgeting | Limit the amount of geometry submitted for rendering |

### Post-processing

After the main scene is rendered, VEXPOLY applies screen-space effects, including:

- Bright-pass bloom with downsampling and additive blending.
- Color grading.
- Vignette.
- Scanlines.
- Damage overlays.
- Hit-related visual effects.

These effects are implemented within the game's rendering workflow rather than delegated to a conventional 3D engine.

## Performance

VEXPOLY uses adaptive rendering to manage the cost of software-based polygon drawing.

| Setting | Configured behavior |
|---|---|
| Render scale | Dynamically adjusts between 0.55× and 1.00× |
| Polygon budget | Dynamically adjusts between 900 and 4,000 |
| Geometry ordering | Prioritizes rendering through back-to-front depth sorting |
| Ground detail | Subdivides nearby ground tiles to improve texture detail |
| Visibility | Culls distant ground tiles according to the configured fog range |

Actual performance depends on CPU speed, screen resolution, scene complexity, and configuration. These mechanisms help manage rendering workload but do not guarantee a particular frame rate.

## Installation

### Requirements

- Python 3.8 or newer.
- `pygame-ce` 2.5 or newer, recommended.
- Alternatively, Pygame 2.0 or newer, if supported by your checkout.

VEXPOLY uses the standard `pygame` import interface. No separate game engine, graphics API setup, or compilation step is required.

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/vexpoly.git
cd vexpoly
```

Replace `YOUR_USERNAME` with the GitHub account or organization hosting the repository.

### 2. Create a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows**

```powershell
py -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Launch the game

```bash
python arena_fps.py
```

That's it. The repository includes the game's bundled assets, so no separate asset download is required.

## Controls

### Gameplay

| Action | Input |
|---|---|
| Move | `W` `A` `S` `D` |
| Sprint | `Shift` |
| Jump | `Space` |
| Look around | Mouse |
| Fire | Left mouse button |
| Reload | `R` or right mouse button |
| Select pistol | `1` |
| Select rifle | `2` |
| Select shotgun | `3` |
| Cycle weapons | `Q` / `E` |
| Pause | `Esc` |
| Toggle mouse capture | `F` |
| Toggle fullscreen | `F11` |
| Return to menu after death | `Space` |

### Menus

| Action | Input |
|---|---|
| Navigate | `↑` / `↓` |
| Adjust settings | `←` / `→` |
| Confirm | `Enter` |
| Go back | `Esc` |

## Customization and progression

VEXPOLY includes several ways to customize the experience and track progress.

**Settings**
- Crosshair style, color, size, gap, and thickness.
- HUD accent color.
- Field of view.
- Mouse sensitivity and inverted vertical movement.
- Audio volume.

**Combat and progression**
- Combo and streak scoring.
- Twelve achievements.
- Health and ammunition pickups.
- Rapid Fire, Double Damage, and Shield power-ups.
- Four difficulty settings affecting combat parameters and score rewards.

Settings and records are stored locally in `vexpoly_save.json`. Keep generated save data out of version control.

## Project structure

```text
vexpoly/
├── arena_fps.py
├── requirements.txt
├── README.md
├── LICENSE
├── ROADMAP.md
├── CONTRIBUTING.md
└── assets/
    ├── textures/
    │   ├── _shared/
    │   └── <theme>/
    ├── sounds/
    │   └── *.wav
    └── ui/
        ├── crosshair_*.png
        ├── muzzle_flash.png
        ├── glow.png
        └── lens_dirt.png
```

The renderer, gameplay logic, interface, and audio systems currently live in `arena_fps.py`. This single-file structure keeps the project easy to run while leaving room for future modularization.

The local `vexpoly_save.json` file is generated at runtime and should be excluded from version control.

## Contributing

Contributions are welcome — whether you're improving the renderer, tuning combat, refining the interface, or exploring new graphics techniques.

### Workflow

1. Read [CONTRIBUTING.md](CONTRIBUTING.md).
2. Fork the repository.
3. Create a branch for your changes.
4. Implement and test your changes.
5. Open a pull request explaining the changes and their impact.

For a manageable starting point, browse the [`good first issue`](../../labels/good%20first%20issue) label.

Before submitting a pull request, launch the game and verify the affected functionality:

```bash
python arena_fps.py
```

For rendering changes, also check for visual artifacts, incorrect clipping, and unexpected performance regressions.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned improvements.

Current areas of interest include:

- Refactoring the single-file implementation into dedicated modules.
- Configurable key bindings.
- Additional enemy types, including flying enemies.
- A dedicated user-data directory for saves and settings.
- Further rendering and performance optimizations.

Ideas, bug reports, and constructive feedback are welcome.

## License

VEXPOLY is released under the [MIT License](LICENSE).

You can use, modify, and redistribute the project in accordance with the license terms.

## Credits

- [pygame-ce](https://github.com/pygame-community/pygame-ce) — input, audio, window management, and polygon drawing.
- VEXPOLY's bundled textures, sound effects, and interface assets.

Review the repository's asset documentation for any additional third-party attribution requirements.

---

<p align="center">
  <strong>VEXPOLY</strong>
  <br>
  <sub>SOFTWARE-RENDERED ARENA COMBAT</sub>
  <br><br>
  <code>NO ENGINE. NO SHORTCUTS. JUST POLYGONS.</code>
</p>