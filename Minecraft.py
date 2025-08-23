Python 3.13.6 (v3.13.6:4e665351082, Aug  6 2025, 11:22:35) [Clang 16.0.0 (clang-1600.0.26.6)] on darwin
Enter "help" below or click "Help" above for more information.
# Mini "Minecraft"-like terminal sandbox
# No imports required. Run with: python3 minecraft_text.py

# ======= CONFIG =======
WORLD_W = 32
WORLD_H = 16

PLAYER = '@'
AIR     = ' '
DIRT    = '#'
STONE   = 'O'
WOOD    = 'W'
LEAVES  = 'L'
PLANK   = 'P'  # craftable from WOOD
CRAFT   = 'C'  # crafting table

# ======= PSEUDO RANDOM (no imports) =======
_seed = 123456789
def srand(seed):
    global _seed
    _seed = seed & 0x7fffffff

def rand():
    # simple linear congruential generator
    global _seed
    _seed = (1103515245 * _seed + 12345) & 0x7fffffff
    return _seed

def randrange(n):
    if n <= 0:
        return 0
    return rand() % n

# ======= WORLD =======
def make_world(seed=1):
    srand(seed or 1)
    w = [[AIR for _ in range(WORLD_W)] for __ in range(WORLD_H)]
    # Terrain height per column using wobble
    base = WORLD_H // 2 + 2
    height = base
    for x in range(WORLD_W):
        # change height slightly
        step = (randrange(3) - 1)  # -1,0,1
        height += step
        if height < WORLD_H//3: height = WORLD_H//3
        if height > WORLD_H-3: height = WORLD_H-3
        # fill ground: top dirt, deeper stone
        for y in range(height, WORLD_H):
            block = DIRT if y <= height+1 else (STONE if randrange(5) else DIRT)
            w[y][x] = block
        # sprinkle trees occasionally on surface
        if randrange(8) == 0:
            sy = height-1
            if sy>=3:
                # trunk
                w[sy][x] = WOOD
                if sy-1>=0: w[sy-1][x] = WOOD
                # leaves blob
                for dx in (-1,0,1):
                    for dy in (-3,-2,-1,0):
                        xx = x+dx
                        yy = sy+dy
                        if 0<=xx<WORLD_W and 0<=yy<WORLD_H and w[yy][xx]==AIR:
                            w[yy][xx] = LEAVES
    return w

# ======= RENDER =======
def clr():
    # ANSI clear
    print('\x1b[2J\x1b[H', end='')

def draw(world, px, py, inv, selected, tip=''):
    clr()
    top = '╔' + ('═'*WORLD_W) + '╗'
    bottom = '╚' + ('═'*WORLD_W) + '╝'
    print(top)
    for y in range(WORLD_H):
        row = world[y][:]
        if 0<=px<WORLD_W and 0<=py<WORLD_H and y==py:
            row = row[:]
            row[px] = PLAYER
        print('║' + ''.join(row) + '║')
    print(bottom)
    # HUD
    names = {AIR:'Air',DIRT:'Dirt',STONE:'Stone',WOOD:'Wood',LEAVES:'Leaves',PLANK:'Plank',CRAFT:'Craft'}
    hotbar = [DIRT, STONE, WOOD, PLANK, CRAFT]
    hb = []
    for i,b in enumerate(hotbar, start=1):
        mark = '*' if selected==b else ' '
        hb.append(f'[{i}:{names[b]} x{inv.get(b,0)}{mark}]')
    print(' '.join(hb))
    print("Controls: w/a/s/d move · mine · place · craft · inv · save · load · quit")
    if tip: print(tip)

# ======= GAME LOGIC =======
def find_spawn(world):
    # spawn at first empty above ground near middle
    x = WORLD_W//2
    for y in range(WORLD_H):
        if world[y][x]==AIR and world[y+1][x] in (DIRT,STONE,WOOD,LEAVES,PLANK,CRAFT):
            return x,y
    # fallback
    return x, WORLD_H//2

def clamp(v,a,b): 
    return a if v<a else b if v>b else v

def mine(world, x, y, inv):
    if 0<=x<WORLD_W and 0<=y<WORLD_H:
        b = world[y][x]
        if b!=AIR and b!=LEAVES: # leaves don't drop
            inv[b] = inv.get(b,0)+1
            world[y][x] = AIR
            return f"Mined {b}."
        elif b==LEAVES:
            world[y][x] = AIR
            return "Cleared leaves."
    return "Nothing to mine."

def place(world, x, y, inv, block):
    if block==AIR: return "Select a block first (1-5)."
    if inv.get(block,0)<=0: return f"Out of {block}."
    if 0<=x<WORLD_W and 0<=y<WORLD_H and world[y][x]==AIR:
        world[y][x] = block
        inv[block]-=1
        return f"Placed {block}."
    return "Can't place there."

