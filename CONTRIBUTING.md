# Contributing to VEXPOLY

Thanks for wanting to help. This is a small hobby project, and every
contribution — code, art, balance tweaks, bug reports, screenshots — makes it
better.

---

## Getting set up

```bash
git clone https://github.com/dranimalis/vexpoly.git
cd vexpoly

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt

python vexpoly.py
```

You should be looking at the main menu. `WASD` plus mouse to play, `Esc` to
pause.

### Python and pygame versions

- **Python 3.9 or newer is required.** 3.10 through 3.13 are the most
  well-tested. Python 3.14 works, but only with `pygame-ce`.
- **`pygame-ce` 2.5 or newer is recommended.** It is a drop-in replacement
  for `pygame` and ships prebuilt wheels for Python 3.9 through 3.14. The
  original `pygame` package does not have wheels for newer interpreters yet,
  so `pip install pygame` will try to build from source and fail unless SDL2
  development headers are installed.
- Because both packages expose the same `import pygame` interface,
  **never install them side by side**. Pick one. Use `pygame-ce`.

---

## What to work on

- **Bugs** — open an issue using the bug report template. Include your OS,
  Python version, pygame version, and a repro if you can.
- **Balance** — damage numbers, enemy speed, spawn rates, powerup durations,
  difficulty scaling. These live in `WEAPONS`, `ENEMY_TYPES`, `POWERUPS` and
  `DIFFICULTIES` near the top of `vexpoly.py`.
- **New content** — enemy types, weapons, themes, achievements. Adding a new
  theme means editing `THEMES` and dropping a texture folder under
  `assets/textures/<name>/`.
- **Renderer** — performance wins in `_emit_poly`, better culling, sub-tile
  LOD, cheaper fog blending. Benchmark before and after using the `fps` and
  `polys` counters in the menu footer.
- **Refactoring** — see [ROADMAP.md](ROADMAP.md). Splitting the monolith into
  modules is a big, welcome task.

If you are unsure where to start, look for the
[`good first issue`](../../labels/good%20first%20issue) label.

---

## Code style

There is no linter config and no formatter running in CI. Just be sensible and
match the surrounding code.

- **4 spaces, no tabs.** See `.editorconfig`.
- **UTF-8 encoding, LF line endings.** See `.editorconfig`.
- Keep lines under roughly 100 characters.
- Module-level constants are `SCREAMING_SNAKE_CASE`.
- Private helpers on `Game` use a leading underscore, for example
  `_emit_poly`, `_to_cam_5`, `_fog_blend`.
- Hoist repeated lookups out of hot loops:
  ```python
  dp = pygame.draw.polygon
  for depth, pts, col, outline in draw_list:
      dp(scr, col, pts)
  ```
  This game is CPU-bound. Micro-optimisations that keep the frame budget are
  genuinely welcome, as long as they do not hurt readability for the rest of
  the renderer.
- Prefer plain `for` loops and lists over comprehensions inside the render
  path. The allocation cost shows up.
- **Do not add dependencies.** The whole point of this project is "Python
  plus pygame, nothing else". If a change feels like it needs numpy or PyOpenGL
  to be worth it, open an issue to discuss first.

---

## Testing

There is no test suite yet. For now, testing means playing the game.

Before submitting a pull request:

1. Run `python vexpoly.py` and confirm the game launches into the menu.
2. Play at least one full wave on the difficulty you touched.
3. Check the `fps` and `polys` counters in the menu footer have not regressed
   compared to the `main` branch.
4. If you changed the renderer, walk the whole arena and look at the ground
   and every wall type from a few different distances.
5. If you changed a theme, cycle through all five and confirm nothing looks
   broken.

A headless smoke test runs on CI
(`.github/workflows/smoke-test.yml`) and verifies the module imports cleanly
across Python 3.9, 3.11 and 3.12, and that `./assets/` is present. If you add
a real test suite, wire it into that workflow.

---

## Commits and pull requests

- Small, focused commits with a clear message:
  - `Add flying enemy type`
  - `Fix shotgun spread resetting on weapon switch`
  - `Reduce bloom threshold from 170 to 150`
- One feature or fix per pull request. If a change touches both balance and
  the renderer, split it.
- Fill in the PR template. A screenshot or a short clip helps enormously for
  anything visual.
- Reference the issue you are closing with `Closes #42`.
- If your change is likely to be controversial — new gameplay mechanic,
  rebalance that shifts the whole game, refactor that touches many files —
  open an issue first and get a thumbs up before spending time on the code.

---

## Adding assets

Textures, sounds and UI sprites live under `./assets/` and are committed to
the repo. If you want to contribute art:

- **Textures** go in `assets/textures/<theme>/` and must be 32 by 32 PNGs.
  Anything larger is smooth-scaled down on load, which looks worse than
  authoring at 32 by 32 to begin with.
- **Enemy textures** go in `assets/textures/_shared/` and are used by all
  themes.
- **Sounds** go in `assets/sounds/` and must be mono 16-bit WAV at 22050 Hz.
  That matches what `generate_sounds` synthesises, so the mixer settings do
  not need to change.
- **UI sprites** go in `assets/ui/`. Crosshair sprites are 64 by 64 RGBA with
  the origin at the centre.

In the pull request, say which licence the art is under (CC0, MIT, your own,
etc.) and confirm you have the right to contribute it. Do not paste in assets
you found on a random site.

---

## Reporting bugs

The bug report template asks for the essentials. If you want to save a round
trip, include:

- OS and version (for example "Windows 11 23H2" or "Ubuntu 24.04")
- Python version (`python --version`)
- pygame or pygame-ce version
  (`python -c "import pygame; print(pygame.version.ver)"`)
- The exact steps you took
- What you expected to happen
- What actually happened
- Any traceback from the terminal

A 10-second clip of the bug happening is worth more than three paragraphs of
description, especially for rendering artefacts.

---

## Questions

Open a discussion or an issue. There is no such thing as a dumb question here.
If something in the codebase is unclear, that is a documentation bug and worth
fixing.