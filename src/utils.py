import bpy
import mathutils

from typing import Literal

from .mesh_struct import MeshVec3, MeshColor4


IntTuple3 = tuple[int, int, int]
FloatTuple3 = tuple[float, float, float]
FloatTuple4 = tuple[float, float, float, float]
MeshTypeEnum = Literal['MESH', 'PHYS']
NameModeEnum = Literal['MESH', 'OBJECT', 'MATERIAL', 'NONE']

GLASS_COLOR = MeshColor4(160, 160, 199, 128)
ADDITIVE_COLOR = MeshColor4(255, 255, 0, 255)
LAVA_COLOR = MeshColor4(149, 149, 149, 255)
OVERRIDE_COLOR_1 = MeshColor4(255, 125, 0, 255)
OVERRIDE_COLOR_2 = MeshColor4(155, 125, 0, 255)
OVERRIDE_COLOR_3 = MeshColor4(55, 125, 0, 255)


def to_blender_vec(v: MeshVec3) -> FloatTuple3:
    return (v.x, v.z, v.y)


def to_blender_color(c: MeshColor4) -> FloatTuple4:
    return (c.r/255, c.g/255, c.b/255, c.a/255)


def from_blender_vec(v: mathutils.Vector) -> MeshVec3:
    return MeshVec3(v[0], v[2], v[1])


def from_blender_color(c: FloatTuple4) -> MeshColor4:
    r, g, b, a = (min(max(round(v * 255), 0), 255) for v in c)
    return MeshColor4(r, g, b, a)


def bsdf_base_color(material: bpy.types.Material):
    material.use_nodes = True
    node_tree = material.node_tree
    assert node_tree is not None
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node.inputs['Base Color']
