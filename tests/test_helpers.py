"""Focused regression tests for deterministic VEXPOLY helpers."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import vexpoly as game


def test_version_and_entrypoint_are_available():
    assert game.VERSION
    assert callable(game.main)
    assert game.Game


def test_lerp_color_endpoints():
    a = (10, 20, 30)
    b = (110, 120, 130)
    assert game.lerp_color(a, b, 0.0) == a
    assert game.lerp_color(a, b, 1.0) == b


def test_ray_aabb_hit_and_miss():
    bounds_min = (-1.0, -1.0, 4.0)
    bounds_max = (1.0, 1.0, 6.0)
    assert game.ray_aabb(0, 0, 0, 0, 0, 1, bounds_min, bounds_max) == 4.0
    assert game.ray_aabb(5, 0, 0, 0, 0, 1, bounds_min, bounds_max) is None


def test_near_plane_clipping_keeps_visible_polygon_in_front():
    corners = [
        (0.0, 0.0, 0.1, 0.0, 0.0),
        (1.0, 0.0, 1.0, 1.0, 0.0),
        (0.0, 1.0, 1.0, 0.0, 1.0),
    ]
    clipped = game.clip_near_poly(corners)
    assert len(clipped) >= 3
    assert all(point[2] >= game.NEAR for point in clipped)


def test_texture_sampler_returns_expected_corner():
    texture = [
        [(255, 0, 0), (0, 255, 0)],
        [(0, 0, 255), (255, 255, 255)],
    ]
    assert game.sample_tex_bilinear([texture], 0.0, 0.0, 0.0) == (255.0, 0.0, 0.0)


def test_user_data_dir_uses_platform_conventions():
    assert game._get_user_data_dir(
        home="/home/tester", platform="linux", environ={}
    ) == "/home/tester/.local/share/vexpoly"
    assert game._get_user_data_dir(
        home="/home/tester",
        platform="linux",
        environ={"XDG_DATA_HOME": "/tmp/test-data"},
    ) == "/tmp/test-data/vexpoly"
    assert game._get_user_data_dir(
        home="/Users/tester", platform="darwin", environ={}
    ) == "/Users/tester/Library/Application Support/VEXPOLY"
    assert game._get_user_data_dir(
        home="C:/Users/tester",
        platform="win32",
        environ={"LOCALAPPDATA": "C:/Users/tester/AppData/Local"},
    ) == "C:/Users/tester/AppData/Local/VEXPOLY"


def test_user_data_dir_ignores_relative_xdg_path():
    assert game._get_user_data_dir(
        home="/home/tester",
        platform="linux",
        environ={"XDG_DATA_HOME": "relative/path"},
    ) == "/home/tester/.local/share/vexpoly"

