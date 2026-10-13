#!/usr/bin/env python3
"""
Render VEXPOLY logo PNGs from the same geometry as docs/logo-*.svg.

Outputs into docs/:
    logo-dark.png      horizontal lockup, light text
    logo-light.png     horizontal lockup, dark text
    logo-mark.png      1024x1024 icon, transparent background
    logo-mark-solid.png 1024x1024 icon on dark rounded square
    social-preview.png  1280x640 banner (GitHub repo social image)

Run:  python generate_logo_png.py
"""

import math
import os
import pygame

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs")
os.makedirs(OUT, exist_ok=True)

# --- palette -----------------------------------------------------------------
DARK_TEXT = (242, 247, 255)
LIGHT_TEXT = (11, 18, 32)
BG_SOLID = (11, 18, 32)

# Facet colors, top-left light source. (dark variant, light variant)
FACETS_DARK = [
    ((142, 244, 255), (110, 224, 245)),  # upper-left
    ((79, 184, 240),  (46, 147, 214)),   # upper-right
    ((30, 95, 168),   (15, 74, 138)),    # lower-left
    ((14, 60, 122),   (8, 43, 92)),      # lower-right
]

# The four facets, in a 100x100 space.
FACET_POINTS = [
    ((50, 8), (8, 68), (50, 52)),
    ((50, 8), (50, 52), (92, 68)),
    ((8, 68), (50, 92), (50, 52)),
    ((50, 52), (92, 68), (50, 92)),
]


def draw_mark(surf, ox, oy, size, light=False):
    """Draw the shard at (ox, oy) occupying `size` x `size` pixels."""
    scale = size / 100.0
    for (pts, (dark_col, light_col)) in zip(FACET_POINTS, FACETS_DARK):
        col = light_col if light else dark_col
        poly = [(ox + x * scale, oy + y * scale) for (x, y) in pts]
        pygame.draw.polygon(surf, col, poly)


def pick_font(size):
    """Try a few common heavy sans fonts before falling back to default."""
    for name in ("inter-black", "inter", "dejavusans", "arial", "helvetica"):
        try:
            f = pygame.font.SysFont(name, size, bold=True)
            if f:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, int(size * 1.15))


def render_wordmark(text, size, color):
    font = pick_font(size)
    # letter-spacing is faked by rendering each glyph and offsetting
    gap = int(size * 0.08)
    glyphs = []
    for ch in text:
        g = font.render(ch, True, color)
        glyphs.append(g)
    total_w = sum(g.get_width() for g in glyphs) + gap * (len(glyphs) - 1)
    h = max(g.get_height() for g in glyphs)
    surf = pygame.Surface((total_w, h), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        surf.blit(g, (x, 0))
        x += g.get_width() + gap
    return surf


def make_lockup(light=False, width=1280, height=320):
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pad = int(height * 0.20)
    mark_size = height - pad * 2
    draw_mark(surf, pad, pad, mark_size, light=light)

    text_col = LIGHT_TEXT if light else DARK_TEXT
    wm_size = int(mark_size * 0.96)
    wm = render_wordmark("VEXPOLY", wm_size, text_col)

    # vertically center the cap height against the mark
    tx = pad + mark_size + int(height * 0.14)
    ty = (height - wm.get_height()) // 2
    surf.blit(wm, (tx, ty))

    # crop to content so there's no wasted right-side space
    right = tx + wm.get_width() + pad
    return surf.subsurface((0, 0, min(right, width), height)).copy()


def make_mark(size=1024, solid=False):
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    if solid:
        r = int(size * 0.19)
        pygame.draw.rect(surf, BG_SOLID, (0, 0, size, size), border_radius=r)
        pad = int(size * 0.14)
    else:
        pad = 0
    draw_mark(surf, pad, pad, size - pad * 2)
    return surf


def make_social(width=1280, height=640):
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    # solid dark background
    surf.fill(BG_SOLID)

    # subtle vignette-ish gradient (top lighter)
    for y in range(height):
        t = y / height
        a = int(28 * (1 - t))
        if a > 0:
            line = pygame.Surface((width, 1), pygame.SRCALPHA)
            line.fill((60, 140, 220, a))
            surf.blit(line, (0, y))

    # centered mark
    mark_size = int(height * 0.42)
    mx = (width - mark_size) // 2
    my = int(height * 0.14)
    draw_mark(surf, mx, my, mark_size)

    # centered wordmark
    wm = render_wordmark("VEXPOLY", int(mark_size * 0.72), DARK_TEXT)
    wx = (width - wm.get_width()) // 2
    wy = my + mark_size + int(height * 0.045)
    surf.blit(wm, (wx, wy))

    # tagline
    try:
        tag_font = pygame.font.SysFont("dejavusans", int(height * 0.032))
    except Exception:
        tag_font = pygame.font.Font(None, int(height * 0.035))
    tag = tag_font.render("NO ENGINE. NO SHORTCUTS. JUST POLYGONS.",
                          True, (120, 200, 240))
    tx = (width - tag.get_width()) // 2
    ty = wy + wm.get_height() + int(height * 0.05)
    surf.blit(tag, (tx, ty))
    return surf


def save(surf, name):
    path = os.path.join(OUT, name)
    pygame.image.save(surf, path)
    print("wrote", os.path.relpath(path, ROOT))


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))  # required for font subsystem

    save(make_lockup(light=False), "logo-dark.png")
    save(make_lockup(light=True),  "logo-light.png")
    save(make_mark(1024, solid=False), "logo-mark.png")
    save(make_mark(1024, solid=True),  "logo-mark-solid.png")
    save(make_social(), "social-preview.png")

    pygame.quit()
    print("\nDone — see ./docs/")


if __name__ == "__main__":
    main()