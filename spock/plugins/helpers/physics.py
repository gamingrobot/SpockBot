"""
PhysicsPlugin is planned to provide vectors and tracking necessary to implement
SMP-compliant client-side physics for entities. Primarirly this will be used to
keep update client position for gravity/knockback/water-flow etc. But it should
also eventually provide functions to track other entities affected by SMP
physics

Minecraft client/player physics is unfortunately very poorly documented.
Most of these values are based of experimental results and the contributions of
a handful of people (Thank you 0pteron!) to the Minecraft wiki talk page on
Entities and Transportation. Ideally someone will decompile the client with MCP
and document the totally correct values and behaviors.
"""

# Gravitational constants defined in blocks/(client tick)^2
PLAYER_ENTITY_GAV = 0.08
THROWN_ENTITY_GAV = 0.03
RIDING_ENTITY_GAV = 0.04
BLOCK_ENTITY_GAV = 0.04
ARROW_ENTITY_GAV = 0.05

# Air drag constants defined in 1/tick
PLAYER_ENTITY_DRG = 0.02
THROWN_ENTITY_DRG = 0.01
RIDING_ENTITY_DRG = 0.05
BLOCK_ENTITY_DRG = 0.02
ARROW_ENTITY_DRG = 0.01

# Player ground acceleration isn't actually linear, but we're going to pretend
# that it is. Max ground velocity for a walking client is 0.215blocks/tick, it
# takes a dozen or so ticks to get close to max velocity. Sprint is 0.28, just
# apply more acceleration to reach a higher max ground velocity
PLAYER_WLK_ACC = 0.15
PLAYER_SPR_ACC = 0.20
PLAYER_GND_DRG = 0.41

# Seems about right, not based on anything
PLAYER_JMP_ACC = 0.45
PLAYER_VCOL_OFFSET = 1.80
PLAYER_HCOL_OFFSET = 0.4

import logging
import math

from spock.mcmap import mapdata
from spock.plugins.base import PluginBase
from spock.utils import BoundingBox, Position, pl_announce
from spock.vector import Vector3

logger = logging.getLogger('spock')


class PhysicsCore(object):
    def __init__(self, vec, pos):
        self.vec = vec
        self.pos = pos

    def jump(self):
        if self.pos.on_ground:
            self.pos.on_ground = False
            self.vec.y += PLAYER_JMP_ACC

    def walk(self, angle, radians=False):
        if self.pos.on_ground:
            angle = angle if radians else math.radians(angle)
            z = math.cos(angle) * PLAYER_WLK_ACC
            x = math.sin(angle) * PLAYER_WLK_ACC
            self.vec.z += z
            self.vec.x += x

    def sprint(self, angle, radians=False):
        if self.pos.on_ground:
            angle = angle if radians else math.radians(angle)
            z = math.cos(angle) * PLAYER_SPR_ACC
            x = math.sin(angle) * PLAYER_SPR_ACC
            self.vec.z += z
            self.vec.x += x


