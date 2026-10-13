# VEXPOLY

VEXPOLY is a Python arena FPS project.

## Project layout

Keep the game entry point and game module at the repository root, with assets in `assets/`:

```text
VEXPOLY/
├── assets/
│   ├── sounds/
│   ├── textures/
│   └── ui/
├── arena_fps.py
├── main.py
├── generate_assets.py
├── arena_save.json
└── vexpoly_save.json
```

## Run

From the repository root, run:

```bash
python main.py
```

Install the dependencies required by the project before running it. Add them to `requirements.txt` once confirmed from the imports in the game source.

## Assets and saves

Keep the original asset folder names and paths intact; the game may load them relative to the source files. Save JSON files may contain local progress or settings, so review them before publishing personal data.

## Status

The repository setup/README is prepared, but the actual Python source files and binary assets must be uploaded from the original project before the game can run from this repository.
