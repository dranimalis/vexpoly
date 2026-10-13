# Roadmap

This is a wish list, not a commitment. Items are ordered roughly by priority.
If something on here excites you, open an issue and claim it so we don't
duplicate work.

---

## Near term

- [ ] **Split `vexpoly.py` into a package.** The whole game currently lives in
  one file, which is great for copy-pasting and terrible for navigation.
  Target layout:

  ```
  vexpoly/
    __init__.py
    renderer.py     projection, clipping, _emit_poly, add_cube, add_billboard
    textures.py     noise, mip chain, bilinear sampling
    audio.py        synth and the SND registry
    world.py        crates, pillars, decals, arena constants
    entities.py     enemy, particle, projectile and pickup update logic
    weapons.py      WEAPONS, fire, trace_shot
    hud.py          crosshair, health bar, kill feed, toasts
    menu.py         menu pages and input
    game.py         the Game class and run loop
  ```

  Keep it a single importable module from the outside, so
  `import vexpoly` still works and `python vexpoly.py` still launches
  the game.

- [ ] **Configurable key bindings.** Move the `pygame.K_*` literals out of
  `handle_event` and `update_player` into a `KEYBINDS` dict that is
  persisted in the save file, with a menu page to rebind. This is the most
  requested feature by players on non-QWERTY layouts.

- [ ] **Move the save file to a proper user-data directory.** Use
  `platformdirs` so `vexpoly_save.json` lands in the right place on Windows,
  macOS and Linux, with a migration path from the current repo-root location.

- [ ] **Real test suite.** At minimum, pure-function tests for `ray_aabb`,
  `clip_near_poly`, `lerp_color`, `sample_tex_bilinear` and the LOD table.
  `pytest`, headless, wired into the CI workflow that already runs.

---

## Medium term

- [ ] **Flying enemy type.** A bobbing, hovering drone that ignores the
  ground-plane collision and dives at the player. Needs a 3-axis update path
  in `update_enemies`, a shadow that shrinks with altitude in
  `draw_blob_shadows`, and a ranged attack variant.

- [ ] **More themes.** Cyberpunk neon, overgrown ruins, underwater lab. Each
  is a `THEMES` entry plus a folder under `assets/textures/<name>/` with the
  six standard textures.

- [ ] **Weapon variety.** A charge-up energy weapon, and a melee or kick
  secondary for when you are completely dry. The energy weapon needs a new
  fire path; the kick can reuse `trace_shot` with a tiny range.

- [ ] **Custom arena presets.** Seed-based layout generators for crates and
  pillars so runs are replayable from a short shareable string.

- [ ] **Better bloom.** The current bright-pass is a single quarter-resolution
  downsample and re-upscale. Try a two-pass gaussian at one quarter and one
  eighth, summed. Should look smoother for the same cost.

- [ ] **Palette quantisation pass.** A post-render per-pixel quantisation for
  a stylistic "low-colour" mode. Toggle in the settings menu.

- [ ] **Wave intro cinematics.** A brief camera fly-through of the spawn ring
  before a boss wave, so the player has a beat to breathe.

- [ ] **Persistent run statistics.** Track total kills, time played, favourite
  weapon, longest streak across sessions.

---

## Long term and exploratory

- [ ] **Web build via [pygbag](https://github.com/pygame-web/pygbag)** so
  people can play without installing anything. Would need a per-frame budget
  review — WASM is noticeably slower than native, and the adaptive scaler may
  need re-tuning.

- [ ] **Level editor.** An in-game grid painter that serialises to JSON and
  can be loaded as a custom arena.

- [ ] **Deterministic replay system.** Record input plus a seed, play it back
  frame-for-frame. This is a prerequisite for co-op.

- [ ] **Co-op.** Two players in the same arena. Not before determinism exists,
  because desyncs in a software renderer are miserable to debug.

- [ ] **Ray-traced ambient occlusion.** March a few short rays per face from
  the face centre in `face_light`. Almost certainly too expensive in pure
  Python, but worth prototyping to see how bad it gets.

---

## Non-goals

- **Do not add a hard dependency on a 3D library.** PyOpenGL, moderngl,
  panda3d, Ursina, whatever — the whole point of VEXPOLY is that it renders
  with `pygame.draw.polygon`. If you want a real engine, there are a hundred
  better projects for that.

- **Do not add a hard dependency on numpy.** Numpy would help enormously with
  vertex transforms and texture sampling, and it is the single most tempting
  optimisation in the whole codebase. But it also changes what the project is.
  If you want to prove a point, do it in a fork.

- **Do not bundle assets that are not freely licensed.** Every texture, every
  sound, every UI sprite in this repo has to be either generated here or
  under a licence that permits redistribution. No ripped sprites.

- **No microtransactions, no telemetry, no network calls.** This is a hobby
  project. It is offline forever.

---

## How to propose a change to this roadmap

Open an issue with the `roadmap` label. Describe what you want to add, why it
fits the project, and roughly how much work you think it is. If it lands, it
goes on this file and someone — possibly you — can pick it up.