@pl_announce('Physics')
class PhysicsPlugin(PluginBase):
    requires = ('Event', 'ClientInfo', 'World')
    events = {
        'physics_tick': 'tick',
    }

    def __init__(self, ploader, settings):
        super(PhysicsPlugin, self).__init__(ploader, settings)
        self.vec = Vector3(0.0, 0.0, 0.0)
        # wiki says 0.6 but I made it 0.8 to give a little wiggle room
        self.playerbb = BoundingBox(0.8, 1.8)
        self.pos = self.clientinfo.position
        ploader.provides('Physics', PhysicsCore(self.vec, self.pos))

    def tick(self, _, __):
        flags = self.do_work()
        self.apply_horizontal_drag()
        self.apply_vector()
        for flag in flags:
            self.event.emit(*flag)

    def gen_block_position(self, pb):
        x = math.floor(pb.x)
        y = math.ceil(pb.y)
        z = math.floor(pb.z)
        return Position(x, y, z)

    def do_work(self):
        #print('pos at b', str(self.pos))
        ret = []
        col = self.check_collision(self.pos)
        if 'y_down' in col:
            self.pos.on_ground = True
            self.vec.y = 0
            self.pos.y = col['y_down'].y+1
            #print('I am on the ground at', self.pos)
        else:
            self.pos.on_ground = False
            self.vec.y -= PLAYER_ENTITY_GAV
            self.apply_vertical_drag()
            #print('I am in the air at', self.pos)
        a = math.ceil(max(abs(self.vec.x), abs(self.vec.y), abs(self.vec.z)))
        #print('pos at c', str(self.pos))
        if a:
            y_up_col = False
            y_down_col = False
            x_col = False
            z_col = False
            for i in range(1, a+1):
                temp_x = (float(i)/a)*self.vec.x + self.pos.x
                temp_y = (float(i)/a)*self.vec.y + self.pos.y
                temp_z = (float(i)/a)*self.vec.z + self.pos.z
                pb = Position(temp_x, temp_y, temp_z)
                #print('Checking pb:', str(pb))
                col = self.check_collision(pb)
                if 'y_up' in col and not y_up_col:
                    y_up_col = True
                    self.vec.y = 0
                    self.pos.y = col['y_up'].y - PLAYER_VCOL_OFFSET
                if 'y_down' in col and not y_down_col and not self.pos.on_ground:
                    #print('I have collided with the ground')
                    y_down_col = True
                    self.pos.on_ground = True
                    self.vec.y = 0
                    self.pos.y = col['y_down'].y + 1
                if 'x' in col and not x_col:
                    x_col = True
                    self.vec.x = 0
                    if col['x'].x < self.pos.x:
                        self.pos.x = math.floor(self.pos.x) + PLAYER_HCOL_OFFSET
                    else:
                        self.pos.x = col['x'].x - PLAYER_HCOL_OFFSET
                if 'z' in col and not z_col:
                    z_col = True
                    self.vec.z = 0
                    if col['z'].z < self.pos.z:
                        self.pos.z = math.floor(self.pos.z) + PLAYER_HCOL_OFFSET
                    else:
                        self.pos.z = col['z'].z - PLAYER_HCOL_OFFSET
        #print('pos at f', str(self.pos))
        return ret

    def check_collision(self, pb):
        ret = {}
        cb = self.gen_block_position(pb)
        #print('Checking in block', str(cb))
        if self.block_collision(pb, cb, y=2):  # we check +2 because above my head
            ret['y_up'] = Position(cb.x, cb.y+2, cb.z)
        if self.block_collision(pb, cb, y=-1):  # we check below feet
            ret['y_down'] = Position(cb.x, cb.y-1, cb.z)
        # feet or head collide with x
        for x in (-1, 1):
            for y in (0, 1):
                if self.block_collision(pb, cb, x=x, y=y):
                    ret['x'] = Position(cb.x+x, cb.y+y, cb.z)
        # feet or head collide with z
        for z in (-1, 1):
            for y in (0, 1):
                if self.block_collision(pb, cb, y=y, z=z):
                    ret['z'] = Position(cb.x, cb.y+y, cb.z+z)
        return ret

    def block_collision(self, pb, cb, x=0, y=0, z=0):
        block_id, meta = self.world.get_block(cb.x + x, cb.y + y, cb.z + z)
        block = mapdata.get_block(block_id, meta)
        if block is None:
            return False
        # possibly we want to use the centers of blocks as the starting
        # points for bounding boxes instead of 0,0,0 this might make thinks
        # easier when we get to more complex shapes that are in the center
        # of a block aka fences but more complicated for the player

        # uncenter the player position
        pos1 = Position(pb.x - self.playerbb.w / 2, pb.y,
                        pb.z - self.playerbb.d / 2)
        bb1 = self.playerbb
        bb2 = block.bounding_box
        if bb2 is not None:
            pos2 = Position(cb.x + x + bb2.x, cb.y + y + bb2.y,
                            cb.z + z + bb2.z)
            if ((pos1.x + bb1.w) >= (pos2.x) and (pos1.x) <= (
                    pos2.x + bb2.w)) and (
                (pos1.y + bb1.h) >= (pos2.y) and (pos1.y) <= (
                    pos2.y + bb2.h)) and (
                (pos1.z + bb1.d) >= (pos2.z) and (pos1.z) <= (
                    pos2.z + bb2.d)):
                return True
        return False

    def apply_vertical_drag(self):
        self.vec.y -= self.vec.y * PLAYER_ENTITY_DRG

    def apply_horizontal_drag(self):
        self.vec.x -= self.vec.x * PLAYER_GND_DRG
        self.vec.z -= self.vec.z * PLAYER_GND_DRG

    def apply_vector(self):
        p = self.pos
        #print('I am at', str(self.pos))
        #print('My vector is', str(self.vec))
        p.x = p.x + self.vec.x
        p.y = p.y + self.vec.y
        p.z = p.z + self.vec.z
