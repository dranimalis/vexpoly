#!/usr/bin/env python3
"""
VEXPOLY 3.4.1  --  adaptive software FPS with fullscreen + render fixes.

Fixes in 3.4.1
    * Ground subdivision was exploding to up to 256 polys per tile because
      the recursive subdivider had no leaf cap.  max_n=4 -> 3, area
      threshold raised 1600 -> 3600, SUBDIV_DIST tightened 26 -> 24.
    * Frustum culling: polys fully off-screen are dropped before sort/draw.
    * draw_blob_shadows no longer calls pygame.transform.scale per entity
      per frame; scaled sprites are cached and quantised by pixel radius.
    * Bloom now does a real bright-pass (BLEND_RGB_SUB threshold) instead
      of a whole-image MULT darken that washed everything out.
    * Sky projection no longer blows up when looking straight up/down
      (tp clamped to +/-4) which used to flash the whole screen.
    * Sky / grade gradients are reused directly when scale == 1.0 instead
      of being smoothscaled to their own size.
    * Outline depth threshold lowered 42 -> 24 so far geometry stops
      drawing ~2x outline passes.
    * self._render cleared in place (list.clear) instead of rebound.

Fixes in 3.4
    * FULLSCREEN: F11 toggles borderless fullscreen using pygame.SCALED,
      so all internal coordinates stay at 960x600 and SDL scales for us.
      Also exposed as SETTINGS toggle, persisted, applied at startup.
    * Semi-auto weapons (PISTOL, SHOTGUN) now actually fire on click.
    * Version centralised in VERSION constant.

Fixes in 3.3.2
    * Font rendering: pygame.font.Font(None, size) instead of SysFont(bold).
    * Removed the overly dark double vignette.
    * Bloom uses bright-pass.

Fixes in 3.3.1
    * new_run() reallocates render surfaces on scale reset.
    * glow=True implemented in add_quad / _emit_poly.

Fixes in 3.3
    * Polygon budget keeps CLOSEST polys.
    * Ground tile bounds use math.floor / math.ceil.
    * NEAR raised 0.16 -> 0.30.
    * Screen coords clamped after near-clip.
    * _frame_avg reset on new_run().
    * render_scale quantised and stepped every 12 frames.
"""

import array, json, math, os, random, sys, wave
import pygame

# ===========================================================================
#  VERSION
# ===========================================================================
VERSION = "3.4.1"

GAME_NAME = "VEXPOLY"

# ===========================================================================
#  CONSTANTS
# ===========================================================================
WIDTH, HEIGHT = 960, 600
HALF_W, HALF_H = WIDTH * 0.5, HEIGHT * 0.5
NEAR = 0.30
TAU = math.pi * 2.0
ARENA, GROUND_HALF, TILE = 34.0, 52.0, 13.0
GRAVITY, EYE_HEIGHT = 20.0, 1.70
FOG_START, FOG_END = 12.0, 78.0
SR = 22050
ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
SETTINGS_PATH = os.path.join(ROOT, "vexpoly_save.json")

try:
    _SCALED = pygame.SCALED
except AttributeError:
    _SCALED = 0

TARGET_FPS      = 60
POLY_BUDGET     = 1800
POLY_BUDGET_MIN = 900
POLY_BUDGET_MAX = 4000
SCALE_MIN       = 0.55
SCALE_MAX       = 1.00
SCALE_STEP      = 0.05
SCALE_COOLDOWN  = 12
PARTICLE_CAP    = 140
SUBDIV_DIST     = 24.0

DIFFICULTIES = [
    ("EASY",      0.70, 0.80, 1.40, 0.85),
    ("NORMAL",    1.00, 1.00, 1.00, 1.00),
    ("HARD",      1.35, 1.20, 0.75, 1.20),
    ("NIGHTMARE", 1.80, 1.40, 0.55, 1.50),
]
MODES = ["SURVIVAL", "ENDLESS", "TIME ATTACK"]

THEMES = {
    "INDUSTRIAL": dict(
        sky_top=(7,9,24), sky_mid=(30,38,78), fog=(46,54,96), dark=(14,16,32),
        ambient=0.32, light_dir=(0.44,0.80,-0.42), grade=(8,10,26),
        folder="industrial", sky_desc="A gritty industrial arena."),
    "VOID": dict(
        sky_top=(10,2,20), sky_mid=(60,20,90), fog=(80,30,110), dark=(22,6,40),
        ambient=0.28, light_dir=(0.35,0.85,-0.30), grade=(24,6,38),
        folder="void", sky_desc="A drifting void fragment."),
    "CRIMSON": dict(
        sky_top=(20,4,8), sky_mid=(80,20,30), fog=(100,30,40), dark=(30,8,12),
        ambient=0.35, light_dir=(0.50,0.75,-0.35), grade=(30,6,10),
        folder="crimson", sky_desc="Blood-red crimson wastes."),
    "ARCTIC": dict(
        sky_top=(15,20,40), sky_mid=(80,100,140), fog=(130,150,180), dark=(30,40,60),
        ambient=0.45, light_dir=(0.30,0.85,-0.45), grade=(20,30,50),
        folder="arctic", sky_desc="A frozen tundra outpost."),
    "TOXIC": dict(
        sky_top=(5,15,5), sky_mid=(30,70,30), fog=(40,80,40), dark=(10,25,10),
        ambient=0.30, light_dir=(0.55,0.70,-0.40), grade=(6,24,8),
        folder="toxic", sky_desc="A toxic wasteland."),
}
THEME_NAMES = list(THEMES.keys())

CROSSHAIR_STYLES = ["CROSS", "DOT", "CIRCLE", "CROSS+DOT", "T-SHAPE"]
CROSSHAIR_COLORS = [("WHITE",(238,246,255)),("RED",(255,90,90)),
                    ("GREEN",(110,255,130)),("CYAN",(110,240,255)),
                    ("MAGENTA",(255,120,220))]
HUD_COLORS = [("BLUE",(110,190,255)),("GREEN",(120,240,160)),
              ("PURPLE",(200,130,255)),("GOLD",(255,200,90)),
              ("CRIMSON",(255,110,110))]

DEFAULT_SETTINGS = {
    "difficulty":1,"mode":0,"theme":0,"sensitivity":1.0,"fov":78,"volume":0.7,
    "invert_y":False,"bloom":True,"scanlines":True,"vignette":True,
    "damage_pulse":True,"fog":True,"shadows":True,"adaptive":True,
    "fullscreen":False,
    "cross_style":3,"cross_color":0,"cross_size":1.0,"cross_gap":1.0,
    "cross_thick":2,"hud_color":0,"achievements":[],
    "best_survival":0,"best_endless":0,"best_kills":0,"best_score":0,
    "time_attack_best":0.0,
}
S = dict(DEFAULT_SETTINGS)

def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            data = json.load(f)
        for k, v in DEFAULT_SETTINGS.items():
            S[k] = data.get(k, v)
    except Exception:
        pass

def save_settings():
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(S, f, indent=2)
    except Exception:
        pass

# ===========================================================================
#  FONT HELPERS
# ===========================================================================
def _make_font(size):
    try:
        return pygame.font.Font(None, size)
    except Exception:
        return pygame.font.SysFont("monospace", size)

# ===========================================================================
#  TEXTURE PIPELINE
# ===========================================================================
TS = 32
TEX_MIPS = {}
TEX = {}

def _i(v): return 0 if v < 0.0 else (255 if v > 255.0 else int(v))

def _noise(size, seed, octaves=3):
    rnd = random.Random(seed)
    out = [[0.0]*size for _ in range(size)]
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        step = max(1, size >> (o+1))
        gn = size // step + 2
        g = [[rnd.uniform(-1,1) for _ in range(gn)] for _ in range(gn)]
        for y in range(size):
            gy = y/step; y0 = int(gy); fy = gy - y0
            fy = fy*fy*(3-2*fy)
            rg0, rg1 = g[y0], g[y0+1]; orow = out[y]
            for x in range(size):
                gx = x/step; x0 = int(gx); fx = gx - x0
                fx = fx*fx*(3-2*fx)
                a = rg0[x0]; b = rg0[x0+1]; c = rg1[x0]; d = rg1[x0+1]
                orow[x] += (a + (b-a)*fx + (c-a)*fy + (a-b-c+d)*fx*fy) * amp
        tot += amp; amp *= 0.5
    inv = 1.0/tot
    for y in range(size):
        r = out[y]
        for x in range(size):
            r[x] *= inv
    return out

def _gen(kind, base, seed):
    n = _noise(TS, seed, 3)
    r0, g0, b0 = base
    def f(x, y):
        v = 1.0 + n[y][x]*0.3
        if kind == "floor":
            if x % 16 == 0 or y % 16 == 0: v -= 0.35
            elif x % 16 == 1 or y % 16 == 1: v += 0.08
        elif kind == "plate":
            cx, cy = x % 16, y % 16
            if cx < 2 or cy < 2 or cx > 13 or cy > 13: v -= 0.3
            if (cx-8)**2 + (cy-8)**2 < 3: v += 0.45
        elif kind == "crate":
            if x < 2 or y < 2 or x > TS-3 or y > TS-3: v -= 0.38
            if abs(x-y) < 2 or abs((x+y)-(TS-1)) < 2: v += 0.18
        elif kind == "pillar":
            if x % 16 < 2 or y % 16 < 2: v -= 0.30
        elif kind == "metal":
            v = 1.0 + n[y][x]*0.2
            if y % 8 == 0: v -= 0.18
            if (x % 16 - 8)**2 + (y % 16 - 8)**2 < 2: v += 0.5
        return (_i(r0*v), _i(g0*v), _i(b0*v))
    return [[f(x, y) for x in range(TS)] for y in range(TS)]

def _load_png(path):
    if not os.path.exists(path):
        return None
    try:
        surf = pygame.image.load(path).convert()
        w, h = surf.get_size()
        if w != TS or h != TS:
            surf = pygame.transform.smoothscale(surf, (TS, TS))
        return [[surf.get_at((x, y))[:3] for x in range(TS)] for y in range(TS)]
    except Exception:
        return None

