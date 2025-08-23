Python 3.13.6 (v3.13.6:4e665351082, Aug  6 2025, 11:22:35) [Clang 16.0.0 (clang-1600.0.26.6)] on darwin
Enter "help" below or click "Help" above for more information.
# TextCraft+ : a richer Minecraft-like terminal game (no imports)
# Run: python3 textcraft_plus.py

# ===== Constants =====
W = 64          # world width (columns)
H = 24          # world height (rows)
CHUNK = 16      # for terrain variety
PLAYER = '@'
AIR=' ' ; DIRT='#'; GRASS='='; STONE='O'; SAND='~'
COAL='c'; IRON='i'; GOLD='g'; DIAMOND='d'
WOOD='W'; LEAF='L'
PLANK='P'; STICK='|' ; TABLE='T'; FURN='F'; BED='B'; TORCH='*'
FIRE='^'  # furnace fire indicator (visual)
# Items (not blocks placed): APPLE, RAW_BEEF, COOKED_BEEF, INGOT_IRON, INGOT_GOLD, PICK_WOOD/STONE/IRON/DIAMOND
APPLE='apple'; BEEF='beef'; STEAK='steak'; ING_IRON='iron'; ING_GOLD='gold'
PICK_W='pickW'; PICK_S='pickS'; PICK_I='pickI'; PICK_D='pickD'

# ===== Tiny RNG (no imports) =====
_seed = 1337
def srand(s): 
    global _seed; _seed = s & 0x7fffffff
def rnd():
    global _seed; _seed = (1103515245*_seed+12345)&0x7fffffff; return _seed
def rrange(n): return 0 if n<=0 else rnd()%n

# ===== Utility =====
def clamp(v,a,b): return a if v<a else b if v>b else v

