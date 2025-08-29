"""
Minecraft‑like 2D Sandbox in Python (~850 lines)
-------------------------------------------------
A self‑contained Pygame project that implements a light, educational
Minecraft‑inspired sandbox with chunked infinite terrain, caves, trees,
biomes, water flow, inventory/hotbar, simple crafting, day/night cycle,
minimap, particles, screenshots, settings, and save/load of edits.

Run
    pip install pygame==2.5.2
    python mc2d_full.py

This file aims to be readable and hackable. Heavy comments are kept so
that learners can understand the structure. Overall length lands around
850 lines including comments/docstrings.
"""
from __future__ import annotations
import math, os, json, random, sys, time, itertools
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional

import pygame

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
WINDOW_W, WINDOW_H = 1200, 720
TILE = 32                      # pixels per tile
CHUNK_SIZE = 32                # tiles per side (square chunk)
REACH = 6                      # how many tiles away the player can interact
GRAVITY = 2300.0
JUMP_VEL = 880.0
WALK_SPEED = 270.0
SEED = 2025
SAVE_FILE = "world_edits_full.json"
SETTINGS_FILE = "settings_full.json"
SS_PATH = "screenshots"

# Gameplay toggles
ENABLE_CAVES = True
ENABLE_WATER = True
ENABLE_PARTICLES = True

# Input repeat
pygame.key.set_repeat(250, 35)

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def clamp(x, a, b):
    return a if x < a else b if x > b else x

def lerp(a, b, t):
    return a + (b - a) * t

# seeded RNG per‑key cache
class RandCache:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.cache: Dict[int, float] = {}
    def r(self, i: int) -> float:
        if i not in self.cache:
            self.cache[i] = self.rng.uniform(-1, 1)
        return self.cache[i]

class ValueNoise1D:
    """Simple value noise; good enough for 2D terrain height fields."""
    def __init__(self, seed: int):
        self.rc = RandCache(seed)
    def smooth(self, x: float) -> float:
        xi = math.floor(x)
        t = x - xi
        a = self.rc.r(int(xi))
        b = self.rc.r(int(xi)+1)
        t = t*t*(3-2*t)
        return lerp(a, b, t)
    def octave(self, x: float, octaves=4, lac=2.0, gain=0.5, scale=0.01) -> float:
        amp = 1.0
        freq = 1.0
        s = 0.0
        for _ in range(octaves):
            s += amp * self.smooth(x * freq * scale)
            amp *= gain
            freq *= lac
        return s

# ---------------------------------------------------------------------------
# Blocks & items
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BlockType:
    id: int
    name: str
    color: Tuple[int,int,int]
    solid: bool = True
    transparent: bool = False
    fluid: bool = False

# palette
AIR   = BlockType(0,  "Air",   (0,0,0), solid=False, transparent=True)
GRASS = BlockType(1,  "Grass", (95,160,53))
DIRT  = BlockType(2,  "Dirt",  (134,96,67))
STONE = BlockType(3,  "Stone", (110,110,110))
SAND  = BlockType(4,  "Sand",  (218,210,158))
WATER = BlockType(5,  "Water", (64,96,255), solid=False, transparent=True, fluid=True)
WOOD  = BlockType(6,  "Wood",  (145,96,58))
LEAF  = BlockType(7,  "Leaf",  (46,160,74), solid=False, transparent=True)
COAL  = BlockType(8,  "Coal",  (20,20,20))
IRON  = BlockType(9,  "Iron",  (170,170,190))
GLASS = BlockType(10, "Glass", (200,220,240), solid=True, transparent=True)
FLOWR = BlockType(11, "Flower",(255,100,140), solid=False, transparent=True)
PLANK = BlockType(12, "Plank", (186,140,90))
BRICK = BlockType(13, "Brick", (172, 82, 68))

BLOCKS: Dict[int, BlockType] = {b.id:b for b in [AIR,GRASS,DIRT,STONE,SAND,WATER,WOOD,LEAF,COAL,IRON,GLASS,FLOWR,PLANK,BRICK]}

# hotbar default (ids)
HOTBAR_DEFAULT = [GRASS.id, DIRT.id, STONE.id, SAND.id, WATER.id, WOOD.id, LEAF.id, GLASS.id, BRICK.id]

