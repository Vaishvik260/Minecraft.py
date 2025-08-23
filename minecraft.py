Python 3.13.6 (v3.13.6:4e665351082, Aug  6 2025, 11:22:35) [Clang 16.0.0 (clang-1600.0.26.6)] on darwin
Enter "help" below or click "Help" above for more information.
# mini_minecraft.py
# A tiny Minecraft-like sandbox written with Ursina.
# Features: WASD first-person movement, jump, place blocks (RMB), break blocks (LMB).
# Should work on Windows/Mac/Linux with Python 3.8–3.12 after: pip install ursina

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random

# --- App setup ---
app = Ursina()
window.title = 'Mini Minecraft (Python + Ursina)'
... window.borderless = False
... window.fullscreen = False
... window.exit_button.visible = False
... mouse.visible = False
... 
... # Choose a simple built-in texture to avoid external assets
... BLOCK_TEX = 'white_cube'  # built-in texture, always available
... 
... # --- Voxel (block) class ---
... class Voxel(Button):
...     def __init__(self, position=(0, 0, 0)):
...         super().__init__(
...             parent=scene,
...             position=position,
...             model='cube',
...             origin_y=0.5,
...             texture=BLOCK_TEX,
...             color=color.color(0, 0, random.uniform(0.9, 1.0)),
...             highlight_color=color.lime,
...             scale=1
...         )
... 
...     def input(self, key):
...         # Place/break only when the mouse is pointing at this block
...         if self.hovered:
...             if key == 'left mouse down':
...                 destroy(self)
...             if key == 'right mouse down':
...                 # Place a new block adjacent to the face you're pointing at
...                 Voxel(position=self.position + mouse.normal)
... 
... 
... # --- Create a simple flat world ---
... WORLD_SIZE = 20
... for z in range(WORLD_SIZE):
...     for x in range(WORLD_SIZE):
...         Voxel(position=(x, 0, z))
... 
... # --- Player, sky, and a soft light ---
... player = FirstPersonController(
...     y=2,
...     speed=6,
...     jump_height=1.2,
...     gravity=1.0
... )
... 
... Sky()  # built-in sky dome
... 
... sun = DirectionalLight()
... sun.look_at(Vec3(1, -1, -1))
... 
... # Simple crosshair
... crosshair = Entity(model='quad', color=color.black, parent=camera.ui, scale=0.008)
... 
... # HUD text
... hint = Text(
...     text='LMB: break | RMB: place | ESC: quit',
...     position=(-0.5, 0.45),
...     origin=(0, 0),
...     scale=1,
...     background=True,
... )
... 
... # Allow Escape to quit
... def input(key):
...     if key == 'escape':
...         application.quit()
... 
... 
... app.run()
... 
