# Changelog

All notable changes to this project are documented here.
The format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions use
[Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- Initial repository scaffolding: README, CONTRIBUTING, ROADMAP, LICENSE,
  Code of Conduct, issue and pull request templates, and a CI smoke test.
- Logo assets (SVG and PNG) in `docs/`.
- `pyproject.toml` for editable installs.

### Changed
- Project renamed from the working title **ARENA** to **VEXPOLY**.
- `arena_fps.py` renamed to `vexpoly.py`.
- Save file renamed from `arena_save.json` to `vexpoly_save.json`.

---

## [3.4.1]

### Fixed
- Ground subdivision could explode to 256 polygons per tile because the
  recursive subdivider had no leaf cap. `max_n` reduced 4 to 3, area threshold
  raised from 1600 to 3600, `SUBDIV_DIST` tightened from 26 to 24.
- Sky projection blew up when looking straight up or down. `tp` is now clamped
  to plus or minus 4, which stops the whole-screen flash that happened at the
  poles.
- Outline depth threshold lowered from 42 to 24 so far geometry stops drawing
  roughly twice the outline passes.

### Changed
- Frustum culling: polygons fully off-screen are now dropped before the sort
  and draw stage instead of being pushed and discarded afterwards.
- `draw_blob_shadows` no longer calls `pygame.transform.scale` per entity per
  frame. Scaled sprites are cached and quantised by pixel radius.
- Bloom now does a real bright-pass (`BLEND_RGB_SUB` threshold) instead of a
  whole-image `MULT` darken that washed everything out.
- Sky and grade gradients are reused directly when render scale equals 1.0,
  instead of being smoothscaled to their own size.
- `self._render` is cleared in place with `list.clear` instead of being
  rebound every frame.

---

## [3.4]

### Added
- Borderless fullscreen via F11 using `pygame.SCALED`. Internal coordinates
  stay at 960 by 600 and SDL handles the scaling, so nothing in the renderer
  needs to know about the display size.
- Fullscreen exposed as a SETTINGS toggle, persisted in the save file, and
  applied at startup.

### Fixed
- Semi-auto weapons (pistol and shotgun) now actually fire on click. Prior to
  this, only automatic weapons responded to mouse input.

### Changed
- Version centralised in a `VERSION` constant at the top of the file.

---

## [3.3.2]

### Fixed
- Font rendering uses `pygame.font.Font(None, size)` instead of
  `pygame.font.SysFont` with bold enabled. SysFont was inconsistent across
  platforms.
- Removed the overly dark double vignette that was crushing the corners.

### Changed
- Bloom switched to a bright-pass implementation.

---

## [3.3.1]

### Fixed
- `new_run()` now reallocates render surfaces when the scale resets, which
  fixes a one-frame stretch that appeared when starting a new run from a
  lowered scale.
- `glow=True` is now actually implemented in `add_quad` and `_emit_poly`.
  Previously the flag was accepted and ignored.

---

## [3.3]

### Fixed
- Polygon budget now keeps the *closest* polygons instead of the first ones
  added, which was dropping geometry right in front of the player.
- Ground tile bounds use `math.floor` and `math.ceil` so the near edge of the
  grid does not pop in and out.
- `NEAR` raised from 0.16 to 0.30, which fixes texture warping on geometry
  very close to the camera.
- Screen coordinates are clamped after near-clip, so a single bad vertex
  cannot produce a million-pixel triangle.
- `_frame_avg` is reset on `new_run()`.

### Changed
- `render_scale` is quantised and stepped every 12 frames instead of every
  frame. This stops the scale from oscillating around the target.

---

## [3.2]

### Added
- Adaptive render scale and polygon budget, driven by a rolling frame
  average.
- Distance fog, bright-pass bloom, colour grading, vignette and scanline
  post-processing.
- Five themes: Industrial, Void, Crimson, Arctic, Toxic.
- Three weapons, four enemy types, boss waves, three game modes and four
  difficulty settings.
- Twelve achievements, combo scoring, kill feed and damage direction
  indicator.

---

## [3.0]

### Added
- First playable build. Custom software renderer: camera transform, near
  clipping, perspective projection, backface culling, texture sampling and
  depth sorting, all in pure Python.
- Ground tile grid, crates, pillars and billboarded particles.
- Basic enemy AI and a survival wave loop.

---

## [2.x]

Prototype. Not released. Experimented with raycaster-style column rendering
before moving to the polygon approach used in 3.0.

---

## [1.x]

Initial exploration. Not released. A few hundred lines of code that drew a
rotating wireframe cube in a pygame window.

---

[Unreleased]: https://github.com/dranimalis/vexpoly/compare/v3.4.1...HEAD
[3.4.1]: https://github.com/dranimalis/vexpoly/compare/v3.4...v3.4.1
[3.4]: https://github.com/dranimalis/vexpoly/compare/v3.3.2...v3.4
[3.3.2]: https://github.com/dranimalis/vexpoly/compare/v3.3.1...v3.3.2
[3.3.1]: https://github.com/dranimalis/vexpoly/compare/v3.3...v3.3.1
[3.3]: https://github.com/dranimalis/vexpoly/compare/v3.2...v3.3
[3.2]: https://github.com/dranimalis/vexpoly/compare/v3.0...v3.2
[3.0]: https://github.com/dranimalis/vexpoly/releases/tag/v3.0