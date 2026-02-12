import bpy
import mathutils

from typing import Literal

from .data_struct import SwVec3, SwColor


IntTuple3 = tuple[int, int, int]
FloatTuple3 = tuple[float, float, float]
FloatTuple4 = tuple[float, float, float, float]
MeshTypeEnum = Literal['MESH', 'PHYS', 'ANIM']
NameModeEnum = Literal['MESH', 'OBJECT', 'MATERIAL', 'NONE']

GLASS_COLOR = SwColor(160, 160, 199, 128)
ADDITIVE_COLOR = SwColor(255, 255, 0, 255)
LAVA_COLOR = SwColor(149, 149, 149, 255)
OVERRIDE_COLOR_1 = SwColor(255, 125, 0, 255)
OVERRIDE_COLOR_2 = SwColor(155, 125, 0, 255)
OVERRIDE_COLOR_3 = SwColor(55, 125, 0, 255)


def to_blender_vec(v: SwVec3) -> FloatTuple3:
    return (v.x, v.z, v.y)


def to_blender_color(c: SwColor) -> FloatTuple4:
    return (c.r/255, c.g/255, c.b/255, c.a/255)


def from_blender_vec(v: mathutils.Vector) -> SwVec3:
    return SwVec3(v[0], v[2], v[1])


def from_blender_color(c: FloatTuple4) -> SwColor:
    r, g, b, a = (min(max(round(v * 255), 0), 255) for v in c)
    return SwColor(r, g, b, a)


def bsdf_base_color(material: bpy.types.Material):
    material.use_nodes = True
    node_tree = material.node_tree
    assert node_tree is not None
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node.inputs['Base Color']