def _build_mips(tex):
    mips = [tex]
    cur = tex
    while len(cur) > 2:
        size = len(cur); ns = size // 2
        nxt = [[None]*ns for _ in range(ns)]
        for y in range(ns):
            for x in range(ns):
                a = cur[y*2][x*2]; b = cur[y*2][x*2+1]
                c = cur[y*2+1][x*2]; d = cur[y*2+1][x*2+1]
                nxt[y][x] = ((a[0]+b[0]+c[0]+d[0])//4,
                             (a[1]+b[1]+c[1]+d[1])//4,
                             (a[2]+b[2]+c[2]+d[2])//4)
        mips.append(nxt); cur = nxt
    return mips

def _register(name, grid):
    TEX_MIPS[name] = _build_mips(grid)
    TEX[name] = grid

_theme_built = None

def build_textures(theme_idx):
    global _theme_built
    if _theme_built == theme_idx:
        return
    t = THEMES[THEME_NAMES[theme_idx]]
    folder = os.path.join(ASSETS, "textures", t["folder"])
    shared = os.path.join(ASSETS, "textures", "_shared")
    pal = {
        "industrial": dict(ground=(58,64,84), ground2=(46,52,70),
                           crate=(108,90,68), pillar=(74,82,110)),
        "void":       dict(ground=(52,30,74), ground2=(40,22,60),
                           crate=(90,50,120), pillar=(100,60,130)),
        "crimson":    dict(ground=(84,40,40), ground2=(66,30,32),
                           crate=(120,60,50), pillar=(110,60,60)),
        "arctic":     dict(ground=(160,180,200), ground2=(130,150,175),
                           crate=(120,160,190), pillar=(150,190,210)),
        "toxic":      dict(ground=(60,80,50), ground2=(48,66,42),
                           crate=(90,120,60), pillar=(70,100,60)),
    }[t["folder"]]

    def get(name, path, gen_kind, base, seed):
        grid = _load_png(path)
        if grid is None:
            grid = _gen(gen_kind, base, seed)
        _register(name, grid)

    get("floor",  os.path.join(folder, "floor.png"),  "floor",  pal["ground"],  101)
    get("floor2", os.path.join(folder, "floor2.png"), "plate",  pal["ground2"], 102)
    get("plate",  os.path.join(folder, "plate.png"),  "plate",  pal["ground"],  103)
    get("crate",  os.path.join(folder, "crate.png"),  "crate",  pal["crate"],   104)
    get("metal",  os.path.join(folder, "metal.png"),  "metal",  (110,116,130),  105)
    get("pillar", os.path.join(folder, "pillar.png"), "pillar", pal["pillar"],  106)
    get("flesh", os.path.join(shared, "flesh.png"), "plate", (130,52,56),  200)
    get("armor", os.path.join(shared, "armor.png"), "metal", (96,60,122),  201)
    get("skin",  os.path.join(shared, "skin.png"),  "plate", (78,110,92),  202)

    _theme_built = theme_idx

def sample_tex_bilinear(mips, u, v, lod):
    li = int(lod + 0.5)
    if li >= len(mips): li = len(mips) - 1
    if li < 0: li = 0
    t = mips[li]
    size = len(t); mask = size - 1
    fu = u * size; fv = v * size
    x0 = int(math.floor(fu)) & mask
    y0 = int(math.floor(fv)) & mask
    x1 = (x0 + 1) & mask
    y1 = (y0 + 1) & mask
    tx = fu - math.floor(fu)
    ty = fv - math.floor(fv)
    c00 = t[y0][x0]; c10 = t[y0][x1]
    c01 = t[y1][x0]; c11 = t[y1][x1]
    w00 = (1-tx)*(1-ty); w10 = tx*(1-ty)
    w01 = (1-tx)*ty;     w11 = tx*ty
    return (c00[0]*w00 + c10[0]*w10 + c01[0]*w01 + c11[0]*w11,
            c00[1]*w00 + c10[1]*w10 + c01[1]*w01 + c11[1]*w11,
            c00[2]*w00 + c10[2]*w10 + c01[2]*w01 + c11[2]*w11)

def sample_tex_nearest(mips, u, v):
    t = mips[-1]
    size = len(t); mask = size - 1
    x = int(u * size) & mask
    y = int(v * size) & mask
    return t[y][x]

# ===========================================================================
#  AUDIO
# ===========================================================================
SND = {}

def _load_wav(name):
    p = os.path.join(ASSETS, "sounds", name + ".wav")
    if not os.path.exists(p): return None
    try: return pygame.mixer.Sound(p)
    except Exception: return None

def _mk_snd(dur, fn):
    n = int(dur * SR)
    buf = array.array("h", bytes(2 * n))
    for i in range(n):
        v = fn(i/SR)
        if v > 1.0: v = 1.0
        elif v < -1.0: v = -1.0
        buf[i] = int(v * 30000)
    return pygame.mixer.Sound(buffer=buf.tobytes())

def build_sounds():
    rnd = random.Random(5)
    def ne(t, d, decay): return rnd.uniform(-1,1)*(1-t/d)**decay
    specs = {
        "pistol":  (0.11, lambda t: ne(t,0.11,8)*0.55 + math.sin(t*340*TAU)*0.35*(1-t/0.11)**6),
        "shotgun": (0.22, lambda t: ne(t,0.22,5)*0.80 + math.sin(t*120*TAU)*0.40*(1-t/0.22)**4),
        "rifle":   (0.08, lambda t: ne(t,0.08,10)*0.45 + math.sin(t*480*TAU)*0.30*(1-t/0.08)**7),
        "hit":     (0.07, lambda t: math.sin(t*1400*TAU)*0.4*(1-t/0.07)**4),
        "kill":    (0.30, lambda t: math.sin(t*(520-900*t)*TAU)*0.5*(1-t/0.30)**2),
        "hurt":    (0.26, lambda t: ne(t,0.26,3)*0.4 + math.sin(t*90*TAU)*0.5*(1-t/0.26)**3),
        "pickup":  (0.20, lambda t: math.sin(t*(600+1400*t)*TAU)*0.4*(1-t/0.20)**2),
        "powerup": (0.45, lambda t: math.sin(t*(400+1500*t)*TAU)*0.35*(1-t/0.45)**1.5
                                  + math.sin(t*(600+1800*t)*TAU)*0.20*(1-t/0.45)**1.5),
        "reload":  (0.30, lambda t: math.sin(t*220*TAU)*0.3*math.exp(-((t-0.02)*40)**2)
                                  + math.sin(t*300*TAU)*0.3*math.exp(-((t-0.20)*40)**2)),
        "wave":    (0.65, lambda t: math.sin(t*(330+120*t)*TAU)*0.30*(1-t/0.65)**1.5
                                  + math.sin(t*(495+180*t)*TAU)*0.20*(1-t/0.65)**1.5),
        "empty":   (0.05, lambda t: ne(t,0.05,14)*0.25),
        "switch":  (0.09, lambda t: math.sin(t*(900-600*t)*TAU)*0.3*(1-t/0.09)**3),
        "achieve": (0.55, lambda t: math.sin(t*880*TAU)*0.22*math.exp(-t*2)
                                  + math.sin(t*1108*TAU)*0.18*math.exp(-t*1.5)
                                  + math.sin(t*1320*TAU)*0.14*math.exp(-t*1.2)),
        "boss":    (0.90, lambda t: math.sin(t*80*TAU)*0.4*(1-t/0.9)**1.5
                                  + ne(t,0.9,2)*0.15),
    }
    for name, (dur, fn) in specs.items():
        s = _load_wav(name)
        if s is None:
            try: s = _mk_snd(dur, fn)
            except Exception: s = None
        if s is not None:
            SND[name] = s

def play(name, vol=1.0):
    s = SND.get(name)
    if s is not None and S["volume"] > 0:
        s.set_volume(vol * S["volume"])
        s.play()

# ===========================================================================
#  HELPERS
# ===========================================================================
CUBE_VERTS = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
              (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
CUBE_FACES = [((0,1,2,3),0,1,1.0,-1.0),((4,5,6,7),0,1,1.0,-1.0),
              ((0,3,7,4),2,1,1.0,-1.0),((1,2,6,5),2,1,1.0,-1.0),
              ((0,1,5,4),0,2,1.0,1.0),((3,2,6,7),0,2,1.0,1.0)]

SCREEN_CLAMP = 20000.0

def lerp_color(a, b, t):
    return (int(a[0]+(b[0]-a[0])*t),
            int(a[1]+(b[1]-a[1])*t),
            int(a[2]+(b[2]-a[2])*t))

def ray_aabb(ox, oy, oz, dx, dy, dz, bmin, bmax):
    tmin, tmax = -1e18, 1e18
    for o, d, lo, hi in ((ox,dx,bmin[0],bmax[0]),
                         (oy,dy,bmin[1],bmax[1]),
                         (oz,dz,bmin[2],bmax[2])):
        if abs(d) < 1e-9:
            if o < lo or o > hi: return None
        else:
            t1 = (lo-o)/d; t2 = (hi-o)/d
            if t1 > t2: t1, t2 = t2, t1
            if t1 > tmin: tmin = t1
            if t2 < tmax: tmax = t2
            if tmin > tmax: return None
    if tmax < 0.0: return None
    return tmin if tmin > 0.0 else tmax

def clip_near_poly(corners):
    out = []; n = len(corners)
    for i in range(n):
        a = corners[i]; b = corners[(i+1)%n]
        a_in = a[2] >= NEAR; b_in = b[2] >= NEAR
        if a_in: out.append(a)
        if a_in != b_in:
            denom = (b[2]-a[2])
            if abs(denom) < 1e-9: denom = 1e-9
            t = (NEAR-a[2])/denom
            out.append((a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, NEAR,
                        a[3]+(b[3]-a[3])*t, a[4]+(b[4]-a[4])*t))
    return out

# ===========================================================================
#  WEAPONS / ENEMIES / POWERUPS / ACHIEVEMENTS
# ===========================================================================
WEAPONS = [
    dict(name="PISTOL",  dmg=18.0, rate=0.16, mag=14, reserve=999,
         pellets=1, spread=0.006, reload=1.05, auto=False, snd="pistol",
         kick=0.9, shake=0.10),
    dict(name="RIFLE",   dmg=13.0, rate=0.085, mag=32, reserve=240,
         pellets=1, spread=0.020, reload=1.45, auto=True, snd="rifle",
         kick=0.6, shake=0.08),
    dict(name="SHOTGUN", dmg=11.0, rate=0.78, mag=7, reserve=48,
         pellets=9, spread=0.085, reload=1.9, auto=False, snd="shotgun",
         kick=3.0, shake=0.35),
]

ENEMY_TYPES = {
    "grunt":   dict(hp=46, spd=2.2, dmg=9, sc=1.00, tex="flesh",
                    tint=(1.0,0.72,0.74), ranged=False, score=10, atk=0.9),
    "runner":  dict(hp=28, spd=4.1, dmg=6, sc=0.82, tex="skin",
                    tint=(1.1,1.0,0.7), ranged=False, score=15, atk=0.65),
    "brute":   dict(hp=150, spd=1.45, dmg=24, sc=1.38, tex="armor",
                    tint=(0.9,0.78,1.15), ranged=False, score=35, atk=1.15),
    "spitter": dict(hp=48, spd=1.9, dmg=11, sc=1.00, tex="skin",
                    tint=(0.72,1.1,0.9), ranged=True, score=25, atk=1.5),
}
BOSS_KINDS = ["brute", "spitter"]

POWERUPS = {
    "rapid":  dict(dur=12.0, color=(255,220,80),  label="RAPID FIRE",   snd="powerup"),
    "damage": dict(dur=12.0, color=(255,90,90),   label="DOUBLE DAMAGE",snd="powerup"),
    "shield": dict(dur=15.0, color=(120,200,255), label="SHIELD",       snd="powerup"),
}

ACHIEVEMENTS = [
    ("first_blood","FIRST BLOOD","First kill"),("wave_5","SURVIVOR","Reach wave 5"),
    ("wave_10","VETERAN","Reach wave 10"),("wave_20","LEGEND","Reach wave 20"),
    ("kill_100","CENTURION","100 kills"),("kill_500","EXTERMINATOR","500 kills"),
    ("combo_10","RAMPAGE","10x combo"),("combo_20","UNSTOPPABLE","20x combo"),
    ("boss_kill","GIANT SLAYER","Kill a boss"),
    ("score_5k","HIGH ROLLER","5000 score"),("score_15k","BIG SPENDER","15000 score"),
    ("no_hit_wave","UNTOUCHABLE","Clear a wave unhurt"),
]

# ===========================================================================
#  GAME
# ===========================================================================
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.font_s  = _make_font(20)
        self.font_m  = _make_font(28)
        self.font_l  = _make_font(72)
        self.font_xl = _make_font(34)
        self.font_t  = _make_font(100)
        self.font_xs = _make_font(16)

        # adaptive resolution
        self.render_scale = 1.0
        self._scale_cooldown = 0
        self._rw, self._rh = WIDTH, HEIGHT
        self.render_surf = None
        self.shadow_overlay = None
        self.hit_overlay = None
        self._sky_scaled = None
        self._grade_scaled = None
        self._dirt_scaled = None
        self._scale_dirty = True

        # LOD table
        self._lod_table = [0.0] * 256
        for i in range(256):
            self._lod_table[i] = math.log2(i / 40.0) if i > 40 else 0.0

        # shadow sprite
        self.shadow_sprite = pygame.Surface((128, 128), pygame.SRCALPHA)
        for r in range(62, 0, -2):
            a = int(110 * (1 - r / 64) ** 1.4)
            if a > 0:
                pygame.draw.circle(self.shadow_sprite, (0, 0, 0, a), (64, 64), r)

        # Shadow sprite cache: quantise radius so we never call
        # pygame.transform.scale per-entity per-frame.
        self._shadow_cache = {}
        self._shadow_cache_max = 96
        self._shadow_cache_step = 4

        # muzzle flash sprite
        self.muzzle_sprite = pygame.Surface((140, 140), pygame.SRCALPHA)
        for rr, col, a in ((132, (255, 130, 40), 90),
                           (95,  (255, 190, 90), 170),
                           (58,  (255, 240, 210), 230),
                           (30,  (255, 255, 255), 255)):
            pygame.draw.circle(self.muzzle_sprite, (*col, a), (70, 70), rr)

        self.stars_rng = random.Random(2024)
        self.stars = [(self.stars_rng.uniform(0,TAU), self.stars_rng.uniform(0.03,1.45),
                       self.stars_rng.uniform(0.25,1.0), self.stars_rng.uniform(0.7,2.0))
                      for _ in range(150)]

        # full-res overlays
        self.dmg_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._rebuild_dmg()
        self.flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.flash_surf.fill((150, 255, 235, 255))
        self.crosshair_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.scan_surf = self._make_scanlines()
        self.vignette_surf = self._make_vignette()

        self.chroma_buf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self.lens_dirt = None
        p = os.path.join(ASSETS, "ui", "lens_dirt.png")
        if os.path.exists(p):
            try: self.lens_dirt = pygame.image.load(p).convert_alpha()
            except Exception: pass

        self.state = "menu"; self.menu_page = "main"; self.menu_index = 0
        self.keys = set(); self.mouse_grabbed = False
        self.mouse_down = False; self.running = True
        self._frame_avg = 16.0
        self.camx = self.camy = self.camz = 0.0
        self.cyaw, self.syaw = 1.0, 0.0
        self.cpitch, self.spitch = 1.0, 0.0
        self.pitch = 0.0; self.t = 0.0
        self.hurt_dir = (0.0, 0.0); self.hurt_dir_t = 0.0
        self._render = []; self.slowmo = 0.0
        self.focal = HALF_W / math.tan(math.radians(S["fov"])*0.5)

        self._alloc_surfaces()
        self.apply_theme()
        self.new_run()
        self.state = "menu"

    # ------------------------------------------------------------------
    def _alloc_surfaces(self):
        self.render_surf    = pygame.Surface((self._rw, self._rh))
        self.shadow_overlay = pygame.Surface((self._rw, self._rh), pygame.SRCALPHA)
        self.hit_overlay    = pygame.Surface((self._rw, self._rh), pygame.SRCALPHA)
        self._sky_scaled   = None
        self._grade_scaled = None
        self._dirt_scaled  = None

    # ------------------------------------------------------------------
    #  DISPLAY / FULLSCREEN
    # ------------------------------------------------------------------
    def _apply_display_mode(self):
        """Recreate the display surface with current fullscreen setting."""
        was_grabbed = self.mouse_grabbed
        fullscreen = bool(S.get("fullscreen", False))
        try:
            flags = _SCALED | pygame.RESIZABLE
            if fullscreen:
                flags |= pygame.FULLSCREEN
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        except pygame.error:
            try:
                self.screen = pygame.display.set_mode(
                    (WIDTH, HEIGHT),
                    pygame.FULLSCREEN if fullscreen else 0)
            except pygame.error:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("%s %s  ·  adaptive software FPS" % (GAME_NAME, VERSION))
        self.mouse_grabbed = was_grabbed
        self.apply_grab()

    def toggle_fullscreen(self):
        S["fullscreen"] = not bool(S.get("fullscreen", False))
        self._apply_display_mode()
        save_settings()
        play("switch", 0.35)

    # ------------------------------------------------------------------
    def apply_theme(self):
        t = THEMES[THEME_NAMES[S["theme"]]]
        self.sky_top = t["sky_top"]; self.sky_mid = t["sky_mid"]
        self.fog = t["fog"]; self.dark = t["dark"]
        self.fog_r, self.fog_g, self.fog_b = t["fog"]
        self.ambient = t["ambient"]
        lx, ly, lz = t["light_dir"]
        n = math.sqrt(lx*lx + ly*ly + lz*lz)
        self.LX, self.LY, self.LZ = lx/n, ly/n, lz/n
        self.grade_col = t["grade"]

        self.sky_grad = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            u = y/(HEIGHT-1)
            c = lerp_color(self.sky_top, self.sky_mid, u/0.55) if u < 0.55 \
                else lerp_color(self.sky_mid, self.fog, (u-0.55)/0.45)
            pygame.draw.line(self.sky_grad, c, (0,y), (WIDTH,y))

        self.grade_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.grade_surf.fill((*self.grade_col, 18))

        self._sky_scaled   = None
        self._grade_scaled = None

        self.accent = HUD_COLORS[S["hud_color"]][1]
        build_textures(S["theme"])

    def _rebuild_dmg(self):
        self.dmg_surf.fill((0,0,0,0))
        edge = 110
        for i in range(edge):
            a = int(120*(1.0-i/edge)**1.6)
            if a <= 0: continue
            pygame.draw.line(self.dmg_surf,(190,20,34,a),(0,i),(WIDTH,i))
            pygame.draw.line(self.dmg_surf,(190,20,34,a),(0,HEIGHT-1-i),(WIDTH,HEIGHT-1-i))
            pygame.draw.line(self.dmg_surf,(190,20,34,a),(i,0),(i,HEIGHT))
            pygame.draw.line(self.dmg_surf,(190,20,34,a),(WIDTH-1-i,0),(WIDTH-1-i,HEIGHT))

    @staticmethod
    def _make_scanlines():
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(0, HEIGHT, 3):
            pygame.draw.line(s, (0,0,0,18), (0,y),(WIDTH,y))
        return s

    @staticmethod
    def _make_vignette():
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        edge = 110
        for i in range(edge):
            a = int(120*(1.0-i/edge)**2.0)
            if a <= 0: continue
            pygame.draw.line(s,(0,0,0,a),(0,i),(WIDTH,i))
            pygame.draw.line(s,(0,0,0,a),(0,HEIGHT-1-i),(WIDTH,HEIGHT-1-i))
            pygame.draw.line(s,(0,0,0,a),(i,0),(i,HEIGHT))
            pygame.draw.line(s,(0,0,0,a),(WIDTH-1-i,0),(WIDTH-1-i,HEIGHT))
        return s

    def _get_shadow(self, r):
        """Return a cached scaled shadow sprite for pixel radius r."""
        if r < 2: r = 2
        if r > self._shadow_cache_max: r = self._shadow_cache_max
        r = (r // self._shadow_cache_step) * self._shadow_cache_step
        if r < 2: r = 2
        s = self._shadow_cache.get(r)
        if s is None:
            s = pygame.transform.scale(self.shadow_sprite, (r * 2, r * 2))
            self._shadow_cache[r] = s
        return s

    # ------------------------------------------------------------------
    def new_run(self):
        d = DIFFICULTIES[S["difficulty"]]
        self.diff_hp, self.diff_spd, self.diff_take, self.diff_score = d[1],d[2],d[3],d[4]
        self.mode = S["mode"]
        self.px, self.pz = 0.0, 6.0
        self.py = 0.0; self.vy = 0.0; self.grounded = True
        self.yaw = math.pi; self.pitch = 0.0
        self.health = 100.0; self.max_health = 100.0; self.shield = 0.0
        self.bob_phase = 0.0; self.bob_amt = 0.0
        self.wi = 0
        self.mag = [w["mag"] for w in WEAPONS]
        self.reserve = [w["reserve"] for w in WEAPONS]
        self.reloading = 0.0; self.fire_cd = 0.0; self.gun_kick = 0.0
        self.muzzle_t = 0.0; self.view_offset = 0.0; self.switch_t = 0.0
        self.shake = 0.0; self.damage_vignette = 0.0; self.hitmarker_t = 0.0
        self.pickup_flash = 0.0; self.flash_light = None; self.flash_light_t = 0.0
        self.fov_kick = 0.0; self.hurt_dir = (0.0, 0.0); self.hurt_dir_t = 0.0
        self.powerups_active = {}
        self.wave_damage = 0.0

        rnd = random.Random(9001)
        self.crates = []
        for _ in range(26):
            for _try in range(80):
                x = rnd.uniform(-(ARENA-3), ARENA-3)
                z = rnd.uniform(-(ARENA-3), ARENA-3)
                if math.hypot(x,z) > 6.5: break
            sx = rnd.uniform(0.7,1.5); sz = rnd.uniform(0.7,1.5)
            sy = rnd.uniform(0.7,1.7)
            self.crates.append(dict(x=x,z=z,sx=sx,sy=sy,sz=sz,
                r=max(sx,sz)*1.42+0.35, tex=rnd.choice(("crate","metal","plate")),
                rot=rnd.choice((0.0,0.0,math.pi*0.5))))
        self.pillars = []
        for i in range(14):
            a = (i/14.0)*TAU + 0.14
            r = ARENA - 1.2
            self.pillars.append(dict(x=math.cos(a)*r, z=math.sin(a)*r,
                sx=0.75, sy=4.6+(i%3)*0.9, sz=0.75, rot=a, r=1.05))

        self.enemies = []; self.particles = []; self.projectiles = []
        self.pickups = []; self.decals = []; self.toasts = []
        self.wave = 0; self.wave_transition = 2.2
        self.kills = 0; self.score = 0; self.combo = 0; self.combo_t = 0.0
        self.best_combo = 0
        self.toast = ""; self.toast_t = 0.0
        self.kill_feed = []
        self.time_elapsed = 0.0; self.time_target = 40
        self.session_kills = 0

        # reset perf state
        self._frame_avg = 16.0
        self.render_scale = 1.0
        self._scale_cooldown = 0
        new_rw = max(320, int(WIDTH  * self.render_scale))
        new_rh = max(200, int(HEIGHT * self.render_scale))
        if (new_rw, new_rh) != (self._rw, self._rh):
            self._rw, self._rh = new_rw, new_rh
            self._alloc_surfaces()
        self.state = "play"

    def set_toast(self, msg, dur=1.4): self.toast = msg; self.toast_t = dur
    def add_feed(self, msg, col=(220,235,255)):
        self.kill_feed.append([msg, col, 2.4])
        if len(self.kill_feed) > 5: self.kill_feed.pop(0)
    def push_toast(self, text, color=(255,220,120), dur=2.8):
        self.toasts.append([text, color, dur, dur])

    def unlock_ach(self, key):
        if key in S["achievements"]: return
        S["achievements"].append(key)
        for k, name, desc in ACHIEVEMENTS:
            if k == key:
                self.push_toast("ACHIEVEMENT: " + name, (255,220,120))
                play("achieve", 0.6); break
        save_settings()

    def check_achievements(self):
        ak = S["achievements"]
        if self.kills >= 1 and "first_blood" not in ak: self.unlock_ach("first_blood")
        if self.wave >= 5 and "wave_5" not in ak: self.unlock_ach("wave_5")
        if self.wave >= 10 and "wave_10" not in ak: self.unlock_ach("wave_10")
        if self.wave >= 20 and "wave_20" not in ak: self.unlock_ach("wave_20")
        if self.kills >= 100 and "kill_100" not in ak: self.unlock_ach("kill_100")
        if self.kills >= 500 and "kill_500" not in ak: self.unlock_ach("kill_500")
        if self.best_combo >= 10 and "combo_10" not in ak: self.unlock_ach("combo_10")
        if self.best_combo >= 20 and "combo_20" not in ak: self.unlock_ach("combo_20")
        if self.score >= 5000 and "score_5k" not in ak: self.unlock_ach("score_5k")
        if self.score >= 15000 and "score_15k" not in ak: self.unlock_ach("score_15k")

    # ------------------------------------------------------------------
    #  INPUT
    # ------------------------------------------------------------------
    def apply_grab(self):
        pygame.mouse.set_visible(not self.mouse_grabbed)
        pygame.event.set_grab(self.mouse_grabbed)
        if self.mouse_grabbed: pygame.mouse.get_rel()

    def toggle_grab(self): self.mouse_grabbed = not self.mouse_grabbed; self.apply_grab()
    def release_mouse(self): self.mouse_grabbed = False; self.apply_grab()
    def grab_mouse(self): self.mouse_grabbed = True; self.apply_grab()

    def handle_event(self, e):
        if e.type == pygame.QUIT: self.running = False; return

        if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
            self.toggle_fullscreen()
            return

        if self.state == "menu": self._menu_event(e); return
        if self.state == "pause":
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: self.resume()
                elif e.key == pygame.K_q:
                    self.state = "menu"; self.menu_page = "main"; self.release_mouse()
            return
        if e.type == pygame.KEYDOWN:
            self.keys.add(e.key)
            if e.key == pygame.K_ESCAPE: self.pause()
            elif e.key == pygame.K_f: self.toggle_grab()
            elif e.key == pygame.K_r and self.state == "play": self.start_reload()
            elif e.key == pygame.K_q and self.state == "play": self.switch_weapon(-1)
            elif e.key == pygame.K_e and self.state == "play": self.switch_weapon(1)
            elif e.key in (pygame.K_1,pygame.K_2,pygame.K_3) and self.state == "play":
                idx = e.key - pygame.K_1
                if idx != self.wi:
                    self.wi = idx; self.reloading = 0.0
                    self.switch_t = 0.28; play("switch", 0.5)
            elif e.key == pygame.K_SPACE and self.state == "dead":
                self.state = "menu"; self.menu_page = "main"
                self.menu_index = 0; self.release_mouse()
        elif e.type == pygame.KEYUP: self.keys.discard(e.key)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                if not self.mouse_grabbed:
                    self.toggle_grab()
                else:
                    self.mouse_down = True
                    if self.state == "play":
                        self.fire()
            elif e.button == 3 and self.state == "play": self.start_reload()
        elif e.type == pygame.MOUSEBUTTONUP:
            if e.button == 1: self.mouse_down = False
        elif e.type == pygame.MOUSEMOTION:
            if self.mouse_grabbed and self.state == "play":
                dx, dy = e.rel
                s = 0.0022 * S["sensitivity"]
                self.yaw += dx * s
                my = -1 if S["invert_y"] else 1
                self.pitch -= dy * s * my
                self.pitch = max(-1.30, min(1.30, self.pitch))

    # ------------------------------------------------------------------
    #  MENU
    # ------------------------------------------------------------------
    def _main_items(self):
        return [("PLAY","action"),("THEME","subtheme"),("CUSTOMIZE","subcustom"),
                ("SETTINGS","subsettings"),("ACHIEVEMENTS","subach"),("QUIT","action")]
    def _custom_items(self):
        return [("CROSSHAIR STYLE","choice_cross_style"),
                ("CROSSHAIR COLOR","choice_cross_color"),
                ("CROSSHAIR SIZE","slider_cross_size"),
                ("CROSSHAIR GAP","slider_cross_gap"),
                ("CROSSHAIR THICK","slider_cross_thick"),
                ("HUD ACCENT","choice_hud_color"),
                ("BACK","back")]
    def _settings_items(self):
        return [("DIFFICULTY","choice_difficulty"),("GAME MODE","choice_mode"),
                ("FIELD OF VIEW","slider_fov"),("SENSITIVITY","slider_sensitivity"),
                ("VOLUME","slider_volume"),("INVERT Y","toggle_invert_y"),
                ("FULLSCREEN (F11)","toggle_fullscreen"),
                ("ADAPTIVE RES","toggle_adaptive"),
                ("BLOOM","toggle_bloom"),("SCANLINES","toggle_scanlines"),
                ("VIGNETTE","toggle_vignette"),("FOG","toggle_fog"),
                ("BLOB SHADOWS","toggle_shadows"),
                ("DAMAGE PULSE","toggle_damage_pulse"),
                ("RESET SAVE","reset_save"),("BACK","back")]
    def _theme_items(self):
        items = [("THEME " + n, "theme_" + n) for n in THEME_NAMES]
        items.append(("BACK","back")); return items
    def _ach_items(self):
        return [("BACK","back")]

    def _current_items(self):
        return {"main":self._main_items,"custom":self._custom_items,
                "settings":self._settings_items,"theme":self._theme_items,
                "ach":self._ach_items}.get(self.menu_page, self._main_items)()

    def _menu_event(self, e):
        items = self._current_items()
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index-1) % len(items); play("switch",0.2)
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index+1) % len(items); play("switch",0.2)
            elif e.key in (pygame.K_LEFT, pygame.K_a): self._adjust(-1)
            elif e.key in (pygame.K_RIGHT, pygame.K_d): self._adjust(1)
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE): self._activate()
            elif e.key == pygame.K_ESCAPE:
                if self.menu_page == "main": self.running = False
                else: self._back()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self._activate()

    def _back(self): self.menu_page = "main"; self.menu_index = 0

    def _adjust(self, d):
        _, kind = self._current_items()[self.menu_index]
        if kind == "choice_difficulty":
            S["difficulty"] = (S["difficulty"]+d) % len(DIFFICULTIES); play("switch",0.25)
        elif kind == "choice_mode":
            S["mode"] = (S["mode"]+d) % len(MODES); play("switch",0.25)
        elif kind == "slider_fov":
            S["fov"] = max(60, min(100, S["fov"]+d*2)); play("switch",0.15)
        elif kind == "slider_sensitivity":
            S["sensitivity"] = round(max(0.20, min(3.0, S["sensitivity"]+d*0.1)),2); play("switch",0.15)
        elif kind == "slider_volume":
            S["volume"] = round(max(0.0, min(1.0, S["volume"]+d*0.1)),2); play("switch",0.15)
        elif kind == "choice_cross_style":
            S["cross_style"] = (S["cross_style"]+d) % len(CROSSHAIR_STYLES); play("switch",0.25)
        elif kind == "choice_cross_color":
            S["cross_color"] = (S["cross_color"]+d) % len(CROSSHAIR_COLORS); play("switch",0.25)
        elif kind == "slider_cross_size":
            S["cross_size"] = round(max(0.4, min(2.0, S["cross_size"]+d*0.1)),2); play("switch",0.15)
        elif kind == "slider_cross_gap":
            S["cross_gap"] = round(max(0.4, min(2.5, S["cross_gap"]+d*0.1)),2); play("switch",0.15)
        elif kind == "slider_cross_thick":
            S["cross_thick"] = max(1, min(4, S["cross_thick"]+d)); play("switch",0.15)
        elif kind == "choice_hud_color":
            S["hud_color"] = (S["hud_color"]+d) % len(HUD_COLORS); play("switch",0.25)
            self.apply_theme()

    def _activate(self):
        _, kind = self._current_items()[self.menu_index]
        if kind == "action":
            label = self._current_items()[self.menu_index][0]
            if label == "PLAY":
                self.new_run(); self.grab_mouse(); play("wave",0.6)
            elif label == "QUIT":
                save_settings(); self.running = False
        elif kind == "subtheme": self.menu_page = "theme"; self.menu_index = 0
        elif kind == "subcustom": self.menu_page = "custom"; self.menu_index = 0
        elif kind == "subsettings": self.menu_page = "settings"; self.menu_index = 0
        elif kind == "subach": self.menu_page = "ach"; self.menu_index = 0
        elif kind == "back": self._back()
        elif kind.startswith("theme_"):
            S["theme"] = THEME_NAMES.index(kind[6:])
            self.apply_theme(); save_settings(); play("pickup",0.5)
        elif kind == "toggle_fullscreen":
            self.toggle_fullscreen()
        elif kind.startswith("toggle_"):
            S[kind[7:]] = not S[kind[7:]]
            play("switch",0.25); save_settings()
        elif kind == "reset_save":
            for k, v in DEFAULT_SETTINGS.items():
                S[k] = v if not isinstance(v, list) else list(v)
            self.apply_theme(); save_settings(); play("empty",0.6)

    def pause(self): self.state = "pause"; self.release_mouse()
    def resume(self): self.state = "play"; self.grab_mouse()

    # ------------------------------------------------------------------
    def switch_weapon(self, d):
        self.wi = (self.wi+d) % len(WEAPONS)
        self.reloading = 0.0; self.switch_t = 0.28; play("switch",0.5)

    def start_reload(self):
        if self.reloading > 0.0: return
        w = WEAPONS[self.wi]
        if self.mag[self.wi] >= w["mag"]: return
        if self.reserve[self.wi] <= 0 and w["reserve"] < 900: return
        self.reloading = w["reload"]; play("reload",0.5)

    def finish_reload(self):
        w = WEAPONS[self.wi]
        need = w["mag"] - self.mag[self.wi]
        if w["reserve"] >= 900: self.mag[self.wi] = w["mag"]
        else:
            take = min(need, self.reserve[self.wi])
            self.mag[self.wi] += take
            self.reserve[self.wi] -= take

    def fire(self):
        if self.state != "play": return
        w = WEAPONS[self.wi]
        if self.reloading > 0 or self.fire_cd > 0 or self.switch_t > 0: return
        if self.mag[self.wi] <= 0:
            play("empty",0.5); self.start_reload(); return
        rate = w["rate"] * (0.5 if "rapid" in self.powerups_active else 1.0)
        self.fire_cd = rate
        self.mag[self.wi] -= 1
        self.gun_kick = min(2.2, self.gun_kick + w["kick"]*0.55)
        self.muzzle_t = 0.075
        self.view_offset += 0.018 * w["kick"]
        self.shake = max(self.shake, w["shake"])
        self.fov_kick = min(3.5, self.fov_kick + w["kick"]*0.8)
        play(w["snd"], 0.75)

        eff = self.pitch + self.view_offset
        cp, sp = math.cos(eff), math.sin(eff)
        sy, cy = math.sin(self.yaw), math.cos(self.yaw)
        ox = self.px; oz = self.pz
        oy = EYE_HEIGHT + self.py + math.sin(self.bob_phase)*0.05*self.bob_amt
        dmg_mul = 2.0 if "damage" in self.powerups_active else 1.0
        for _ in range(w["pellets"]):
            jx = random.gauss(0.0, w["spread"])
            jy = random.gauss(0.0, w["spread"])
            ddx = cp*sy + jx*cy; ddy = sp + jy; ddz = cp*cy - jx*sy
            n = math.sqrt(ddx*ddx + ddy*ddy + ddz*ddz)
            self.trace_shot(ox, oy, oz, ddx/n, ddy/n, ddz/n, w["dmg"]*dmg_mul)
        self.flash_light = (ox+sy*1.2, oy-0.15, oz+cy*1.2, 9.0, 1.35)
        self.flash_light_t = 0.09
        if self.mag[self.wi] == 0: self.start_reload()

    def trace_shot(self, ox, oy, oz, dx, dy, dz, dmg):
        hit = self.raycast(ox, oy, oz, dx, dy, dz, 220.0)
        if hit is None: return
        t, enemy, hx, hy, hz = hit
        if enemy is not None:
            head = hy > 1.62*enemy["spec"]["sc"]
            d = dmg * (2.2 if head else 1.0)
            enemy["hp"] -= d; enemy["flash"] = 1.0; enemy["hurt_t"] = 0.22
            self.hitmarker_t = 0.16
            self.spawn_particles(hx, hy, hz, (250,60,60), 6, 2.8)
            if head: self.spawn_particles(hx, hy, hz, (255,220,90), 4, 3.2)
            play("hit",0.30)
            if enemy["hp"] <= 0.0: self.kill_enemy(enemy)
        else:
            self.spawn_particles(hx, hy, hz, (200,200,210), 5, 2.0)
            self.spawn_particles(hx, hy, hz, (255,190,90), 3, 3.4)

    def kill_enemy(self, e):
        if e not in self.enemies: return
        self.enemies.remove(e)
        self.kills += 1; self.session_kills += 1
        self.combo += 1; self.combo_t = 2.6
        self.best_combo = max(self.best_combo, self.combo)
        spec = e["spec"]; is_boss = e.get("is_boss", False)
        gain = int(spec["score"] * (1.0 + self.combo*0.05) * self.diff_score)
        if is_boss: gain *= 6
        self.score += gain
        pc = 80 if is_boss else 24
        self.spawn_particles(e["x"],1.1,e["z"],(255,70,70),pc,5.5)
        self.spawn_particles(e["x"],1.1,e["z"],(170,24,40),pc*2//3,3.2)
        self.spawn_particles(e["x"],1.1,e["z"],(255,210,130),8,6.5)
        self.decals.append([e["x"],0.02,e["z"],
                            random.uniform(1.6,2.6)*(2 if is_boss else 1),22.0])
        play("kill",0.45)
        self.add_feed("+%d  %s%s" % (gain, "BOSS " if is_boss else "", e["kind"].upper()),
                      (255,180,90) if is_boss else ((255,200,120) if self.combo>2 else (200,230,255)))
        if is_boss:
            self.unlock_ach("boss_kill")
            self.push_toast("BOSS DOWN!  +%d" % gain, (255,180,90))
            self.pickups.append({"x":e["x"],"z":e["z"],"y":0.6,
                "kind":random.choice(list(POWERUPS.keys())),"phase":0.0,"life":40.0})
        else:
            r = random.random()
            if r < 0.10:
                self.pickups.append({"x":e["x"],"z":e["z"],"y":0.6,
                    "kind":random.choice(list(POWERUPS.keys())),"phase":0.0,"life":30.0})
            elif r < 0.32:
                self.pickups.append({"x":e["x"],"z":e["z"],"y":0.6,
                    "kind":random.choice(("ammo","health")),"phase":0.0,"life":26.0})
        if self.combo > 0 and self.combo % 5 == 0:
            self.set_toast("%d KILL STREAK!" % self.combo, 1.4)
        self.check_achievements()

    def raycast(self, ox, oy, oz, dx, dy, dz, max_dist):
        best = None
        for e in self.enemies:
            sc = e["spec"]["sc"]
            hw = 0.42*sc; hh = 1.95*sc
            bmin = (e["x"]-hw, 0.0, e["z"]-hw)
            bmax = (e["x"]+hw, hh,  e["z"]+hw)
            t = ray_aabb(ox,oy,oz,dx,dy,dz,bmin,bmax)
            if t is not None and 0.0 < t < max_dist:
                if best is None or t < best[0]:
                    best = (t, e, ox+dx*t, oy+dy*t, oz+dz*t)
        for c in self.crates:
            bmin = (c["x"]-c["sx"],0.0,c["z"]-c["sz"])
            bmax = (c["x"]+c["sx"],2.0*c["sy"],c["z"]+c["sz"])
            t = ray_aabb(ox,oy,oz,dx,dy,dz,bmin,bmax)
            if t is not None and 0.0 < t < max_dist:
                if best is None or t < best[0]:
                    best = (t, None, ox+dx*t, oy+dy*t, oz+dz*t)
        for p in self.pillars:
            bmin = (p["x"]-p["sx"],0.0,p["z"]-p["sz"])
            bmax = (p["x"]+p["sx"],2.0*p["sy"],p["z"]+p["sz"])
            t = ray_aabb(ox,oy,oz,dx,dy,dz,bmin,bmax)
            if t is not None and 0.0 < t < max_dist:
                if best is None or t < best[0]:
                    best = (t, None, ox+dx*t, oy+dy*t, oz+dz*t)
        return best

    def damage_player(self, amount, from_x=None, from_z=None):
        if self.shield > 0:
            absorbed = min(self.shield, amount)
            self.shield -= absorbed; amount -= absorbed
        self.health -= amount * self.diff_take
        self.wave_damage += amount * self.diff_take
        self.damage_vignette = min(1.0, self.damage_vignette + 0.55)
        self.shake = max(self.shake, 0.34); self.combo = 0
        play("hurt",0.4)
        if from_x is not None:
            self.hurt_dir = (from_x, from_z); self.hurt_dir_t = 0.8
        if self.health <= 0.0:
            self.health = 0.0
            self.state = "dead"; self.slowmo = 1.2
            self.release_mouse()
            if self.mode == 0:
                S["best_survival"] = max(S["best_survival"], max(0,self.wave-1))
            elif self.mode == 1:
                S["best_endless"] = max(S["best_endless"], max(0,self.wave-1))
            S["best_kills"] = max(S["best_kills"], self.kills)
            S["best_score"] = max(S["best_score"], self.score)
            save_settings()

    def spawn_particles(self, x, y, z, color, count, speed, gravity=True):
        for _ in range(count):
            a = random.uniform(0, TAU); p = random.uniform(0.3,1.0)
            s = random.uniform(0.4,1.0) * speed
            self.particles.append({"x":x,"y":y,"z":z,
                "vx":math.cos(a)*s*p, "vy":random.uniform(1.2,3.6),
                "vz":math.sin(a)*s*p,
                "life":random.uniform(0.35,0.9),"max":0.9,
                "color":color,"size":random.uniform(0.045,0.095),"grav":gravity})
        if len(self.particles) > 320:
            del self.particles[:len(self.particles)-320]

    # ------------------------------------------------------------------
    #  UPDATE
    # ------------------------------------------------------------------
    def update(self, dt):
        self.t += dt
        if self.state == "menu": self._menu_camera(); return
        if self.state == "pause": return
        if self.slowmo > 0:
            self.slowmo = max(0.0, self.slowmo - dt); dt *= 0.35
        self.time_elapsed += dt

        self.fire_cd = max(0.0, self.fire_cd - dt)
        self.muzzle_t = max(0.0, self.muzzle_t - dt)
        self.gun_kick = max(0.0, self.gun_kick - dt*5.0)
        self.view_offset *= max(0.0, 1.0 - dt*6.5)
        self.switch_t = max(0.0, self.switch_t - dt)
        self.fov_kick *= max(0.0, 1.0 - dt*5.0)
        self.flash_light_t = max(0.0, self.flash_light_t - dt)
        if self.flash_light_t <= 0.0: self.flash_light = None
        else:
            fx, fy, fz, rad, inten = self.flash_light
            k = self.flash_light_t/0.09
            self.flash_light = (fx, fy, fz, rad, inten*k)
        if self.reloading > 0.0:
            self.reloading -= dt
            if self.reloading <= 0.0:
                self.reloading = 0.0; self.finish_reload()
        for k in list(self.powerups_active.keys()):
            self.powerups_active[k] -= dt
            if self.powerups_active[k] <= 0: del self.powerups_active[k]
        self.shake = max(0.0, self.shake - dt*2.4)
        self.damage_vignette = max(0.0, self.damage_vignette - dt*0.85)
        self.hitmarker_t = max(0.0, self.hitmarker_t - dt)
        self.pickup_flash = max(0.0, self.pickup_flash - dt*3.0)
        self.toast_t = max(0.0, self.toast_t - dt)
        self.combo_t = max(0.0, self.combo_t - dt)
        self.hurt_dir_t = max(0.0, self.hurt_dir_t - dt)
        if self.combo_t <= 0.0: self.combo = 0
        for f in self.kill_feed: f[2] -= dt
        self.kill_feed = [f for f in self.kill_feed if f[2] > 0.0]
        for tt in self.toasts: tt[2] -= dt
        self.toasts = [tt for tt in self.toasts if tt[2] > 0.0]
        if self.state != "play":
            self.update_particles(dt); self.update_pickups(dt); return
        if self.mouse_down and WEAPONS[self.wi]["auto"]: self.fire()

        if self.mode == 2:
            if self.session_kills >= self.time_target:
                if S["time_attack_best"] == 0 or self.time_elapsed < S["time_attack_best"]:
                    S["time_attack_best"] = self.time_elapsed; save_settings()
                self.state = "dead"; self.release_mouse()
            elif not self.enemies:
                for _ in range(3):
                    self.spawn_enemy(random.choice(["grunt","runner","spitter"]))
        else:
            if not self.enemies and self.wave_transition <= 0.0:
                self.wave_transition = 2.8 if self.mode == 0 else 1.2
                heal = 22.0 + self.wave*2.0
                self.health = min(self.max_health, self.health + heal)
                for i in range(len(WEAPONS)):
                    self.reserve[i] += WEAPONS[i]["mag"]*2
                self.score += 50 * self.wave
                if self.wave_damage <= 0 and self.wave > 0:
                    self.unlock_ach("no_hit_wave")
                self.wave_damage = 0.0
                self.set_toast("WAVE %d CLEARED  +%d HP" % (self.wave, int(heal)), 2.2)
                play("pickup",0.6)
            if self.wave_transition > 0.0:
                self.wave_transition -= dt
                if self.wave_transition <= 0.0 and not self.enemies:
                    self.start_wave()

        self.update_player(dt); self.update_enemies(dt)
        self.update_projectiles(dt); self.update_particles(dt); self.update_pickups(dt)
        for d in self.decals: d[4] -= dt*1.2
        self.decals = [d for d in self.decals if d[4] > 0.0]

    def _menu_camera(self):
        a = self.t * 0.11; r = 30.0
        self.camx = math.cos(a)*r; self.camz = math.sin(a)*r
        self.camy = 9.5 + math.sin(self.t*0.21)*2.6
        dx = 0.0 - self.camx; dy = 2.0 - self.camy; dz = 0.0 - self.camz
        dh = math.sqrt(dx*dx + dz*dz)
        yaw = math.atan2(dx, dz); pitch = math.atan2(dy, dh)
        self.cyaw = math.cos(yaw); self.syaw = math.sin(yaw)
        self.cpitch = math.cos(pitch); self.spitch = math.sin(pitch)
        self.pitch = pitch

    def start_wave(self):
        self.wave += 1
        for i in range(len(WEAPONS)):
            self.reserve[i] = max(self.reserve[i], WEAPONS[i]["mag"]*2)
        self.mag[self.wi] = WEAPONS[self.wi]["mag"]; self.reloading = 0.0
        is_boss_wave = (self.mode == 0 and self.wave % 5 == 0)
        if is_boss_wave:
            self.spawn_boss()
            for _ in range(2 + self.wave//3): self.spawn_enemy("runner")
            play("boss",0.7); self.set_toast("BOSS  WAVE  %d" % self.wave, 3.0)
        else:
            n = 3 + int(self.wave*1.5)
            if self.mode == 1: n += 2
            pool = ["grunt"]
            if self.wave >= 2: pool.append("runner")
            if self.wave >= 3: pool += ["runner","spitter"]
            if self.wave >= 4: pool += ["brute","spitter","runner"]
            for _ in range(n): self.spawn_enemy(random.choice(pool))
            self.set_toast("WAVE %d" % self.wave, 2.4); play("wave",0.7)

    def spawn_enemy(self, kind, boss=False):
        spec = ENEMY_TYPES[kind]
        x = z = 0.0
        for _ in range(120):
            a = random.uniform(0, TAU)
            r = random.uniform(ARENA*0.5, ARENA-2.0)
            x = math.cos(a)*r; z = math.sin(a)*r
            if math.hypot(x-self.px, z-self.pz) > 15.0: break
        hp = spec["hp"] * self.diff_hp * (1.0 + self.wave*0.055)
        if boss: hp *= 8.0
        self.enemies.append({"kind":kind,"spec":spec,"x":x,"z":z,
            "hp":hp,"max_hp":hp,"phase":random.uniform(0,TAU),
            "attack_cd":random.uniform(0.3,1.2),"flash":0.0,
            "speed":spec["spd"]*self.diff_spd*(1.0 + self.wave*0.018),
            "yaw":0.0,"hurt_t":0.0,"is_boss":boss,
            "slam_cd":random.uniform(3.0,6.0) if boss else 0.0})
        return self.enemies[-1]

    def spawn_boss(self):
        kind = random.choice(BOSS_KINDS)
        b = self.spawn_enemy(kind, boss=True)
        b["spec"] = dict(b["spec"])
        b["spec"]["sc"] *= 3.0
        b["spec"]["dmg"] *= 2
        b["spec"]["atk"] = 1.6
        b["spec"]["score"] *= 4
        self.add_feed("A BOSS APPEARS", (255,180,90))
        return b

    def update_player(self, dt):
        keys = self.keys
        turn = (pygame.K_RIGHT in keys) - (pygame.K_LEFT in keys)
        look = (pygame.K_UP in keys) - (pygame.K_DOWN in keys)
        if turn or look:
            self.yaw += turn*2.2*dt
            self.pitch += look*1.5*dt*(-1 if S["invert_y"] else 1)
            self.pitch = max(-1.30, min(1.30, self.pitch))
        fwd = (pygame.K_w in keys) - (pygame.K_s in keys)
        strafe = (pygame.K_d in keys) - (pygame.K_a in keys)
        sprint = (pygame.K_LSHIFT in keys) or (pygame.K_RSHIFT in keys)
        speed = 8.6 * (1.65 if sprint else 1.0)
        n = math.hypot(fwd, strafe)
        if n > 0.0: fwd /= n; strafe /= n
        sy, cy = math.sin(self.yaw), math.cos(self.yaw)
        self.px += (sy*fwd + cy*strafe) * speed * dt
        self.pz += (cy*fwd - sy*strafe) * speed * dt
        if n > 0.0:
            self.bob_phase += dt * (14.0 if sprint else 10.5)
            self.bob_amt = min(1.0, self.bob_amt + dt*6.0)
        else:
            self.bob_amt = max(0.0, self.bob_amt - dt*6.0)
        if self.grounded and (pygame.K_SPACE in keys):
            self.vy = 6.4; self.grounded = False
        self.vy -= GRAVITY*dt; self.py += self.vy*dt
        if self.py <= 0.0: self.py = 0.0; self.vy = 0.0; self.grounded = True
        lim = ARENA + 8.0
        self.px = max(-lim, min(lim, self.px))
        self.pz = max(-lim, min(lim, self.pz))
        for c in self.crates:
            dx = self.px-c["x"]; dz = self.pz-c["z"]
            d = math.hypot(dx, dz); rr = c["r"]+0.42
            if 1e-6 < d < rr:
                push = rr-d; self.px += dx/d*push; self.pz += dz/d*push
        for p in self.pillars:
            dx = self.px-p["x"]; dz = self.pz-p["z"]
            d = math.hypot(dx, dz); rr = p["r"]+0.42
            if 1e-6 < d < rr:
                push = rr-d; self.px += dx/d*push; self.pz += dz/d*push

    def update_enemies(self, dt):
        for e in self.enemies:
            spec = e["spec"]
            e["phase"] += dt
            e["flash"] = max(0.0, e["flash"]-dt*5.0)
            e["hurt_t"] = max(0.0, e["hurt_t"]-dt)
            e["attack_cd"] = max(0.0, e["attack_cd"]-dt)
            dx = self.px-e["x"]; dz = self.pz-e["z"]
            dist = math.hypot(dx, dz) or 1e-6
            e["yaw"] = math.atan2(dx, dz)
            if spec["ranged"]:
                if dist > 12.0:
                    e["x"] += dx/dist*e["speed"]*dt
                    e["z"] += dz/dist*e["speed"]*dt
                elif dist < 7.0:
                    e["x"] -= dx/dist*e["speed"]*0.7*dt
                    e["z"] -= dz/dist*e["speed"]*0.7*dt
                if e["attack_cd"] <= 0.0 and dist < 22.0:
                    e["attack_cd"] = spec["atk"]*random.uniform(0.8,1.2)
                    self.spawn_projectile(e)
            else:
                if dist > 1.6*e["spec"]["sc"]:
                    e["x"] += dx/dist*e["speed"]*dt
                    e["z"] += dz/dist*e["speed"]*dt
                elif e["attack_cd"] <= 0.0:
                    e["attack_cd"] = spec["atk"]
                    self.damage_player(spec["dmg"], e["x"], e["z"])
                    self.spawn_particles(self.px,1.4,self.pz,(230,40,50),7,2.6)
            if e.get("is_boss"):
                e["slam_cd"] = max(0.0, e["slam_cd"]-dt)
                if e["slam_cd"] <= 0.0 and dist < 6.0:
                    e["slam_cd"] = 4.5
                    self.spawn_particles(e["x"],0.3,e["z"],(255,140,60),30,6.0)
                    for _ in range(3):
                        self.spawn_particles(e["x"],0.3,e["z"],(255,90,90),12,4.0)
                    if math.hypot(self.px-e["x"], self.pz-e["z"]) < 4.5:
                        self.damage_player(18, e["x"], e["z"])
                    self.shake = max(self.shake, 0.6)
            for c in self.crates:
                cdx = e["x"]-c["x"]; cdz = e["z"]-c["z"]
                cd = math.hypot(cdx, cdz); rr = c["r"]+0.5
                if 1e-6 < cd < rr:
                    p = (rr-cd)*0.6
                    e["x"] += cdx/cd*p; e["z"] += cdz/cd*p
        n = len(self.enemies)
        for i in range(n):
            e1 = self.enemies[i]
            for j in range(i+1, n):
                e2 = self.enemies[j]
                dx = e1["x"]-e2["x"]; dz = e1["z"]-e2["z"]
                d = math.hypot(dx, dz)
                md = 1.05 + (0.5 if e1.get("is_boss") or e2.get("is_boss") else 0)
                if 1e-6 < d < md:
                    push = (md-d)*0.5; ux, uz = dx/d, dz/d
                    e1["x"] += ux*push; e1["z"] += uz*push
                    e2["x"] -= ux*push; e2["z"] -= uz*push

    def spawn_projectile(self, e):
        dx = self.px-e["x"]; dz = self.pz-e["z"]
        d = math.hypot(dx, dz) or 1e-6; sp = 15.0
        self.projectiles.append({"x":e["x"],"y":1.25,"z":e["z"],
            "vx":dx/d*sp,"vy":0.6,"vz":dz/d*sp,"life":3.0,"dmg":e["spec"]["dmg"]})
        self.spawn_particles(e["x"],1.25,e["z"],(120,240,180),4,1.6)

    def update_projectiles(self, dt):
        alive = []
        for p in self.projectiles:
            p["life"] -= dt
            if p["life"] <= 0.0: continue
            p["vy"] -= 3.0*dt
            p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt; p["z"] += p["vz"]*dt
            if p["y"] < 0.1: p["y"] = 0.1; p["vy"] = 0.0
            dx = p["x"]-self.px; dy = p["y"]-(1.1+self.py); dz = p["z"]-self.pz
            if dx*dx+dy*dy+dz*dz < 0.7:
                self.damage_player(p["dmg"], p["x"], p["z"])
                self.spawn_particles(p["x"],p["y"],p["z"],(120,255,190),12,3.4)
                continue
            hit = False
            for c in self.crates:
                if (abs(p["x"]-c["x"]) < c["sx"] and 0.0 < p["y"] < 2.0*c["sy"]
                        and abs(p["z"]-c["z"]) < c["sz"]):
                    hit = True; break
            if hit:
                self.spawn_particles(p["x"],p["y"],p["z"],(120,255,190),10,3.0)
                continue
            alive.append(p)
        self.projectiles = alive

    def update_particles(self, dt):
        alive = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] <= 0.0: continue
            if p["grav"]: p["vy"] -= 9.5*dt
            p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt; p["z"] += p["vz"]*dt
            if p["y"] < 0.04:
                p["y"] = 0.04; p["vy"] = -p["vy"]*0.32
                p["vx"] *= 0.55; p["vz"] *= 0.55
            alive.append(p)
        self.particles = alive

    def update_pickups(self, dt):
        alive = []
        for p in self.pickups:
            p["life"] -= dt; p["phase"] += dt
            p["y"] = 0.55 + math.sin(p["phase"]*2.4)*0.14
            if p["life"] <= 0.0: continue
            if math.hypot(p["x"]-self.px, p["z"]-self.pz) < 1.4 and self.state == "play":
                k = p["kind"]
                if k == "health":
                    if self.health >= self.max_health: alive.append(p); continue
                    self.health = min(self.max_health, self.health+28.0)
                    self.set_toast("+28 HP",1.0)
                elif k == "ammo":
                    w = WEAPONS[self.wi]
                    self.reserve[self.wi] += w["mag"]*3
                    self.set_toast("+AMMO",1.0)
                else:
                    pu = POWERUPS[k]
                    self.powerups_active[k] = pu["dur"]
                    self.set_toast(pu["label"]+"  ACTIVATED", 1.6)
                    play(pu["snd"],0.7); self.push_toast(pu["label"], pu["color"])
                self.pickup_flash = 0.5; play("pickup",0.5)
                col = POWERUPS.get(k, {"color":(140,255,220)})["color"]
                self.spawn_particles(p["x"],p["y"],p["z"],col,12,2.4,False)
                continue
            alive.append(p)
        self.pickups = alive

    # ==================================================================
    #  RENDER
    # ==================================================================
    def _update_render_scale(self):
        if not S.get("adaptive", True):
            new_scale = 1.0
        else:
            if self._scale_cooldown > 0:
                self._scale_cooldown -= 1
                return
            new_scale = self.render_scale
            if self._frame_avg > 20.0 and self.render_scale > SCALE_MIN + 0.001:
                new_scale = max(SCALE_MIN, round(self.render_scale - SCALE_STEP, 2))
            elif self._frame_avg < 14.0 and self.render_scale < SCALE_MAX - 0.001:
                new_scale = min(SCALE_MAX, round(self.render_scale + SCALE_STEP, 2))
            else:
                return
        if new_scale == self.render_scale:
            return
        self.render_scale = new_scale
        self._scale_cooldown = SCALE_COOLDOWN
        rw = max(320, int(WIDTH  * self.render_scale))
        rh = max(200, int(HEIGHT * self.render_scale))
        if (rw, rh) != (self._rw, self._rh):
            self._rw, self._rh = rw, rh
            self._alloc_surfaces()

    def _poly_budget(self):
        if not S.get("adaptive", True):
            return POLY_BUDGET_MAX
        if self._frame_avg > 22.0: return POLY_BUDGET_MIN
        if self._frame_avg < 14.0: return POLY_BUDGET_MAX
        return POLY_BUDGET

    def draw(self):
        self._update_render_scale()
        scr = self.render_surf
        self._render.clear()

        if self.state != "menu":
            camx, camz = self.px, self.pz
            camy = EYE_HEIGHT + self.py + math.sin(self.bob_phase)*0.05*self.bob_amt
            if self.shake > 0.0:
                camx += random.uniform(-1,1)*self.shake*0.14
                camy += random.uniform(-1,1)*self.shake*0.14
                camz += random.uniform(-1,1)*self.shake*0.14
            self.camx, self.camy, self.camz = camx, camy, camz
            eff = self.pitch + self.view_offset
            fov = math.radians(S["fov"] + self.fov_kick*0.1)
            self.focal = HALF_W / math.tan(fov*0.5) * self.render_scale
            self.cyaw, self.syaw = math.cos(self.yaw), math.sin(self.yaw)
            self.cpitch, self.spitch = math.cos(eff), math.sin(eff)
        else:
            self.focal = HALF_W / math.tan(math.radians(S["fov"])*0.5) * self.render_scale

        # ----- sky ------------------------------------------------------
        scr.fill(self.fog)
        cp_safe = self.cpitch if abs(self.cpitch) > 1e-6 else \
                  (1e-6 if self.cpitch >= 0 else -1e-6)
        tp = self.spitch / cp_safe
        if tp > 4.0: tp = 4.0
        elif tp < -4.0: tp = -4.0
        horizon = self._rh * 0.5 + self.focal * tp
        y0 = int(horizon - self._rh*0.86)
        if y0 > 0:
            scr.fill(self.sky_top, (0, 0, self._rw, min(y0, self._rh)))
        if self._sky_scaled is None:
            if (self._rw, self._rh) == (WIDTH, HEIGHT):
                self._sky_scaled = self.sky_grad
            else:
                self._sky_scaled = pygame.transform.smoothscale(
                    self.sky_grad, (self._rw, self._rh))
        scr.blit(self._sky_scaled, (0, y0))

        yb = y0 + self._rh
        if yb < self._rh:
            scr.fill(self.fog, (0, max(0, yb), self._rw, self._rh - max(0, yb)))
        self.draw_stars()

        # ----- geometry -------------------------------------------------
        self.queue_ground()
        self.queue_world()
        self.queue_effects()

        # ----- rasterise (KEEP CLOSEST if over budget) ------------------
        self._render.sort(key=lambda r: r[0], reverse=True)
        budget = self._poly_budget()
        total = len(self._render)
        if total > budget:
            draw_list = self._render[total - budget:]
        else:
            draw_list = self._render
        dp = pygame.draw.polygon
        for depth, pts, col, outline in draw_list:
            if len(pts) < 3: continue
            dp(scr, col, pts)
            if outline and depth < 24.0:
                dp(scr, self.dark, pts, 1)

        # ----- soft shadows --------------------------------------------
        if S["shadows"] and self.state != "menu":
            self.draw_blob_shadows(scr)

        # ----- world overlays ------------------------------------------
        if self.state in ("play","pause","dead"):
            self.draw_world_overlays(scr)

        # ----- viewmodel ------------------------------------------------
        if self.state in ("play","pause"):
            self.draw_gun(scr)

        # ----- post -----------------------------------------------------
        if S["bloom"]: self.draw_bloom(scr)
        if self.state != "menu":
            if self._grade_scaled is None:
                if (self._rw, self._rh) == (WIDTH, HEIGHT):
                    self._grade_scaled = self.grade_surf
                else:
                    self._grade_scaled = pygame.transform.smoothscale(
                        self.grade_surf, (self._rw, self._rh))
            scr.blit(self._grade_scaled, (0, 0))
        if S["damage_pulse"] and self.damage_vignette > 0.15:
            self.draw_chromatic(scr)

        # ----- composite to display -------------------------------------
        if (self._rw, self._rh) == (WIDTH, HEIGHT):
            self.screen.blit(scr, (0, 0))
        else:
            self.screen.blit(
                pygame.transform.smoothscale(scr, (WIDTH, HEIGHT)), (0, 0))

        # ----- full-resolution overlays ---------------------------------
        if S["vignette"]: self.screen.blit(self.vignette_surf, (0, 0))
        if S["scanlines"]: self.screen.blit(self.scan_surf, (0, 0))

        if self.state == "play": self.draw_hud()
        elif self.state == "dead": self.draw_dead()
        elif self.state == "pause": self.draw_hud(); self.draw_pause()
        elif self.state == "menu": self.draw_menu()

    def draw_stars(self):
        scr = self.render_surf
        cy, sy = self.cyaw, self.syaw
        cp, sp = self.cpitch, self.spitch
        rw, rh = self._rw, self._rh
        hw, hh = rw * 0.5, rh * 0.5
        for az, el, br, sz in self.stars:
            ce = math.cos(el)
            x = math.sin(az)*ce; y = math.sin(el); z = math.cos(az)*ce
            x1 = x*cy - z*sy; z1 = x*sy + z*cy
            y2 = y*cp - z1*sp; z2 = y*sp + z1*cp
            if z2 <= 0.05: continue
            inv = self.focal/z2
            sx = hw + x1*inv; sy_ = hh - y2*inv
            if -20 < sx < rw+20 and -20 < sy_ < rh+20:
                v = int(150*br)
                if v > 8:
                    scr.fill((v,v,min(255,v+30)),
                             (int(sx),int(sy_),int(sz),int(sz)))

    def queue_ground(self):
        gx0 = int(math.floor((self.camx - GROUND_HALF)/TILE))
        gx1 = int(math.ceil ((self.camx + GROUND_HALF)/TILE))
        gz0 = int(math.floor((self.camz - GROUND_HALF)/TILE))
        gz1 = int(math.ceil ((self.camz + GROUND_HALF)/TILE))
        cull = FOG_END + 8.0; cull2 = cull*cull
        mf = TEX_MIPS["floor"]; mf2 = TEX_MIPS["floor2"]
        ts = 5.0
        for i in range(gx0, gx1):
            for j in range(gz0, gz1):
                x0 = i*TILE; z0 = j*TILE
                mx = x0 + TILE*0.5 - self.camx
                mz = z0 + TILE*0.5 - self.camz
                dist2 = mx*mx + mz*mz
                if dist2 > cull2: continue
                wp = ((x0,0,z0),(x0+TILE,0,z0),
                      (x0+TILE,0,z0+TILE),(x0,0,z0+TILE))
                uv = ((x0/ts,z0/ts),((x0+TILE)/ts,z0/ts),
                      ((x0+TILE)/ts,(z0+TILE)/ts),(x0/ts,(z0+TILE)/ts))
                lit = self.face_light(0.0,1.0,0.0,
                                      x0+TILE*0.5, 0.0, z0+TILE*0.5)
                mips = mf if ((i+j)&1) == 0 else mf2
                if dist2 < SUBDIV_DIST*SUBDIV_DIST:
                    max_n = 3
                elif dist2 < 45.0*45.0:
                    max_n = 1
                else:
                    max_n = 0
                self.add_quad(wp, uv, mips, lit, max_n=max_n, outline=False)

    def queue_world(self):
        for c in self.crates:
            self.add_cube(c["x"],c["sy"],c["z"],c["sx"],c["sy"],c["sz"],
                          TEX_MIPS[c["tex"]], c["rot"], outline=True)
        for p in self.pillars:
            self.add_cube(p["x"],p["sy"],p["z"],p["sx"],p["sy"],p["sz"],
                          TEX_MIPS["pillar"], p["rot"], outline=True)
        for d in self.decals:
            alpha = d[4]/22.0
            if alpha <= 0.0: continue
            wp = ((d[0]-d[3],0.02,d[2]-d[3]),(d[0]+d[3],0.02,d[2]-d[3]),
                  (d[0]+d[3],0.02,d[2]+d[3]),(d[0]-d[3],0.02,d[2]+d[3]))
            col = (int(70*alpha), int(16*alpha), int(22*alpha))
            if col[0] < 3: continue
            self.add_color_quad(wp, col)
        for e in self.enemies:
            self.queue_enemy(e)
        for p in self.pickups:
            if p["kind"] in POWERUPS:
                col = POWERUPS[p["kind"]]["color"]
                self.add_billboard(p["x"],p["y"],p["z"],0.42,col,glow=True)
                self.add_billboard(p["x"],p["y"]+0.25,p["z"],0.20,col)
            else:
                col = (90,240,170) if p["kind"]=="health" else (250,200,90)
                self.add_billboard(p["x"],p["y"],p["z"],0.34,col,glow=True)

    def queue_enemy(self, e):
        spec = e["spec"]; sc = spec["sc"]; yaw = e["yaw"]
        bob = math.sin(e["phase"]*8.0)*0.05
        tint = (1,1,1) if e["hurt_t"] > 0.0 else spec["tint"]
        flash = e["hurt_t"] > 0.0
        tb = TEX_MIPS[spec["tex"]]; ta = TEX_MIPS["armor"]
        def part(ox, oy, oz, sx, sy, sz, tex, tm):
            ca, sa = math.cos(yaw), math.sin(yaw)
            wx = e["x"] + ox*ca + oz*sa
            wz = e["z"] - ox*sa + oz*ca
            wy = oy + bob*sc
            t = (min(1.0, tm[0]*tint[0]),
                 min(1.0, tm[1]*tint[1]),
                 min(1.0, tm[2]*tint[2]))
            if flash:
                t = (min(1.0, t[0]+0.6), min(1.0, t[1]+0.6), min(1.0, t[2]+0.6))
            self.add_cube(wx,wy,wz,sx*sc,sy*sc,sz*sc, tex, yaw, tint=t,
                          outline=False, point=(e["x"],1.2,e["z"]),
                          glow=e.get("is_boss", False))
        part(0.0,0.36,0.0,0.32,0.38,0.26,tb,(1,1,1))
        part(0.0,1.02,0.0,0.40,0.40,0.30,tb,(1,1,1))
        part(0.0,1.48,0.0,0.54,0.11,0.28,ta,(1,1,1))
        part(0.0,1.80,0.0,0.24,0.24,0.24,tb,(1,1,1))
        ey = 1.80 + bob*sc
        ex = e["x"] + math.sin(yaw)*0.26*sc
        ez = e["z"] + math.cos(yaw)*0.26*sc
        self.add_cube(ex,ey,ez,0.07*sc,0.07*sc,0.045*sc, TEX_MIPS["skin"],
                      yaw, tint=(1.0,0.42,0.34), emissive=True,
                      outline=False, glow=True)

    def queue_effects(self):
        camx, camz = self.camx, self.camz
        visible = []
        for p in self.particles:
            dx = p["x"] - camx; dz = p["z"] - camz
            if dx*dx + dz*dz < 900.0:
                visible.append(p)
                if len(visible) >= PARTICLE_CAP: break
        for p in visible:
            t = p["life"]/p["max"]
            size = p["size"]*(0.4+0.6*t)
            self.add_billboard(p["x"],p["y"],p["z"],size,p["color"])
        for pr in self.projectiles:
            self.add_billboard(pr["x"],pr["y"],pr["z"],0.18,(140,255,200),glow=True)

    # ------------------------------------------------------------------
    def draw_blob_shadows(self, scr):
        surf = self.shadow_overlay
        surf.fill((0, 0, 0, 0))
        dirty = False
        get = self._get_shadow
        blit = surf.blit
        focal = self.focal
        for e in self.enemies:
            base = self.project_point(e["x"], 0.02, e["z"])
            if base is None: continue
            sx, sy_, d = base
            if d > 30.0: continue
            r = int((0.55 + 0.15*e["spec"]["sc"]) * focal / d * 1.4)
            if r < 2: continue
            sprite = get(r)
            rr = sprite.get_width() >> 1
            blit(sprite, (int(sx) - rr, int(sy_) - rr))
            dirty = True
        for c in self.crates:
            base = self.project_point(c["x"], 0.02, c["z"])
            if base is None: continue
            sx, sy_, d = base
            if d > 30.0: continue
            r = int(max(c["sx"], c["sz"]) * focal / d * 1.5)
            if r < 3: continue
            sprite = get(r)
            rr = sprite.get_width() >> 1
            blit(sprite, (int(sx) - rr, int(sy_) - rr))
            dirty = True
        if dirty:
            scr.blit(surf, (0, 0))

    def draw_chromatic(self, scr):
        v = self.damage_vignette
        if v <= 0.10: return
        amt = int(3 * v)
        if amt <= 0: return
        rw, rh = self._rw, self._rh
        buf = self.chroma_buf
        if buf.get_width() < rw or buf.get_height() < rh:
            buf = pygame.Surface((rw, rh), pygame.SRCALPHA)
            self.chroma_buf = buf
        buf.fill((0, 0, 0, 0), (0, 0, rw, rh))
        buf.fill((int(80*v), 0, 0, 0), (0, 0, rw, rh))
        scr.blit(buf, (amt, 0), special_flags=pygame.BLEND_ADD,
                 area=(0, 0, rw - amt, rh))
        buf.fill((0, 0, 0, 0), (0, 0, rw, rh))
        buf.fill((0, 0, int(80*v), 0), (0, 0, rw, rh))
        scr.blit(buf, (-amt, 0), special_flags=pygame.BLEND_ADD,
                 area=(amt, 0, rw - amt, rh))

    def draw_world_overlays(self, scr):
        for e in self.enemies:
            if e["hp"] >= e["max_hp"]-0.5: continue
            p = self.project_point(e["x"], 2.25*e["spec"]["sc"], e["z"])
            if p is None: continue
            sx, sy_, d = p
            if d > 45.0: continue
            w = max(24, int(120/d * 2.0 * (2.5 if e.get("is_boss") else 1)))
            frac = max(0.0, e["hp"]/e["max_hp"])
            x0 = int(sx-w*0.5); y0 = int(sy_)
            bg = (12,14,28) if not e.get("is_boss") else (40,14,14)
            fg = (200,60,60) if not e.get("is_boss") else (255,140,60)
            pygame.draw.rect(scr, bg, (x0-1,y0-1,w+2,6))
            pygame.draw.rect(scr, fg, (x0,y0,int(w*frac),4))
        if self.hurt_dir_t > 0.0:
            hx, hz = self.hurt_dir
            ang = math.atan2(hx - self.px, hz - self.pz) - self.yaw
            while ang >  math.pi: ang -= TAU
            while ang < -math.pi: ang += TAU
            a = int(220 * min(1.0, self.hurt_dir_t / 0.8))
            if a > 0:
                r = self._rh * 0.28
                hw, hh = self._rw * 0.5, self._rh * 0.5
                sx = hw + math.sin(ang) * r
                sy_ = hh - math.cos(ang) * r
                pts = [(sx + math.sin(ang) * 14,      sy_ - math.cos(ang) * 14),
                       (sx + math.sin(ang + 2.5) * 11, sy_ - math.cos(ang + 2.5) * 11),
                       (sx + math.sin(ang - 2.5) * 11, sy_ - math.cos(ang - 2.5) * 11)]
                hm = self.hit_overlay
                hm.fill((0, 0, 0, 0))
                pygame.draw.polygon(hm, (255, 60, 60, a), pts)
                scr.blit(hm, (0, 0))

    # ------------------------------------------------------------------
    #  PROJECTION + PRIMITIVES
    # ------------------------------------------------------------------
    def project_point(self, x, y, z):
        dx = x - self.camx; dy = y - self.camy; dz = z - self.camz
        cy = self.cyaw; sy = self.syaw
        cp = self.cpitch; sp = self.spitch
        z1 = sy * dx + cy * dz
        zc = sp * dy + cp * z1
        if zc <= NEAR: return None
        xc = cy * dx - sy * dz
        yc = cp * dy - sp * z1
        inv = self.focal / zc
        sx = self._rw * 0.5 + xc * inv
        sy_ = self._rh * 0.5 - yc * inv
        if sx < -SCREEN_CLAMP: sx = -SCREEN_CLAMP
        elif sx > SCREEN_CLAMP: sx = SCREEN_CLAMP
        if sy_ < -SCREEN_CLAMP: sy_ = -SCREEN_CLAMP
        elif sy_ > SCREEN_CLAMP: sy_ = SCREEN_CLAMP
        return (sx, sy_, zc)

    def face_light(self, nx, ny, nz, x, y, z):
        n = math.sqrt(nx*nx + ny*ny + nz*nz)
        if n > 1e-9:
            nx /= n; ny /= n; nz /= n
        d = nx*self.LX + ny*self.LY + nz*self.LZ
        if d < 0.0: d = 0.0
        r = self.ambient + (1.0 - self.ambient) * d
        if self.flash_light is not None:
            fx, fy, fz, rad, inten = self.flash_light
            fdx = x - fx; fdy = y - fy; fdz = z - fz
            dd = math.sqrt(fdx*fdx + fdy*fdy + fdz*fdz)
            if dd < rad:
                k = 1.0 - dd / rad
                r += k * k * inten * 0.75
        if r > 1.65: r = 1.65
        return r

    def _to_cam_5(self, wp, uv):
        cx = self.camx; cyy = self.camy; cz = self.camz
        cy = self.cyaw; sy = self.syaw
        cp = self.cpitch; sp = self.spitch
        out = []
        for (wx, wy, wz), (u, v) in zip(wp, uv):
            dx = wx - cx; dy = wy - cyy; dz = wz - cz
            z1 = sy*dx + cy*dz
            xc = cy*dx - sy*dz
            yc = cp*dy - sp*z1
            zc = sp*dy + cp*z1
            out.append((xc, yc, zc, u, v))
        return out

    def _fog_blend(self, r, g, b, depth):
        if not S["fog"]:
            return (int(r) if 0 <= r < 255 else (0 if r < 0 else 255),
                    int(g) if 0 <= g < 255 else (0 if g < 0 else 255),
                    int(b) if 0 <= b < 255 else (0 if b < 0 else 255))
        fd = depth - FOG_START
        if fd <= 0.0:
            fogf = 0.0
        else:
            fogf = 1.0 - math.exp(-fd * 0.055)
            if fogf > 1.0: fogf = 1.0
        fr = self.fog_r; fg = self.fog_g; fb = self.fog_b
        r = r * (1.0 - fogf) + fr * fogf
        g = g * (1.0 - fogf) + fg * fogf
        b = b * (1.0 - fogf) + fb * fogf
        if r > 255.0: r = 255.0
        elif r < 0.0: r = 0.0
        if g > 255.0: g = 255.0
        elif g < 0.0: g = 0.0
        if b > 255.0: b = 255.0
        elif b < 0.0: b = 0.0
        return (int(r), int(g), int(b))

    def _emit_poly(self, cam, mips, lit, outline, tint, emissive, glow=False):
        n = len(cam)
        if n < 3: return
        pts = []
        usum = 0.0; vsum = 0.0; zsum = 0.0
        hw = self._rw * 0.5; hh = self._rh * 0.5
        for xc, yc, zc, u, v in cam:
            if zc < NEAR: return
            inv = self.focal / zc
            sx = hw + xc * inv
            sy_ = hh - yc * inv
            if sx < -SCREEN_CLAMP: sx = -SCREEN_CLAMP
            elif sx > SCREEN_CLAMP: sx = SCREEN_CLAMP
            if sy_ < -SCREEN_CLAMP: sy_ = -SCREEN_CLAMP
            elif sy_ > SCREEN_CLAMP: sy_ = SCREEN_CLAMP
            pts.append((sx, sy_))
            usum += u; vsum += v; zsum += zc

        # Cheap frustum cull: drop polys entirely off-screen.
        xs_min = xs_max = pts[0][0]
        ys_min = ys_max = pts[0][1]
        for px, py in pts:
            if px < xs_min: xs_min = px
            elif px > xs_max: xs_max = px
            if py < ys_min: ys_min = py
            elif py > ys_max: ys_max = py
        if xs_max < 0.0 or xs_min > self._rw:
            return
        if ys_max < 0.0 or ys_min > self._rh:
            return

        depth = zsum / n
        if depth > FOG_END + 6.0:
            return
        cu = (usum / n) % 1.0
        cv = (vsum / n) % 1.0
        di = int(depth)
        if 0 <= di < 256:
            lod = self._lod_table[di]
        else:
            lod = self._lod_table[-1]
        if lod >= 2.0:
            tr, tg, tb = sample_tex_nearest(mips, cu, cv)
        else:
            tr, tg, tb = sample_tex_bilinear(mips, cu, cv, lod)
        if tint is not None:
            tr *= tint[0]; tg *= tint[1]; tb *= tint[2]
        if emissive:
            r, g, b = tr, tg, tb
        else:
            r = tr * lit; g = tg * lit; b = tb * lit
        col = self._fog_blend(r, g, b, depth)
        self._render.append((depth, pts, col, outline))
        if glow and emissive:
            cxs = sum(p[0] for p in pts) / len(pts)
            cys = sum(p[1] for p in pts) / len(pts)
            halo = [(cxs + (px - cxs) * 1.6, cys + (py - cys) * 1.6)
                    for px, py in pts]
            halo_col = (min(255, int(col[0] * 0.35)),
                        min(255, int(col[1] * 0.35)),
                        min(255, int(col[2] * 0.35)))
            self._render.append((depth + 0.02, halo, halo_col, False))

    def add_quad(self, wp, uv, mips, lit, max_n=0, outline=True,
                 tint=None, emissive=False, glow=False):
        cam = self._to_cam_5(wp, uv)
        if all(c[2] < NEAR for c in cam):
            return
        if any(c[2] < NEAR for c in cam):
            cam = clip_near_poly(cam)
            if len(cam) < 3:
                return
            self._emit_poly(cam, mips, lit, outline, tint, emissive, glow)
            return
        if max_n > 0:
            invs = [self.focal / c[2] for c in cam]
            sxs  = [self._rw * 0.5 + c[0] * inv for c, inv in zip(cam, invs)]
            sys_ = [self._rh * 0.5 - c[1] * inv for c, inv in zip(cam, invs)]
            w = max(sxs) - min(sxs); h = max(sys_) - min(sys_)
            if w * h > 3600.0 and w < 1e6 and h < 1e6:
                p = wp; u = uv
                def midp(i, j):
                    return ((p[i][0] + p[j][0]) * 0.5,
                            (p[i][1] + p[j][1]) * 0.5,
                            (p[i][2] + p[j][2]) * 0.5)
                def miduv(i, j):
                    return ((u[i][0] + u[j][0]) * 0.5,
                            (u[i][1] + u[j][1]) * 0.5)
                e01 = midp(0, 1); e12 = midp(1, 2)
                e23 = midp(2, 3); e03 = midp(3, 0)
                cc  = ((p[0][0] + p[1][0] + p[2][0] + p[3][0]) * 0.25,
                       (p[0][1] + p[1][1] + p[2][1] + p[3][1]) * 0.25,
                       (p[0][2] + p[1][2] + p[2][2] + p[3][2]) * 0.25)
                u01 = miduv(0, 1); u12 = miduv(1, 2)
                u23 = miduv(2, 3); u03 = miduv(3, 0)
                ucc = ((u[0][0] + u[1][0] + u[2][0] + u[3][0]) * 0.25,
                       (u[0][1] + u[1][1] + u[2][1] + u[3][1]) * 0.25)
                nn = max_n - 1
                self.add_quad([p[0], e01, cc,  e03], [u[0], u01, ucc, u03],
                              mips, lit, nn, outline, tint, emissive, glow)
                self.add_quad([e01,  p[1], e12, cc],  [u01, u[1], u12, ucc],
                              mips, lit, nn, outline, tint, emissive, glow)
                self.add_quad([cc,   e12, p[2], e23], [ucc, u12, u[2], u23],
                              mips, lit, nn, outline, tint, emissive, glow)
                self.add_quad([e03,  cc,  e23, p[3]], [u03, ucc, u23, u[3]],
                              mips, lit, nn, outline, tint, emissive, glow)
                return
        self._emit_poly(cam, mips, lit, outline, tint, emissive, glow)

    def add_color_quad(self, wp, color):
        cam = self._to_cam_5(wp, [(0.0, 0.0)] * len(wp))
        if all(c[2] < NEAR for c in cam):
            return
        if any(c[2] < NEAR for c in cam):
            cam = clip_near_poly(cam)
            if len(cam) < 3:
                return
        pts = []
        zsum = 0.0
        hw = self._rw * 0.5; hh = self._rh * 0.5
        for xc, yc, zc, _, _ in cam:
            if zc < NEAR: return
            inv = self.focal / zc
            sx = hw + xc * inv
            sy_ = hh - yc * inv
            if sx < -SCREEN_CLAMP: sx = -SCREEN_CLAMP
            elif sx > SCREEN_CLAMP: sx = SCREEN_CLAMP
            if sy_ < -SCREEN_CLAMP: sy_ = -SCREEN_CLAMP
            elif sy_ > SCREEN_CLAMP: sy_ = SCREEN_CLAMP
            pts.append((sx, sy_))
            zsum += zc
        depth = zsum / len(cam)
        col = self._fog_blend(color[0], color[1], color[2], depth)
        self._render.append((depth, pts, col, False))

    def add_cube(self, cx, cy, cz, sx, sy, sz, mips, rot,
                 tint=None, outline=True, point=None, glow=False, emissive=False):
        ca = math.cos(rot); sa = math.sin(rot)
        verts = []
        for vx, vy, vz in CUBE_VERTS:
            wx = vx * sx; wy = vy * sy; wz = vz * sz
            rx = wx * ca - wz * sa
            rz = wx * sa + wz * ca
            verts.append((cx + rx, cy + wy, cz + rz))
        max_n = 0 if emissive else 2
        for fidx, _a, _b, _c, _d in CUBE_FACES:
            quad = [verts[i] for i in fidx]
            onx = 0.0; ony = 0.0; onz = 0.0
            for v in quad:
                onx += v[0] - cx; ony += v[1] - cy; onz += v[2] - cz
            qx = onx * 0.25; qy = ony * 0.25; qz = onz * 0.25
            ccx = cx + qx; ccy = cy + qy; ccz = cz + qz
            vdx = ccx - self.camx; vdy = ccy - self.camy; vdz = ccz - self.camz
            if qx * vdx + qy * vdy + qz * vdz > 0.0:
                continue
            aqx = abs(qx); aqy = abs(qy); aqz = abs(qz)
            if aqx >= aqy and aqx >= aqz:
                uidx, vidx = 2, 1
            elif aqy >= aqz:
                uidx, vidx = 0, 2
            else:
                uidx, vidx = 0, 1
            us = 0.20
            uvs = [(v[uidx] * us, v[vidx] * us) for v in quad]
            lit = self.face_light(qx, qy, qz, ccx, ccy, ccz)
            if emissive:
                lit = 1.0
            self.add_quad(quad, uvs, mips, lit, max_n=max_n,
                          outline=outline, tint=tint, emissive=emissive, glow=glow)

    def add_billboard(self, x, y, z, size, color, glow=False):
        rx = self.cyaw; rz = -self.syaw
        wp = [(x - rx*size, y - size, z - rz*size),
              (x + rx*size, y - size, z + rz*size),
              (x + rx*size, y + size, z + rz*size),
              (x - rx*size, y + size, z - rz*size)]
        cam = self._to_cam_5(wp, [(0.0, 0.0)] * 4)
        if all(c[2] < NEAR for c in cam):
            return
        if any(c[2] < NEAR for c in cam):
            cam = clip_near_poly(cam)
            if len(cam) < 3:
                return
        pts = []
        zsum = 0.0
        hw = self._rw * 0.5; hh = self._rh * 0.5
        for xc, yc, zc, _, _ in cam:
            if zc < NEAR: return
            inv = self.focal / zc
            sx = hw + xc * inv
            sy_ = hh - yc * inv
            if sx < -SCREEN_CLAMP: sx = -SCREEN_CLAMP
            elif sx > SCREEN_CLAMP: sx = SCREEN_CLAMP
            if sy_ < -SCREEN_CLAMP: sy_ = -SCREEN_CLAMP
            elif sy_ > SCREEN_CLAMP: sy_ = SCREEN_CLAMP
            pts.append((sx, sy_))
            zsum += zc
        depth = zsum / len(cam)
        r, g, b = color
        if glow:
            s2 = size * 1.9
            wp2 = [(x - rx*s2, y - s2, z - rz*s2),
                   (x + rx*s2, y - s2, z + rz*s2),
                   (x + rx*s2, y + s2, z + rz*s2),
                   (x - rx*s2, y + s2, z - rz*s2)]
            cam2 = self._to_cam_5(wp2, [(0.0, 0.0)] * 4)
            if all(c[2] >= NEAR for c in cam2):
                pts2 = []
                z2 = 0.0
                for xc, yc, zc, _, _ in cam2:
                    inv = self.focal / zc
                    sx2 = hw + xc * inv
                    sy2 = hh - yc * inv
                    if sx2 < -SCREEN_CLAMP: sx2 = -SCREEN_CLAMP
                    elif sx2 > SCREEN_CLAMP: sx2 = SCREEN_CLAMP
                    if sy2 < -SCREEN_CLAMP: sy2 = -SCREEN_CLAMP
                    elif sy2 > SCREEN_CLAMP: sy2 = SCREEN_CLAMP
                    pts2.append((sx2, sy2))
                    z2 += zc
                d2 = z2 / 4.0
                gc = self._fog_blend(r * 0.32, g * 0.32, b * 0.32, d2)
                self._render.append((d2 + 0.05, pts2, gc, False))
        col = self._fog_blend(r, g, b, depth)
        self._render.append((depth, pts, col, False))

    # ------------------------------------------------------------------
    #  VIEWMODEL
    # ------------------------------------------------------------------
    def draw_gun(self, scr):
        w = WEAPONS[self.wi]
        scale = self.render_scale
        rw, rh = self._rw, self._rh
        bobx = math.sin(self.bob_phase) * 9.0 * self.bob_amt * scale
        boby = abs(math.cos(self.bob_phase)) * 6.0 * self.bob_amt * scale
        kick = self.gun_kick * 14.0 * scale
        cx = rw * 0.74 + bobx
        cy = rh - 34 * scale + boby + kick

        if self.reloading > 0.0:
            rl = self.reloading / max(0.01, w["reload"])
            cy += math.sin(rl * math.pi) * 70.0 * scale

        dark  = (36, 40, 56)
        mid   = (58, 64, 84)
        light = (92, 100, 124)
        edg   = (120, 128, 152)
        dp = pygame.draw.polygon
        dr = pygame.draw.rect
        dl = pygame.draw.line

        if w["name"] == "PISTOL":
            dp(scr, dark,  [(cx-16*scale, cy+70*scale),(cx+22*scale, cy+70*scale),
                            (cx+12*scale, cy-6*scale),(cx-6*scale, cy-6*scale)])
            dp(scr, mid,   [(cx-10*scale, cy-6*scale),(cx+10*scale, cy-6*scale),
                            (cx+7*scale, cy-26*scale),(cx-7*scale, cy-26*scale)])
            dp(scr, light, [(cx-6*scale, cy-26*scale),(cx+6*scale, cy-26*scale),
                            (cx+4*scale, cy-40*scale),(cx-4*scale, cy-40*scale)])
            dr(scr, dark,  (cx-3*scale, cy-52*scale, 6*scale, 14*scale))
        elif w["name"] == "RIFLE":
            dp(scr, dark,  [(cx-22*scale, cy+78*scale),(cx+28*scale, cy+78*scale),
                            (cx+14*scale, cy-2*scale),(cx-10*scale, cy-2*scale)])
            dp(scr, mid,   [(cx-14*scale, cy-2*scale),(cx+12*scale, cy-2*scale),
                            (cx+9*scale, cy-42*scale),(cx-9*scale, cy-42*scale)])
            dr(scr, light, (cx-5*scale, cy-78*scale, 10*scale, 40*scale))
            dr(scr, dark,  (cx-22*scale, cy+10*scale, 16*scale, 26*scale))
            dr(scr, dark,  (cx+6*scale,  cy-46*scale, 12*scale, 6*scale))
        else:
            dp(scr, dark,  [(cx-28*scale, cy+80*scale),(cx+30*scale, cy+80*scale),
                            (cx+16*scale, cy-4*scale),(cx-12*scale, cy-4*scale)])
            dp(scr, mid,   [(cx-16*scale, cy-4*scale),(cx+14*scale, cy-4*scale),
                            (cx+11*scale, cy-52*scale),(cx-11*scale, cy-52*scale)])
            dr(scr, light, (cx-9*scale, cy-88*scale, 18*scale, 40*scale))
            dr(scr, dark,  (cx-22*scale, cy-46*scale, 8*scale, 8*scale))
            dr(scr, dark,  (cx+14*scale, cy-46*scale, 8*scale, 8*scale))

        dl(scr, edg, (cx - 16*scale, cy + 70*scale), (cx + 22*scale, cy + 70*scale), 1)

        if self.muzzle_t > 0.0:
            k = self.muzzle_t / 0.075
            r0 = max(1, int((40 + 26 * k) * scale))
            flash = pygame.transform.scale(self.muzzle_sprite, (r0*2, r0*2))
            inten = int(255 * k)
            flash.fill((inten, inten, inten, 255), special_flags=pygame.BLEND_RGBA_MULT)
            gx = cx
            gy = cy - (52 if w["name"] == "PISTOL"
                       else (78 if w["name"] == "RIFLE" else 88)) * scale
            scr.blit(flash, (int(gx - r0), int(gy - r0)),
                     special_flags=pygame.BLEND_ADD)

            if self.lens_dirt is not None:
                if self._dirt_scaled is None:
                    self._dirt_scaled = pygame.transform.smoothscale(
                        self.lens_dirt, (rw, rh))
                self._dirt_scaled.set_alpha(int(70 * k))
                scr.blit(self._dirt_scaled, (0, 0))

    # ------------------------------------------------------------------
    #  POST
    # ------------------------------------------------------------------
    def draw_bloom(self, scr):
        rw, rh = self._rw, self._rh
        small = pygame.transform.smoothscale(
            scr, (max(1, rw // 4), max(1, rh // 4)))
        # Proper bright-pass: subtract a threshold, clamped at 0.
        # Only pixels above ~150 survive.  Then blur-add back.
        small.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_SUB)
        big = pygame.transform.smoothscale(small, (rw, rh))
        scr.blit(big, (0, 0), special_flags=pygame.BLEND_ADD)

    # ------------------------------------------------------------------
    #  CROSSHAIR
    # ------------------------------------------------------------------
    def draw_crosshair(self):
        scr = self.screen
        cx = WIDTH // 2; cy = HEIGHT // 2
        style = S["cross_style"]
        col = CROSSHAIR_COLORS[S["cross_color"]][1]
        size = 9.0 * S["cross_size"]
        gap = 3.0 * S["cross_gap"]
        thick = S["cross_thick"]

        def line(a, b, c, w):
            pygame.draw.line(scr, (0, 0, 0), a, b, w + 2)
            pygame.draw.line(scr, c, a, b, w)

        if style in (0, 3):
            line((cx - gap - size, cy), (cx - gap, cy), col, thick)
            line((cx + gap, cy), (cx + gap + size, cy), col, thick)
            line((cx, cy - gap - size), (cx, cy - gap), col, thick)
            line((cx, cy + gap), (cx, cy + gap + size), col, thick)
        if style == 1:
            pygame.draw.circle(scr, (0, 0, 0), (cx, cy), 3)
            pygame.draw.circle(scr, col, (cx, cy), 2)
        if style == 2:
            pygame.draw.circle(scr, (0, 0, 0), (cx, cy), int(size * 1.6), thick + 2)
            pygame.draw.circle(scr, col, (cx, cy), int(size * 1.6), thick)
        if style == 3:
            pygame.draw.circle(scr, (0, 0, 0), (cx, cy), 3)
            pygame.draw.circle(scr, col, (cx, cy), 2)
        if style == 4:
            line((cx, cy - gap - size), (cx, cy - gap), col, thick)
            line((cx - size, cy), (cx + size, cy), col, thick)

        if self.hitmarker_t > 0.0:
            k = self.hitmarker_t / 0.16
            a = int(255 * k)
            hm = self.crosshair_surf
            hm.fill((0, 0, 0, 0))
            off = 5; ln = 8
            for (dx, dy) in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                x0 = cx + dx * off; y0 = cy + dy * off
                x1 = cx + dx * (off + ln); y1 = cy + dy * (off + ln)
                pygame.draw.line(hm, (255, 255, 255, a), (x0, y0), (x1, y1), 2)
            scr.blit(hm, (0, 0))

    # ------------------------------------------------------------------
    #  HUD
    # ------------------------------------------------------------------
    def draw_hud(self):
        scr = self.screen
        accent = self.accent

        bx, by = 34, HEIGHT - 54
        bw, bh = 240, 20
        frac = max(0.0, self.health / self.max_health)
        pygame.draw.rect(scr, (12, 14, 26), (bx - 3, by - 3, bw + 6, bh + 6))
        pygame.draw.rect(scr, (52, 16, 20), (bx, by, bw, bh))
        r = int(230 * (1.0 - frac) + 90 * frac)
        g = int(50 + 180 * frac)
        b = int(70 + 60 * frac)
        pygame.draw.rect(scr, (r, g, b), (bx, by, int(bw * frac), bh))
        pygame.draw.rect(scr, (240, 240, 255), (bx, by, bw, bh), 1)
        hp_txt = self.font_xs.render("%d / %d" % (int(self.health), int(self.max_health)),
                                     True, (255, 250, 240))
        scr.blit(hp_txt, (bx + 6, by + 3))

        if self.shield > 0.0:
            sfrac = max(0.0, min(1.0, self.shield / 100.0))
            pygame.draw.rect(scr, (90, 190, 250), (bx, by - 8, int(bw * sfrac), 4))

        w = WEAPONS[self.wi]
        ax = WIDTH - 40
        name = self.font_m.render(w["name"], True, accent)
        scr.blit(name, (ax - name.get_width(), HEIGHT - 88))
        mag = self.mag[self.wi]
        res = self.reserve[self.wi]
        reserve_txt = "INF" if w["reserve"] >= 900 else str(res)
        ammo = self.font_l.render(str(mag), True,
                                  (255, 220, 130) if mag > 0 else (255, 90, 90))
        scr.blit(ammo, (ax - ammo.get_width(), HEIGHT - 78))
        rs = self.font_xl.render("/ " + reserve_txt, True, (170, 190, 210))
        scr.blit(rs, (ax - rs.get_width(), HEIGHT - 52))

        if self.reloading > 0.0:
            rl = 1.0 - self.reloading / max(0.01, w["reload"])
            bx2 = WIDTH // 2 - 70; by2 = HEIGHT // 2 + 46
            pygame.draw.rect(scr, (12, 14, 26), (bx2 - 2, by2 - 2, 144, 10))
            pygame.draw.rect(scr, (60, 60, 80), (bx2, by2, 140, 6))
            pygame.draw.rect(scr, (240, 200, 120), (bx2, by2, int(140 * rl), 6))
            lbl = self.font_xs.render("RELOADING", True, (230, 220, 200))
            scr.blit(lbl, (WIDTH // 2 - lbl.get_width() // 2, by2 - 18))

        mode_name = MODES[self.mode]
        top = self.font_m.render("%s  ·  WAVE %d" % (mode_name, self.wave), True, accent)
        scr.blit(top, (34, 22))
        sub = self.font_s.render(DIFFICULTIES[S["difficulty"]][0], True, (180, 200, 220))
        scr.blit(sub, (34, 50))
        if self.mode == 2:
            rem = max(0, self.time_target - self.session_kills)
            tline = self.font_s.render("TARGET: %d  ·  LEFT: %d" %
                                       (self.time_target, rem), True, (230, 210, 160))
            scr.blit(tline, (34, 74))

        score_s = self.font_m.render("SCORE  %d" % self.score, True, (240, 240, 255))
        scr.blit(score_s, (WIDTH - 34 - score_s.get_width(), 22))
        kill_s = self.font_s.render("KILLS  %d" % self.kills, True, (200, 220, 240))
        scr.blit(kill_s, (WIDTH - 34 - kill_s.get_width(), 50))
        if self.combo > 1:
            c = 200 + min(55, self.combo * 3)
            comb = self.font_xl.render("x%d" % self.combo, True, (255, c, 90))
            scr.blit(comb, (WIDTH - 34 - comb.get_width(), 74))

        n = len(self.enemies)
        if n > 0:
            e_txt = self.font_xs.render("%d HOSTILE%s" % (n, "S" if n != 1 else ""),
                                        True, (255, 130, 130))
            scr.blit(e_txt, (WIDTH // 2 - e_txt.get_width() // 2, 22))

        py = 120
        for k, t_rem in self.powerups_active.items():
            pu = POWERUPS[k]
            dur = pu["dur"]
            frac2 = max(0.0, min(1.0, t_rem / dur))
            col = pu["color"]
            bx3 = 34
            pygame.draw.rect(scr, (12, 14, 26), (bx3 - 2, py - 2, 148, 16))
            pygame.draw.rect(scr, col, (bx3, py, int(144 * frac2), 12))
            lbl = self.font_xs.render(pu["label"], True, (12, 12, 16))
            scr.blit(lbl, (bx3 + 6, py - 1))
            py += 22

        fy = 120
        for text, col, life in self.kill_feed:
            a = int(255 * min(1.0, life / 1.2))
            surf = self.font_s.render(text, True, col)
            surf.set_alpha(a)
            scr.blit(surf, (WIDTH - 34 - surf.get_width(), fy))
            fy += 22

        ty = HEIGHT // 2 - 130
        for text, col, life, total in self.toasts:
            a = int(255 * min(1.0, life / 0.9))
            surf = self.font_xl.render(text, True, col)
            surf.set_alpha(a)
            x = WIDTH // 2 - surf.get_width() // 2
            scr.blit(surf, (x, ty))
            ty += 40

        if self.toast_t > 0.0:
            a = int(255 * min(1.0, self.toast_t / 0.5))
            surf = self.font_m.render(self.toast, True, (240, 240, 255))
            surf.set_alpha(a)
            scr.blit(surf, (WIDTH // 2 - surf.get_width() // 2, 96))

        if self.damage_vignette > 0.02:
            self.dmg_surf.set_alpha(int(255 * min(1.0, self.damage_vignette)))
            scr.blit(self.dmg_surf, (0, 0))

        if self.pickup_flash > 0.0:
            f = self.flash_surf.copy()
            f.set_alpha(int(70 * self.pickup_flash))
            scr.blit(f, (0, 0), special_flags=pygame.BLEND_ADD)

        self.draw_crosshair()

    # ------------------------------------------------------------------
    #  END SCREENS / MENU
    # ------------------------------------------------------------------
    def draw_dead(self):
        scr = self.screen
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((8, 4, 6, 170))
        scr.blit(ov, (0, 0))

        if self.mode == 2 and self.session_kills >= self.time_target:
            title = "TIME ATTACK COMPLETE"
            col = (140, 240, 180)
        else:
            title = "YOU DIED"
            col = (255, 90, 90)

        t = self.font_l.render(title, True, col)
        scr.blit(t, (WIDTH // 2 - t.get_width() // 2, 110))

        lines = [
            "SURVIVED TO WAVE  %d" % max(0, self.wave if self.mode != 2 else self.session_kills),
            "KILLS  %d" % self.kills,
            "SCORE  %d" % self.score,
            "BEST COMBO  x%d" % self.best_combo,
            "TIME  %.1fs" % self.time_elapsed,
        ]
        if self.mode == 2 and S["time_attack_best"] > 0:
            lines.append("BEST TIME  %.1fs" % S["time_attack_best"])
        y = 220
        for ln in lines:
            s = self.font_xl.render(ln, True, (220, 230, 250))
            scr.blit(s, (WIDTH // 2 - s.get_width() // 2, y))
            y += 40

        hint = self.font_m.render("SPACE - return to menu", True, (170, 200, 230))
        scr.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 60))

    def draw_pause(self):
        scr = self.screen
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((4, 6, 14, 165))
        scr.blit(ov, (0, 0))
        t = self.font_l.render("PAUSED", True, (220, 230, 250))
        scr.blit(t, (WIDTH // 2 - t.get_width() // 2, 160))
        hints = [
            "ESC - resume",
            "Q - quit to menu",
            "F11 - toggle fullscreen",
            "",
            "WASD move    SHIFT sprint    SPACE jump",
            "MOUSE aim    LMB fire    R reload",
            "1 / 2 / 3  or  Q / E  switch weapon",
        ]
        y = 260
        for h in hints:
            s = self.font_m.render(h, True, (190, 210, 235))
            scr.blit(s, (WIDTH // 2 - s.get_width() // 2, y))
            y += 34

    def draw_menu(self):
        scr = self.screen
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((3, 5, 14, 150))
        scr.blit(ov, (0, 0))

        title = self.font_t.render(GAME_NAME, True, (240, 248, 255))
        glow  = self.font_t.render(GAME_NAME, True, self.accent)
        glow.set_alpha(90)
        scr.blit(glow, (WIDTH // 2 - glow.get_width() // 2 + 3, 41))
        scr.blit(glow, (WIDTH // 2 - glow.get_width() // 2 - 3, 39))
        scr.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))

        sub = self.font_m.render("%s  ·  ADAPTIVE SOFTWARE FPS" % VERSION,
                                 True, (200, 220, 245))
        scr.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 140))

        page_label = {"main": "", "theme": "THEME", "custom": "CUSTOMIZE",
                      "settings": "SETTINGS", "ach": "ACHIEVEMENTS"}[self.menu_page]
        if page_label:
            pl = self.font_xl.render(page_label, True, self.accent)
            scr.blit(pl, (WIDTH // 2 - pl.get_width() // 2, 176))

        items = self._current_items()
        n = len(items)
        line_h = 34
        total_h = n * line_h
        y0 = max(200, (HEIGHT - total_h) // 2 + 24)
        for i, (label, kind) in enumerate(items):
            y = y0 + i * line_h
            sel = (i == self.menu_index)
            text = self._item_text(label, kind)
            if sel:
                hilit = pygame.Surface((460, line_h - 4), pygame.SRCALPHA)
                hilit.fill((*self.accent, 55))
                scr.blit(hilit, (WIDTH // 2 - 230, y - 2))
                pygame.draw.rect(scr, self.accent,
                                 (WIDTH // 2 - 230, y - 2, 460, line_h - 4), 1)
            col = (255, 240, 200) if sel else (180, 200, 225)
            surf = self.font_xl.render(text, True, col)
            scr.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))

        if self.menu_page == "theme":
            t = THEMES[THEME_NAMES[S["theme"]]]
            x = 30; y = 200; w = 12
            for c in (t["sky_top"], t["sky_mid"], t["fog"], t["dark"]):
                pygame.draw.rect(scr, c, (x, y, w, 120))
                x += w + 4
            desc = self.font_s.render(t["sky_desc"], True, (200, 215, 240))
            scr.blit(desc, (30, y + 130))

        if self.menu_page == "ach":
            gx = 100; gy = 220
            colw = 380; rowh = 26
            for i, (k, nm, desc) in enumerate(ACHIEVEMENTS):
                cx = gx + (i % 2) * colw
                cy = gy + (i // 2) * rowh
                got = k in S["achievements"]
                col = (140, 240, 180) if got else (90, 100, 120)
                mark = "[X]" if got else "[ ]"
                s = self.font_s.render("%s %-18s %s" % (mark, nm, desc), True, col)
                scr.blit(s, (cx, cy))

        hint = ("UP/DOWN · ENTER · LEFT/RIGHT · ESC · F11 FULLSCREEN"
                if self.menu_page == "main"
                else "ESC - back    UP/DOWN - select    LEFT/RIGHT - adjust")
        h = self.font_s.render(hint, True, (150, 175, 205))
        scr.blit(h, (WIDTH // 2 - h.get_width() // 2, HEIGHT - 40))

        fps = int(1000.0 / max(1.0, self._frame_avg))
        polys_drawn = min(len(self._render), self._poly_budget())
        ver = self.font_xs.render(
            "%s v%s   %d fps   scale %.2f   polys %d/%d   %s" %
            (GAME_NAME, VERSION, fps, self.render_scale, polys_drawn, len(self._render),
             "FULLSCREEN" if S.get("fullscreen") else "WINDOWED"),
            True, (110, 130, 150))
        scr.blit(ver, (WIDTH - ver.get_width() - 8, HEIGHT - 18))

    def _item_text(self, label, kind):
        if kind == "choice_difficulty":
            return "%s   < %s >" % (label, DIFFICULTIES[S["difficulty"]][0])
        if kind == "choice_mode":
            return "%s   < %s >" % (label, MODES[S["mode"]])
        if kind == "slider_fov":
            return "%s   < %d >" % (label, S["fov"])
        if kind == "slider_sensitivity":
            return "%s   < %.2f >" % (label, S["sensitivity"])
        if kind == "slider_volume":
            return "%s   < %.2f >" % (label, S["volume"])
        if kind == "slider_cross_size":
            return "%s   < %.2f >" % (label, S["cross_size"])
        if kind == "slider_cross_gap":
            return "%s   < %.2f >" % (label, S["cross_gap"])
        if kind == "slider_cross_thick":
            return "%s   < %d >" % (label, S["cross_thick"])
        if kind == "choice_cross_style":
            return "%s   < %s >" % (label, CROSSHAIR_STYLES[S["cross_style"]])
        if kind == "choice_cross_color":
            return "%s   < %s >" % (label, CROSSHAIR_COLORS[S["cross_color"]][0])
        if kind == "choice_hud_color":
            return "%s   < %s >" % (label, HUD_COLORS[S["hud_color"]][0])
        if kind == "toggle_fullscreen":
            return "%s   [ %s ]" % (label, "ON" if S.get("fullscreen") else "OFF")
        if kind.startswith("toggle_"):
            v = S[kind[7:]]
            return "%s   [ %s ]" % (label, "ON" if v else "OFF")
        if kind.startswith("theme_"):
            nm = kind[6:]
            mark = "o" if THEME_NAMES[S["theme"]] == nm else " "
            return "[%s] %s" % (mark, label)
        return label

    # ------------------------------------------------------------------
    #  FRAME LOOP
    # ------------------------------------------------------------------
    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            dt = clock.tick(TARGET_FPS) / 1000.0
            if dt > 0.05: dt = 0.05
            self._frame_avg = self._frame_avg * 0.90 + (dt * 1000.0) * 0.10
            for e in pygame.event.get():
                self.handle_event(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        save_settings()


# ===========================================================================
#  ENTRY POINT
# ===========================================================================
def main():
    load_settings()

    try:
        pygame.mixer.pre_init(SR, -16, 1, 512)
    except Exception:
        pass

    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass

    fullscreen = bool(S.get("fullscreen", False))
    flags = _SCALED | pygame.RESIZABLE
    if fullscreen:
        flags |= pygame.FULLSCREEN
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    except pygame.error:
        try:
            screen = pygame.display.set_mode(
                (WIDTH, HEIGHT), pygame.FULLSCREEN if fullscreen else 0)
        except pygame.error:
            screen = pygame.display.set_mode((WIDTH, HEIGHT))

    pygame.display.set_caption("%s %s  ·  adaptive software FPS" % (GAME_NAME, VERSION))
    build_sounds()
    game = Game(screen)
    game.run()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()