def craft(inv):
    # simple recipes
    made = []
    # 2 wood -> 4 planks
    while inv.get(WOOD,0) >= 2:
        inv[WOOD]-=2
        inv[PLANK] = inv.get(PLANK,0)+4
        made.append("4 Planks")
        break
    # 4 stone -> 1 crafting table
    if inv.get(STONE,0) >= 4:
        inv[STONE]-=4
        inv[CRAFT] = inv.get(CRAFT,0)+1
        made.append("1 Craft Table")
    return "Crafted: " + (', '.join(made) if made else "nothing.")

def save(world, px, py, inv, seed):
    data = {
        'seed': seed,
        'px': px, 'py': py,
        'inv': inv,
        'world': [''.join(row) for row in world],
    }
    # serialize without imports
    text_lines = []
    text_lines.append(str(seed))
    text_lines.append(f"{px},{py}")
    # inventory
    items = []
    for k,v in inv.items():
        items.append(f"{k}:{v}")
    text_lines.append('|'.join(items))
    # world rows
    for r in data['world']:
        text_lines.append(r)
    with open('minecraft_save.txt','w', encoding='utf-8') as f:
        f.write('\n'.join(text_lines))
    return "Saved to minecraft_save.txt"

def load():
    try:
        with open('minecraft_save.txt','r', encoding='utf-8') as f:
            lines = [line.rstrip('\n') for line in f]
        seed = int(lines[0] or '1')
        coords = lines[1].split(',')
        px = int(coords[0]); py=int(coords[1])
        inv = {}
        for part in lines[2].split('|'):
            if not part: continue
            k,v = part.split(':')
            inv[k] = int(v)
        world_rows = lines[3:3+WORLD_H]
        world = [list(row.ljust(WORLD_W)[:WORLD_W]) for row in world_rows]
        return world, px, py, inv, seed, "Loaded save."
    except Exception as e:
        return None, None, None, None, None, "No save found or file corrupted."
    
def run():
...     print("Seed (press Enter for default): ", end='')
...     s = input().strip()
...     try:
...         seed = int(s) if s else 1
...     except:
...         seed = 1
...     world = make_world(seed)
...     px, py = find_spawn(world)
...     inv = {DIRT:3, WOOD:0, STONE:0, PLANK:0, CRAFT:0}
...     selected = DIRT
...     hotbar = [DIRT, STONE, WOOD, PLANK, CRAFT]
...     tip = "Welcome! Type commands like w, a, s, d, mine, place, craft, save, load, inv, quit."
...     while True:
...         # draw
...         draw(world, px, py, inv, selected, tip)
...         tip = ''
...         cmd = input("> ").strip().lower()
...         if not cmd: continue
...         if cmd in ('quit','exit','q'):
...             print("Goodbye!")
...             break
...         if cmd in ('w','a','s','d'):
...             dx = (1 if cmd=='d' else -1 if cmd=='a' else 0)
...             dy = (-1 if cmd=='w' else 1 if cmd=='s' else 0)
...             nx = clamp(px+dx,0,WORLD_W-1)
...             ny = clamp(py+dy,0,WORLD_H-1)
...             if world[ny][nx]==AIR:
...                 px,py = nx,ny
...             else:
...                 tip = "Bumped into a block."
...             continue
...         if cmd.startswith(('1','2','3','4','5')):
...             idx = ord(cmd[0])-ord('1')
...             if 0<=idx<len(hotbar):
...                 selected = hotbar[idx]
...                 tip = f"Selected {selected}."
...             continue
...         if cmd=='inv':
...             tip = "Inventory: " + ', '.join([f"{k}:{inv.get(k,0)}" for k in (DIRT,STONE,WOOD,PLANK,CRAFT)])
...             continue
...         if cmd=='mine':
...             # mine in front if possible else under feet
...             tx,ty = px,py+1
...             if 0<=ty<WORLD_H and world[ty][tx]!=AIR:
...                 tip = mine(world,tx,ty,inv)
...             else:
...                 tip = mine(world,px,py,inv)
...             continue
...         if cmd=='place':
...             # place under or at feet if air under, else in front
...             tx,ty = px,py+1
...             if not (0<=ty<WORLD_H and world[ty][tx]==AIR):
...                 tx,ty = px,py
...             tip = place(world,tx,ty,inv,selected)
...             continue
...         if cmd=='craft':
...             tip = craft(inv)
...             continue
...         if cmd=='save':
...             tip = save(world, px, py, inv, seed)
...             continue
...         if cmd=='load':
...             w, lx, ly, linv, lseed, tipmsg = load()
...             tip = tipmsg
...             if w:
...                 world, px, py, inv, seed = w, lx, ly, linv, lseed
...             continue
...         tip = "Unknown command."
...         
... if __name__=='__main__':
...     run()
