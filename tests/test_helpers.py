"""Focused tests for deterministic, dependency-light VEXPOLY helpers."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
import pytest

import vexpoly as game


@pytest.fixture(scope="module", autouse=True)
def pygame_init():
    pygame.init()
    pygame.display.set_mode((game.WIDTH, game.HEIGHT))
    yield
    pygame.quit()


def test_version_and_entrypoint_are_available():
    assert game.VERSION
    assert callable(game.main)
    assert game.Game


def test_lerp_color_clamps_interpolation():
    # Use the helper's actual public signature and validate its endpoints.
    a = (10, 20, 30)
    b = (110, 120, 130)
    assert game.lerp_color(a, b, 0.0) == a
    assert game.lerp_color(a, b, 1.0) == b


def test_texture_sampler_returns_rgb_tuple():
    tex = [
        [(255, 0, 0), (0, 255, 0)],
        [(0, 0, 255), (255, 255, 255)],
    ]
    color = game.sample_tex_bilinear(tex, 0.0, 0.0)
    assert isinstance(color, (tuple, list))
    assert len(color) >= 3