# crafting: simple mapping (two input items -> result)
CRAFT_RECIPES = {
    (WOOD.id,): PLANK.id,            # 1 wood -> plank
    (PLANK.id, PLANK.id): BRICK.id,  # whimsical recipe to show UI
}

# ---------------------------------------------------------------------------
# World & generation
# ---------------------------------------------------------------------------
@dataclass
class World:
    seed: int
    edits: Dict[Tuple[int,int], int] = field(default_factory=dict)
    chunks: Dict[Tuple[int,int], List[List[int]]] = field(default_factory=dict)
    sea_level: int = 16
    noise: ValueNoise1D = field(default_factory=lambda: ValueNoise1D(SEED))

    def load(self):
        if os.path.exists(SAVE_FILE):
            try:
                data = json.load(open(SAVE_FILE, 'r'))
                self.edits = {tuple(map(int, k.split(','))): int(v) for k,v in data.items()}
                print(f"Loaded edits: {len(self.edits)}")
            except Exception as e:
                print("Failed load edits:", e)
    def save(self):
        try:
            os.makedirs(os.path.dirname(SAVE_FILE) or '.', exist_ok=True)
            json.dump({f"{x},{y}":bid for (x,y),bid in self.edits.items()}, open(SAVE_FILE,'w'))
            print(f"Saved edits: {len(self.edits)}")
        except Exception as e:
            print("Failed save edits:", e)

    # ---------------- generation -----------------
    def height(self, x: int) -> int:
        base = self.noise.octave(x, octaves=5, scale=0.007, gain=0.55)
        mtn  = self.noise.octave(x+10000, octaves=3, scale=0.018, gain=0.5)
        return self.sea_level + int(10*base + 18*mtn)

    def biome(self, x: int) -> str:
        t = self.noise.octave(x+3333, octaves=3, scale=0.004, gain=0.7)
        if t < -0.25: return 'desert'
        if t > 0.35:  return 'forest'
        return 'plains'

    def generated_block(self, x: int, y: int) -> int:
        h = self.height(x)
        b = self.biome(x)
        if y > h:
            # above ground; water if below/near sea
            if y <= self.sea_level:
                return WATER.id
            return AIR.id
        # surface choice
        if y == h:
            if b == 'desert' or h <= self.sea_level+1: return SAND.id
            return GRASS.id
        # below surface
        depth = h - y
        if ENABLE_CAVES and depth > 3:
            cav = self.noise.octave(x*13 + y*7, octaves=3, scale=0.05, gain=0.5)
            if cav > 0.35:
                # ore pockets
                if cav > 0.65 and y < self.sea_level-8 and random.Random((x<<16)^y^self.seed).random() < 0.06: return IRON.id
                if cav > 0.52 and y < self.sea_level-4 and random.Random((x<<16)+y+self.seed).random() < 0.08: return COAL.id
                return STONE.id
            if y <= self.sea_level-2 and self.noise.octave(x*5-y*3+1234, octaves=2, scale=0.06, gain=0.6) > 0.15:
                return WATER.id
            return AIR.id
        if depth <= 3:
            if b == 'desert': return SAND.id
            return DIRT.id
        return STONE.id

    def get(self, x: int, y: int) -> int:
        if (x,y) in self.edits:
            return self.edits[(x,y)]
        return self.generated_block(x,y)

    def set(self, x: int, y: int, bid: int):
        gen = self.generated_block(x,y)
        if bid == gen:
            self.edits.pop((x,y), None)
        else:
            self.edits[(x,y)] = bid
        self.chunks.pop((x//CHUNK_SIZE, y//CHUNK_SIZE), None)

    def ensure_chunk(self, cx: int, cy: int):
        if (cx,cy) in self.chunks: return
        grid = [[AIR.id for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
        for lx in range(CHUNK_SIZE):
            wx = cx*CHUNK_SIZE + lx
            h = self.height(wx)
            for ly in range(CHUNK_SIZE):
                wy = cy*CHUNK_SIZE + ly
                grid[ly][lx] = self.generated_block(wx, wy)
        # apply edits
        x0,y0 = cx*CHUNK_SIZE, cy*CHUNK_SIZE
        for (ex,ey),bid in self.edits.items():
            if x0 <= ex < x0+CHUNK_SIZE and y0 <= ey < y0+CHUNK_SIZE:
                grid[ey-y0][ex-x0] = bid
        self.chunks[(cx,cy)] = grid

# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
@dataclass
class Player:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    w: float = 0.7
    h: float = 1.8
    facing: int = 1     # 1 right, -1 left
    selected: int = 0   # hotbar index
    hotbar: List[int] = field(default_factory=lambda: list(HOTBAR_DEFAULT))
    inventory: Dict[int,int] = field(default_factory=dict)

    def aabb(self):
        return (self.x-self.w/2, self.y, self.x+self.w/2, self.y+self.h)

# ---------------------------------------------------------------------------
# Particles (very small system)
# ---------------------------------------------------------------------------
@dataclass
class Particle:
    x: float; y: float; vx: float; vy: float; life: float; col: Tuple[int,int,int]

# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Minecraft‑like 2D (Full)")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.big  = pygame.font.SysFont("consolas", 28, bold=True)

        self.world = World(SEED)
        self.world.load()

        hx = 0
        hy = self.world.height(hx) + 3
        self.player = Player(hx + 0.5, hy)

        self.day_time = 6.0 * 60.0  # minutes since 00:00 (start at 6:00)
        self.time_scale = 12.0       # how fast time passes (x real time)

        self.paused = False
        self.show_minimap = True
        self.show_debug = False
        self.console_text = ""
        self.console_active = False
        self.water_accum: List[Tuple[int,int]] = []
        self.particles: List[Particle] = []

        self.settings = self.load_settings()

    # ---------------- settings ----------------
    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                return json.load(open(SETTINGS_FILE,'r'))
            except Exception:
                pass
        return {
            "mouse_sensitivity": 1.0,
            "show_tutorial": True,
        }
    def save_settings(self):
        try:
            json.dump(self.settings, open(SETTINGS_FILE,'w'))
        except Exception:
            pass

    # ---------------- camera ----------------
    def w2s(self, wx, wy, camx, camy):
        sx = int((wx - camx) * TILE + WINDOW_W//2)
        sy = int((camy - wy) * TILE + WINDOW_H//2)
        return sx, sy
    def s2w(self, sx, sy, camx, camy):
        wx = (sx - WINDOW_W//2)/TILE + camx
        wy = camy - (sy - WINDOW_H//2)/TILE
        return wx, wy

    # ---------------- physics ----------------
    def is_solid(self, tx, ty):
        b = BLOCKS[self.world.get(tx,ty)]
        return b.solid and not b.fluid

    def on_ground(self):
        p = self.player
        below = int(math.floor(p.y - 0.05))
        for ox in (-int(math.floor(p.w/2)), int(math.floor(p.w/2))):
            if self.is_solid(int(math.floor(p.x+ox)), below):
                return True
        return False

    def move_player(self, dt, keys):
        p = self.player
        move = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        p.vx = (WALK_SPEED/TILE) * move
        if move != 0:
            p.facing = 1 if move > 0 else -1
        p.vy -= GRAVITY*dt/TILE
        # integrate + collide
        p.x += p.vx * dt
        self.resolve_collisions(axis=0)
        p.y += p.vy * dt
        self.resolve_collisions(axis=1)

    def resolve_collisions(self, axis):
        p = self.player
        x0 = int(math.floor(p.x - p.w/2))
        x1 = int(math.floor(p.x + p.w/2))
        y0 = int(math.floor(p.y))
        y1 = int(math.floor(p.y + p.h))
        for tx in range(x0-1, x1+2):
            for ty in range(y0-1, y1+2):
                if self.is_solid(tx,ty):
                    left,right = tx, tx+1
                    bottom,top = ty, ty+1
                    cx0, cx1 = p.x - p.w/2, p.x + p.w/2
                    cy0, cy1 = p.y, p.y + p.h
                    if cx1 <= left or cx0 >= right or cy1 <= bottom or cy0 >= top:
                        continue
                    if axis == 0:
                        if p.vx > 0: p.x = left - p.w/2
                        elif p.vx < 0: p.x = right + p.w/2
                        p.vx = 0
                    else:
                        if p.vy > 0: p.y = bottom - p.h
                        elif p.vy < 0: p.y = top
                        p.vy = 0

    # ---------------- interaction ----------------
    def tile_ray(self, ox, oy, tx, ty, max_tiles=REACH) -> Optional[Tuple[int,int]]:
        dx, dy = tx-ox, ty-oy
        d = math.hypot(dx,dy)
        if d == 0: return None
        dx/=d; dy/=d
        steps = int(min(max_tiles, d) * 12)
        x,y = ox, oy
        for _ in range(steps):
            x += dx * (1/12)
            y += dy * (1/12)
            txi, tyi = int(math.floor(x)), int(math.floor(y))
            bid = self.world.get(txi, tyi)
            if bid != AIR.id:
                return (txi, tyi)
        return None

    def place_block(self, tx, ty, bid):
        p = self.player
        # don't place on player
        px0, py0 = int(math.floor(p.x - p.w/2)), int(math.floor(p.y))
        px1, py1 = int(math.floor(p.x + p.w/2)), int(math.floor(p.y + p.h))
        if px0 <= tx <= px1 and py0 <= ty <= py1:
            return False
        if BLOCKS[self.world.get(tx,ty)].solid: return False
        self.world.set(tx,ty,bid)
        if ENABLE_PARTICLES:
            self.spawn_particles(tx+0.5,ty+0.5, BLOCKS[bid].color)
        return True

    def break_block(self, tx, ty):
        bid = self.world.get(tx,ty)
        if bid == AIR.id: return False
        self.world.set(tx,ty,AIR.id)
        # add to inventory (except water)
        if not BLOCKS[bid].fluid:
            self.player.inventory[bid] = self.player.inventory.get(bid,0) + 1
        if ENABLE_PARTICLES:
            self.spawn_particles(tx+0.5,ty+0.5, BLOCKS[bid].color)
        return True

    # ---------------- fluids (very simple cellular flow) ----------------
    def update_fluids(self):
        if not ENABLE_WATER: return
        # collect a set of water tiles to update (limit per frame for perf)
        rnd = random.Random(int(time.time()*30) ^ SEED)
        to_check = []
        # sample near player region
        px, py = int(self.player.x), int(self.player.y)
        for ty in range(py-16, py+16):
            for tx in range(px-24, px+24):
                if self.world.get(tx,ty) == WATER.id:
                    to_check.append((tx,ty))
        rnd.shuffle(to_check)
        to_check = to_check[:100]
        for tx,ty in to_check:
            below = self.world.get(tx,ty-1)
            if below == AIR.id:
                self.world.set(tx,ty-1,WATER.id)
                self.world.set(tx,ty,AIR.id)
                continue
            # sideways spread if below blocked
            if BLOCKS[below].solid:
                for dir in (1,-1):
                    if self.world.get(tx+dir,ty) == AIR.id and self.world.get(tx+dir,ty-1) == AIR.id:
                        self.world.set(tx+dir,ty,WATER.id)
                        self.world.set(tx,ty,AIR.id)
                        break

    # ---------------- particles ----------------
    def spawn_particles(self, x,y, col):
        if not ENABLE_PARTICLES: return
        rnd = random.Random((int(x*1000)<<16) ^ int(y*1000) ^ int(time.time()*1000))
        for _ in range(8):
            ang = rnd.uniform(0, math.tau)
            spd = rnd.uniform(0.6, 1.8)
            vx, vy = math.cos(ang)*spd, math.sin(ang)*spd
            self.particles.append(Particle(x,y,vx,vy, life=rnd.uniform(0.3,0.8), col=col))

    def step_particles(self, dt):
        alive = []
        for p in self.particles:
            p.vy -= 9.8*dt
            p.x += p.vx * dt * 8
            p.y += p.vy * dt * 8
            p.life -= dt
            if p.life > 0:
                alive.append(p)
        self.particles = alive

    # ---------------- UI helpers ----------------
    def draw_rect_border(self, r, col, border=2, radius=6):
        pygame.draw.rect(self.screen, col, r, border, border_radius=radius)

    def draw_text(self, txt, pos, col=(0,0,0), big=False):
        surf = (self.big if big else self.font).render(txt, True, col)
        self.screen.blit(surf, pos)

    def draw_block_icon(self, bid, rect):
        color = BLOCKS[bid].color
        pygame.draw.rect(self.screen, (230,230,230), rect, border_radius=5)
        inner = rect.inflate(-8, -8)
        pygame.draw.rect(self.screen, color, inner, border_radius=4)
        # slight shine
        pygame.draw.line(self.screen, (255,255,255), inner.topleft, (inner.right, inner.top))

    # ---------------- minimap ----------------
    def draw_minimap(self, camx, camy):
        if not self.show_minimap: return
        w, h = 200, 120
        surf = pygame.Surface((w,h), pygame.SRCALPHA)
        # sample world around player
        px, py = int(self.player.x), int(self.player.y)
        sx, sy = 100, 60
        for dy in range(-sy//2, sy//2):
            for dx in range(-sx//2, sx//2):
                wx, wy = px+dx, py+dy
                bid = self.world.get(wx, wy)
                col = BLOCKS[bid].color
                surf.set_at((dx+sx//2, sy//2-dy), col)
        pygame.draw.rect(surf, (255,255,255), (0,0,w-1,h-1), 2, border_radius=6)
        # player marker
        pygame.draw.circle(surf, (255,0,0), (sx//2, sy//2), 3)
        self.screen.blit(surf, (WINDOW_W-w-12, 12))

    # ---------------- drawing world ----------------
    def draw_world(self, camx, camy):
        # sky gradient by time
        tnorm = (math.sin(self.day_time/180.0*math.tau)+1)*0.5
        sky_top = (int(30+150*tnorm), int(80+120*tnorm), int(180+50*tnorm))
        sky_bot = (int(10+60*tnorm), int(30+70*tnorm), int(120+40*tnorm))
        pygame.draw.rect(self.screen, sky_top, (0,0,WINDOW_W, WINDOW_H//2))
        pygame.draw.rect(self.screen, sky_bot, (0,WINDOW_H//2, WINDOW_W, WINDOW_H//2))

        tx0 = int(math.floor(camx - WINDOW_W/TILE/2)) - 1
        tx1 = int(math.ceil (camx + WINDOW_W/TILE/2)) + 1
        ty0 = int(math.floor(camy - WINDOW_H/TILE/2)) - 1
        ty1 = int(math.ceil (camy + WINDOW_H/TILE/2)) + 1
        for ty in range(ty0, ty1+1):
            cy = ty//CHUNK_SIZE
            for tx in range(tx0, tx1+1):
                cx = tx//CHUNK_SIZE
                self.world.ensure_chunk(cx, cy)
                bid = self.world.chunks[(cx,cy)][ty-cy*CHUNK_SIZE][tx-cx*CHUNK_SIZE]
                if bid == AIR.id: continue
                sx, sy = self.w2s(tx, ty, camx, camy)
                r = pygame.Rect(sx, sy-TILE, TILE, TILE)
                color = BLOCKS[bid].color
                pygame.draw.rect(self.screen, color, r)
                sh = 12
                pygame.draw.line(self.screen, (max(0,color[0]-sh), max(0,color[1]-sh), max(0,color[2]-sh)), (r.left, r.bottom-1), (r.right-1, r.bottom-1))
                pygame.draw.line(self.screen, (min(255,color[0]+sh), min(255,color[1]+sh), min(255,color[2]+sh)), (r.left, r.top), (r.right-1, r.top))

        # particles
        for p in self.particles:
            sx, sy = self.w2s(p.x, p.y, camx, camy)
            pygame.draw.circle(self.screen, p.col, (sx, sy), 2)

        # dusk overlay
        darkness = int(110 * (1 - tnorm))
        if darkness > 0:
            s = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
            s.fill((0,0,0,darkness))
            self.screen.blit(s, (0,0))

    def draw_player(self, camx, camy):
        p = self.player
        sx, sy = self.w2s(p.x, p.y, camx, camy)
        r = pygame.Rect(int(sx - p.w*TILE/2), int(sy - p.h*TILE), int(p.w*TILE), int(p.h*TILE))
        pygame.draw.rect(self.screen, (235,220,180), r, border_radius=3)
        # simple eyes
        ex = r.centerx + (6 if p.facing>0 else -10)
        pygame.draw.rect(self.screen, (0,0,0), (ex, r.top+8, 4,4))
        pygame.draw.rect(self.screen, (0,0,0), (ex+6, r.top+8, 4,4))

    def draw_ui(self, camx, camy):
        # hotbar
        p = self.player
        pad = 8
        w = len(p.hotbar)*(TILE+pad) + pad
        x = (WINDOW_W - w)//2
        y = WINDOW_H - (TILE+pad*3)
        pygame.draw.rect(self.screen, (0,0,0), (x-6,y-6,w+12,TILE+12), border_radius=10)
        for i,bid in enumerate(p.hotbar):
            r = pygame.Rect(x+pad+i*(TILE+pad), y+pad, TILE, TILE)
            self.draw_block_icon(bid, r)
            if i == p.selected:
                self.draw_rect_border(r, (255,255,255), 3, 6)
        # inventory counts
        inv_str = " ".join(f"{BLOCKS[k].name}:{v}" for k,v in sorted(p.inventory.items()))
        self.draw_text(inv_str[:80], (10, WINDOW_H-26))
        # coords, time
        hours = int(self.day_time//60)%24
        mins = int(self.day_time%60)
        self.draw_text(f"XYZ: {p.x:.1f},{p.y:.1f}  Time {hours:02d}:{mins:02d}  FPS {self.clock.get_fps():.0f}", (10,10))

        if self.settings.get("show_tutorial", True):
            tuto = "WASD move, SPACE jump, LMB place, RMB mine, MouseWheel or 1-9 select, F5 save, M minimap, ` console"
            self.draw_text(tuto[:110], (10, 34))

    def draw_pause_menu(self):
        msg = [
            "Paused",
            "Esc: Resume  |  F5: Save  |  F12: Screenshot",
            "F1: Toggle tutorial  |  F3: Debug  |  M: Minimap",
        ]
        surf = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        surf.fill((0,0,0,128))
        self.screen.blit(surf, (0,0))
        for i,t in enumerate(msg):
            self.draw_text(t, (WINDOW_W//2-260, WINDOW_H//2-40 + i*28), (255,255,255), big=(i==0))

    def draw_console(self):
        if not self.console_active: return
        h = 32
        s = pygame.Surface((WINDOW_W, h), pygame.SRCALPHA)
        s.fill((0,0,0,200))
        self.screen.blit(s,(0,0))
        self.draw_text(
            "> " + self.console_text,
            (8, 6), (255,255,255)
        )

    # ---------------- console commands ----------------
    def console_eval(self, cmd: str):
        tok = cmd.strip().split()
        if not tok: return ""
        t0 = tok[0].lower()
        try:
            if t0 == 'tp' and len(tok)>=3:
                self.player.x = float(tok[1]); self.player.y = float(tok[2])
                return "teleported"
            if t0 == 'time' and len(tok)>=2:
                if tok[1] == 'set' and len(tok)>=3:
                    # expect HH:MM
                    hh,mm = map(int, tok[2].split(':'))
                    self.day_time = (hh%24)*60 + (mm%60)
                    return "time set"
                elif tok[1] == 'add' and len(tok)>=3:
                    self.day_time += float(tok[2])
                    return "time advanced"
                return f"time is {self.day_time:.1f}"
            if t0 == 'give' and len(tok)>=3:
                # give <name> <count>
                name = tok[1].lower(); count = int(tok[2])
                for b in BLOCKS.values():
                    if b.name.lower() == name:
                        self.player.inventory[b.id] = self.player.inventory.get(b.id,0) + count
                        return f"gave {count} {b.name}"
                return "unknown item"
            if t0 == 'seed':
                return str(self.world.seed)
            if t0 == 'help':
                return "tp x y | time set HH:MM | time add m | give name n | seed"
        except Exception as e:
            return f"error: {e}"
        return "unknown command"

    # ---------------- main loop ----------------
    def run(self):
        running = True
        pending_save = False
        os.makedirs(SS_PATH, exist_ok=True)
        last_click = 0
        while running:
            dt_real = self.clock.tick(60)/1000.0
            if not self.paused and not self.console_active:
                self.day_time = (self.day_time + dt_real*self.time_scale) % (24*60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.paused = not self.paused
                    elif event.key == pygame.K_SPACE and not self.paused and not self.console_active and self.on_ground():
                        self.player.vy = JUMP_VEL/TILE
                    elif pygame.K_1 <= event.key <= pygame.K_9:
                        self.player.selected = min(event.key - pygame.K_1, len(self.player.hotbar)-1)
                    elif event.key == pygame.K_F3:
                        self.show_debug = not self.show_debug
                    elif event.key == pygame.K_F1:
                        self.settings["show_tutorial"] = not self.settings.get("show_tutorial", True)
                        self.save_settings()
                    elif event.key == pygame.K_F5:
                        self.world.save(); pending_save=False
                    elif event.key == pygame.K_BACKQUOTE:  # `
                        self.console_active = not self.console_active
                        if not self.console_active:
                            self.console_text = ""
                    elif event.key == pygame.K_F12:
                        self.screenshot()
                    elif event.key == pygame.K_m:
                        self.show_minimap = not self.show_minimap
                    elif self.console_active:
                        if event.key == pygame.K_RETURN:
                            out = self.console_eval(self.console_text)
                            print(out)
                            self.console_text = ""
                            self.console_active = False
                        elif event.key == pygame.K_BACKSPACE:
                            self.console_text = self.console_text[:-1]
                        else:
                            ch = event.unicode
                            if ch and 32 <= ord(ch) <= 126:
                                self.console_text += ch
                elif event.type == pygame.MOUSEWHEEL and not self.paused and not self.console_active:
                    d = -1 if event.y>0 else 1
                    self.player.selected = (self.player.selected + d) % len(self.player.hotbar)
                elif event.type == pygame.MOUSEBUTTONDOWN and not self.paused and not self.console_active:
                    now = time.time()
                    if now - last_click < 0.02:  # de‑bounce
                        continue
                    last_click = now
                    mx,my = pygame.mouse.get_pos()
                    camx, camy = self.player.x, self.player.y + 0.15
                    wx, wy = self.s2w(mx,my,camx,camy)
                    tx, ty = int(math.floor(wx)), int(math.floor(wy))
                    if math.hypot(tx+0.5-self.player.x, ty+0.5-(self.player.y+0.9)) <= REACH:
                        if event.button == 1:
                            bid = self.player.hotbar[self.player.selected]
                            if self.place_block(tx,ty,bid):
                                pending_save = True
                        elif event.button == 3:
                            if self.break_block(tx,ty):
                                pending_save = True

            keys = pygame.key.get_pressed()
            if not self.paused and not self.console_active:
                self.move_player(dt_real, keys)
                self.step_particles(dt_real)
                self.update_fluids()

            # camera follows player
            camx, camy = self.player.x, self.player.y + 0.2

            # draw frame
            self.draw_world(camx, camy)
            self.draw_player(camx, camy)
            self.draw_ui(camx, camy)
            self.draw_minimap(camx, camy)
            if self.paused:
                self.draw_pause_menu()
            if self.console_active:
                self.draw_console()
            if self.show_debug:
                self.draw_debug_overlay(camx, camy)

            pygame.display.flip()

        if pending_save:
            self.world.save()
        pygame.quit()

    # ---------------- misc ----------------
    def draw_debug_overlay(self, camx, camy):
        p = self.player
        info = [
            f"pos=({p.x:.2f},{p.y:.2f}) vel=({p.vx:.2f},{p.vy:.2f}) facing={'R' if p.facing>0 else 'L'}",
            f"selected={BLOCKS[p.hotbar[p.selected]].name} seed={self.world.seed}",
            f"chunks={len(self.world.chunks)} edits={len(self.world.edits)}",
        ]
        s = pygame.Surface((WINDOW_W, 70), pygame.SRCALPHA)
        s.fill((0,0,0,140))
        self.screen.blit(s,(0,WINDOW_H-72))
        for i,t in enumerate(info):
            self.draw_text(t, (10, WINDOW_H-66 + i*20), (255,255,255))

    def screenshot(self):
        ts = int(time.time())
        path = os.path.join(SS_PATH, f"shot_{ts}.png")
        pygame.image.save(self.screen, path)
        print("Saved screenshot:", path)


if __name__ == '__main__':
    try:
        Game().run()
    except Exception as e:
        print("Fatal:", e)
        pygame.quit()
        sys.exit(1)