# ===== World Gen =====
def make_world(seed=1):
    srand(seed or 1)
    world = [[AIR for _ in range(W)] for __ in range(H)]
    height = H//2 + 2
    for x in range(W):
        # terrain wobble
        if x%CHUNK==0: height += (rrange(5)-2)
        height = clamp(height, H//3, H-4)
        # top block
        tb = GRASS if rrange(3) else SAND if rrange(20)==0 else GRASS
        for y in range(height, H):
            b = DIRT if y<=height+1 else STONE
            # ores
            if y>H*3//4 and rrange(25)==0: b = COAL
            if y>H*4//5 and rrange(40)==0: b = IRON
            if y>H*5//6 and rrange(65)==0: b = GOLD
            if y>H*9//10 and rrange(120)==0: b = DIAMOND
            world[y][x] = b
        # surface
        if height>0: world[height-1][x] = tb
        # trees
        if rrange(10)==0 and height-1>=3 and tb==GRASS:
            sy=height-2
            world[sy][x]=WOOD
            if sy-1>=0: world[sy-1][x]=WOOD
            for dx in (-1,0,1):
                for dy in (-3,-2,-1,0):
                    xx=x+dx; yy=sy+dy
                    if 0<=xx<W and 0<=yy<H and world[yy][xx]==AIR: world[yy][xx]=LEAF
        # caves
        if rrange(7)==0:
            cy = rrange(H-height)+height
            for dx in range(-2,3):
                xx=x+dx
                if 0<=xx<W:
                    for dy in range(-1,2):
                        yy=cy+dy
                        if height<=yy<H and world[yy][xx]!=AIR:
                            world[yy][xx]=AIR
    # scatter apples/beef as drops in leaves/ground
    drops=[]
    for x in range(W):
        for y in range(H):
            if world[y][x]==LEAF and rrange(30)==0:
                drops.append((x,y,APPLE,1))
            if y==H-1 and world[y][x] in (DIRT,GRASS) and rrange(60)==0:
                drops.append((x,y-1,BEEF,1))
    return world, drops

# ===== Player & Entities =====
def find_spawn(world):
    for y in range(H):
        if world[y][W//2]==AIR and world[y+1][W//2]!=AIR:
            return W//2, y
    return W//2, H//2

def block_solid(b): return b not in (AIR, LEAF, TORCH, FIRE)
def block_breakable(b): return b not in (AIR, FIRE)
def harvest_drop(b, tool):
    # returns (item/block, count, hardness_ticks)
    # hardness depends on tool tier
    tier = 0
    if tool in (PICK_W,): tier=1
    if tool in (PICK_S,): tier=2
    if tool in (PICK_I,): tier=3
    if tool in (PICK_D,): tier=4
    if b in (DIRT, GRASS, SAND, LEAF, WOOD, PLANK, TABLE, FURN, BED, TORCH): base=6
    elif b==COAL: base=16
    elif b==IRON: base=26
    elif b==GOLD: base=30
    elif b==DIAMOND: base=40
    else: base=22  # stone
    speed = 1 + tier
    time = max(2, base//speed)
    # drop item
    if b==GRASS: drop=DIRT
    elif b==COAL: drop=('coal',1)
    elif b==IRON: drop=('raw_iron',1)
    elif b==GOLD: drop=('raw_gold',1)
    elif b==DIAMOND: drop=('diamond',1)
    elif b==LEAF: drop=None
    else: drop=(b,1)
    return drop, time

def names(x):
    mapping = {
        AIR:'Air', DIRT:'Dirt', GRASS:'Grass', STONE:'Stone', SAND:'Sand',
        COAL:'Coal Ore', IRON:'Iron Ore', GOLD:'Gold Ore', DIAMOND:'Diamond Ore',
        WOOD:'Log', LEAF:'Leaves', PLANK:'Planks', TABLE:'Crafting Table',
        FURN:'Furnace', BED:'Bed', TORCH:'Torch',
        APPLE:'Apple', BEEF:'Raw Beef', STEAK:'Steak',
        ING_IRON:'Iron Ingot', ING_GOLD:'Gold Ingot',
        PICK_W:'Wood Pick', PICK_S:'Stone Pick', PICK_I:'Iron Pick', PICK_D:'Diamond Pick'
    }
    return mapping.get(x, str(x))

# ===== Rendering =====
def clear(): print('\x1b[2J\x1b[H', end='')
def draw(world, px, py, inv, hotbar, sel, health, hunger, daytick, mobs, drops, tip):
    clear()
    tcycle = (daytick//50)%24000  # fake MC ticks; day ~24000
    is_night = not (0<=tcycle<12000)
    top = '╔' + ('═'*W) + '╗'
    print(top)
    for y in range(H):
        row = world[y][:]
        # mobs
        for m in mobs:
            if m['y']==y and 0<=m['x']<W: row[m['x']] = 'Z' if m['type']=='zombie' else 'S'
        # drops (draw small •)
        for dx,dy,_,_ in drops:
            if dy==y and 0<=dx<W and row[dx]==AIR: row[dx]='·'
        if 0<=px<W and 0<=py<H and y==py:
            row[px]=PLAYER
        print('║' + ''.join(row) + '║')
    print('╚' + ('═'*W) + '╝')
    # HUD
    bar = ''.join(['♥' if i<health else '♡' for i in range(10)])
    food = ''.join(['🍗' if i<hunger else '·' for i in range(10)])
    time_label = 'Night' if is_night else 'Day'
    print(f"HP:{bar}  Food:{food}  Time:{time_label}  Tick:{tcycle}")
    hb=[]
    for i,b in enumerate(hotbar, start=1):
        if b is None: hb.append(f"[{i}: empty]")
        else:
            cnt = inv.get(b,0)
            mark='*' if sel==i-1 else ' '
            hb.append(f"[{i}:{names(b)} x{cnt}{mark}]")
    print(' '.join(hb))
    print("Commands: a/d, jump, mine, place, torch, craft <r>, smelt <item>, equip <tool>, eat, bed, look, inv, save, load, help, quit")
    if tip: print(tip)

# ===== Crafting & Smelting =====
RECIPES = {
    'planks': {WOOD:1},           # -> 4 planks
    'sticks': {PLANK:2},          # -> 4 sticks
    'table': {PLANK:4},           # -> 1 table
    'furnace': {STONE:8},         # -> 1 furnace
    'bed': {PLANK:3},             # -> 1 bed (wool hand-waved)
    'pick_wood': {PLANK:3, STICK:2},
    'pick_stone': {STONE:3, STICK:2},
    'pick_iron': {ING_IRON:3, STICK:2},
    'pick_diamond': { 'diamond':3, STICK:2},
    'torch': {'coal':1, STICK:1}
}
def craft(inv, recipe):
    r = recipe.lower()
    if r not in RECIPES: return "Unknown recipe."
    need = RECIPES[r]
    # check
    for k,v in need.items():
        if inv.get(k,0)<v: return "Not enough materials."
    for k,v in need.items(): inv[k]-=v
    # outputs
    if r=='planks': inv[PLANK]=inv.get(PLANK,0)+4; return "Crafted 4 Planks."
    if r=='sticks': inv[STICK]=inv.get(STICK,0)+4; return "Crafted 4 Sticks."
    if r=='table': inv[TABLE]=inv.get(TABLE,0)+1; return "Crafted Crafting Table."
    if r=='furnace': inv[FURN]=inv.get(FURN,0)+1; return "Crafted Furnace."
    if r=='bed': inv[BED]=inv.get(BED,0)+1; return "Crafted Bed."
    if r=='pick_wood': inv[PICK_W]=inv.get(PICK_W,0)+1; return "Crafted Wood Pick."
    if r=='pick_stone': inv[PICK_S]=inv.get(PICK_S,0)+1; return "Crafted Stone Pick."
    if r=='pick_iron': inv[PICK_I]=inv.get(PICK_I,0)+1; return "Crafted Iron Pick."
    if r=='pick_diamond': inv[PICK_D]=inv.get(PICK_D,0)+1; return "Crafted Diamond Pick."
    if r=='torch': inv[TORCH]=inv.get(TORCH,0)+4; return "Crafted 4 Torches."
    return "Crafted."

def smelt(inv, item):
    if item=='raw_iron' and inv.get('raw_iron',0)>0:
        inv['raw_iron']-=1; inv[ING_IRON]=inv.get(ING_IRON,0)+1; return "Smelted Iron Ingot."
    if item=='raw_gold' and inv.get('raw_gold',0)>0:
        inv['raw_gold']-=1; inv[ING_GOLD]=inv.get(ING_GOLD,0)+1; return "Smelted Gold Ingot."
    return "Nothing to smelt."

# ===== Game mechanics =====
def can_stand(world, x, y):
    # ensure player cell is air and above is not solid against head? (player height=1 in this 2D)
    return 0<=x<W and 0<=y<H and world[y][x]==AIR

def step_physics(world, px, py, vy, health, hunger, daytick, mobs, drops, lightmap):
    # gravity
    if py+1<H and not can_stand(world, px, py+1):
        # on ground
        vy = 0
    else:
        # falling
        if py+1<H and world[py+1][px]==AIR:
            py += 1
            vy += 1
    # starvation
    if hunger>=10 and daytick%80==0 and health<10: health+=1
    if hunger<=0 and daytick%80==0 and health>0: health-=1
    # mob AI (very simple)
    for m in mobs:
        if rnd()%2==0:
            m['x'] += -1 if m['x']>px else (1 if m['x']<px else 0)
            m['x']=clamp(m['x'],0,W-1)
        # attack if adjacent
        if abs(m['x']-px)<=1 and abs(m['y']-py)<=0:
            if daytick%20==0 and health>0: health-=1
    # drop pickup
    picked=[]
    for i,(dx,dy,it,cnt) in enumerate(drops):
        if abs(dx-px)<=0 and abs(dy-py)<=0:
            inv_gain = cnt
            picked.append(i)
    for idx in reversed(picked):
        it = drops[idx][2]; cnt=drops[idx][3]
        drops.pop(idx)
        # add to global inventory later in loop (handled by caller)
    return px, py, vy, health, hunger

def light_level_at(world, x, y, torches):
    # very simple: base daylight, minus depth, plus torches nearby
    base = 8
    if y>H//2: base = 6
    if y>H*3//4: base = 4
    # night penalty
    base -= 5
    for tx,ty in torches:
        if abs(tx-x)+abs(ty-y)<=4: base += 6
    return clamp(base, 0, 15)

def spawn_mobs(world, daytick, mobs, px, py, torches):
    tcycle = (daytick//50)%24000
    is_night = not (0<=tcycle<12000)
    if not is_night: return
    if len(mobs)>8: return
    if rnd()%5!=0: return
    for _ in range(3):
        x = rrange(W)
        # find ground spot far from player
        for y in range(H-2):
            pass
        y = H-2
        if abs(x-px)<8: continue
        if world[y][x]!=AIR and world[y-1][x]==AIR:
            # light check (no torches nearby)
            lit = 0
            for tx,ty in torches:
                if abs(tx-x)+abs(ty-y)<=4: lit+=1
            if lit==0:
                mobs.append({'type':'zombie' if rnd()%2==0 else 'spider','x':x,'y':y})

# ===== Save/Load =====
def save_game(world, px, py, inv, hotbar, sel, health, hunger, daytick, mobs, torches, seed):
    lines=[]
    lines.append(str(seed))
    lines.append(f"{px},{py},{sel},{health},{hunger},{daytick}")
    # inv
    lines.append('|'.join([f"{k}:{inv.get(k,0)}" for k in inv if inv.get(k,0)>0]))
    # hotbar
    lines.append('|'.join([str(h) if h is not None else '.' for h in hotbar]))
    # torches
    lines.append('|'.join([f"{x},{y}" for (x,y) in torches]))
    # mobs
    lines.append('|'.join([f"{m['type']},{m['x']},{m['y']}" for m in mobs]))
    # world
    for y in range(H):
        lines.append(''.join(world[y]))
    with open('textcraft_save.txt','w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return "Saved."

def load_game():
    try:
        with open('textcraft_save.txt','r',encoding='utf-8') as f:
            L=[l.rstrip('\n') for l in f]
        seed=int(L[0]); p= L[1].split(','); px=int(p[0]); py=int(p[1]); sel=int(p[2]); health=int(p[3]); hunger=int(p[4]); daytick=int(p[5])
        inv={}
        if L[2]:
            for part in L[2].split('|'):
                k,v=part.split(':'); inv[k]=int(v)
        hb=[]
        if L[3]:
            for t in L[3].split('|'):
                hb.append(None if t=='.' else t)
        torches=[]
        if L[4]:
            for t in L[4].split('|'):
                x,y=t.split(','); torches.append((int(x),int(y)))
        mobs=[]
        if L[5]:
            for t in L[5].split('|'):
                typ,x,y=t.split(','); mobs.append({'type':typ,'x':int(x),'y':int(y)})
        world=[]
        rows=L[6:6+H]
        for r in rows:
            world.append(list(r.ljust(W)[:W]))
        return world, px, py, inv, hb, sel, health, hunger, daytick, mobs, torches, seed, "Loaded."
    except:
        return None,None,None,None,None,None,None,None,None,None,None,None,"No save found."

# ===== Game Loop =====
def run():
    print("Seed (Enter=default): ", end=''); s=input().strip()
    try: seed=int(s) if s else 1
    except: seed=1
    world, drops = make_world(seed)
    px,py = find_spawn(world)
    vy=0
    inv = {DIRT:5, PLANK:0, STICK:0, TABLE:0, FURN:0, BED:0, TORCH:0,
           APPLE:1, BEEF:0, STEAK:0,
           'coal':0, 'raw_iron':0, 'raw_gold':0, ING_IRON:0, ING_GOLD:0, 'diamond':0,
           PICK_W:1, PICK_S:0, PICK_I:0, PICK_D:0}
    tool_dur = {PICK_W:60, PICK_S:132, PICK_I:251, PICK_D:1561}
    equipped = PICK_W
    hotbar = [DIRT, STONE, PLANK, TORCH, TABLE, FURN, BED, None, None]
    sel=0
    health=10; hunger=4
    daytick=0
    mobs=[]
    torches=set()
    tip="Welcome to TextCraft+. Type 'help' for recipes and tips."
    mining = {'time':0,'target':None,'tx':None,'ty':None}
    # game
    while True:
        # draw
        draw(world, px, py, inv, hotbar, sel, health, hunger, daytick, mobs, drops, tip)
        tip=""
        if health<=0:
            print("You died. Game over.")
            break
        # spawn
        spawn_mobs(world, daytick, mobs, px, py, torches)
        # input
        cmd=input("> ").strip().lower()
        # time advances on any input (simplified)
        daytick+=50
        # passive hunger drain
        if daytick%200==0 and hunger<10: hunger+=1
        # process commands
        if cmd in ('quit','q','exit'): print("Bye!"); break
        if cmd=='help':
            tip=("Craft: planks, sticks, table, furnace, bed, pick_wood, pick_stone, pick_iron, pick_diamond, torch | "
                 "Use: a/d move, jump, mine, place, torch, equip <tool>, craft <r>, smelt <item>, eat, bed, save, load")
            continue
        if cmd in ('a','d'):
            dx = -1 if cmd=='a' else 1
            nx = clamp(px+dx,0,W-1)
            if can_stand(world,nx,py): px=nx
            else: tip="Blocked."
        elif cmd=='jump':
            if py+1<H and not can_stand(world,px,py+1):
                # on ground -> jump
                if py-1>=0 and can_stand(world,px,py-1): py-=1
        elif cmd=='mine':
            tx,ty=px,py+1
            # if air below, mine in front
            if ty<H and world[ty][tx]==AIR:
                tx=px; ty=py
            if 0<=ty<H and 0<=tx<W and block_breakable(world[ty][tx]):
                drop, need = harvest_drop(world[ty][tx], equipped)
                mining={'time':need,'target':drop,'tx':tx,'ty':ty}
                tip=f"Mining {names(world[ty][tx])}… ({need} ticks)"
            else:
                tip="Nothing to mine."
        elif cmd=='place':
            block = hotbar[sel]
            if block is None: tip="Hotbar slot empty."
            elif inv.get(block,0)<=0: tip=f"No {names(block)} left."
            else:
                tx,ty=px,py
                if world[ty][tx]==AIR:
                    world[ty][tx]=block
                    inv[block]-=1
                    tip=f"Placed {names(block)}."
                    if block==TORCH: torches.add((tx,ty))
                else:
                    tip="Can't place here."
        elif cmd.startswith(tuple(str(i) for i in range(1,10))):
            idx=int(cmd[0])-1
            sel=idx
            tip=f"Selected slot {idx+1}."
        elif cmd.startswith('equip'):
            parts=cmd.split()
            if len(parts)<2: tip="equip <tool>"
            else:
                tname=parts[1]
                lookup={'wood':PICK_W,'stone':PICK_S,'iron':PICK_I,'diamond':PICK_D}
                if tname in lookup and inv.get(lookup[tname],0)>0:
                    equipped=lookup[tname]; tip=f"Equipped {names(equipped)}."
                else:
                    tip="You don't have that pick."
        elif cmd.startswith('craft'):
            parts=cmd.split()
            if len(parts)<2: tip="craft <recipe>"
            else:
                tip = craft(inv, parts[1])
        elif cmd.startswith('smelt'):
            parts=cmd.split()
            if len(parts)<2: tip="smelt <raw_iron|raw_gold>"
...             else:
...                 tip = smelt(inv, parts[1])
...         elif cmd=='torch':
...             if inv.get(TORCH,0)>0:
...                 if world[py][px]==AIR:
...                     world[py][px]=TORCH; inv[TORCH]-=1; torches.add((px,py)); tip="Torch placed."
...                 else: tip="No space for torch."
...             else: tip="No torches."
...         elif cmd=='eat':
...             if inv.get(APPLE,0)>0:
...                 inv[APPLE]-=1; hunger=max(0,hunger-3); tip="Ate apple."
...             elif inv.get(STEAK,0)>0:
...                 inv[STEAK]-=1; hunger=max(0,hunger-6); tip="Ate steak."
...             else: tip="No food."
...         elif cmd=='bed':
...             # skip night and heal a bit if bed in hotbar or placed at feet
...             has_bed = inv.get(BED,0)>0 or world[py][px]==BED
...             if has_bed:
...                 daytick += 24000
...                 health=min(10,health+3)
...                 tip="You slept till morning."
...             else:
...                 tip="You need a bed (craft or place it)."
...         elif cmd=='inv':
...             tip = "Inventory: " + ', '.join([f"{names(k)}:{v}" for k,v in inv.items() if v>0])
...         elif cmd=='look':
...             under = world[py+1][px] if py+1<H else AIR
...             tip = f"Underfoot: {names(under)}."
...         elif cmd=='save':
...             tip = save_game(world, px, py, inv, hotbar, sel, health, hunger, daytick, mobs, torches, seed)
...         elif cmd=='load':
...             w, lpx, lpy, linv, lhb, lsel, lhp, lhun, lday, lmobs, ltor, lseed, msg = load_game()
...             tip = msg
...             if w:
...                 world, px, py, inv, hotbar, sel, health, hunger, daytick, mobs, torches, seed = \
...                     w, lpx, lpy, linv, lhb, lsel, lhp, lhun, lday, lmobs, set(ltor), lseed
...         else:
...             tip="Unknown command."
...         # handle mining progress
...         if mining['time']>0:
...             mining['time']-=1
...             if mining['time']==0 and mining['tx'] is not None:
...                 tx,ty= mining['tx'], mining['ty']
...                 target = mining['target']
...                 b = world[ty][tx]
...                 world[ty][tx]=AIR
...                 # tool wear
...                 if equipped in tool_dur:
...                     tool_dur[equipped]-=1
...                     if tool_dur[equipped]<=0:
...                         inv[equipped]-=1
...                         tool_dur[equipped]=0
...                         tip += " Your tool broke!"
...                         if inv.get(equipped,0)==0:
...                             # fallback equip wood pick if available
...                             if inv.get(PICK_W,0)>0: equipped=PICK_W
...                 # drop item
...                 if target:
...                     if isinstance(target, tuple):
...                         it,cnt=target
...                         inv[it]=inv.get(it,0)+cnt
...                     else:
...                         it,cnt=target,1
...                         inv[it]=inv.get(it,0)+cnt
...         # physics & AI
...         px,py,vy,health,hunger = step_physics(world, px, py, vy, health, hunger, daytick, mobs, drops, None)
...         # trivial fall damage check (if fell more than 3 in a tick -> damage)
...         # (Simplified: not tracking height; omitted for brevity)
... 
... if __name__=='__main__':
...     run()
