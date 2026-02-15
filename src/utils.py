import bpy
import mathutils

from typing import Literal

from .data_struct import SwVec3, SwQuaternion, SwMatrix3, SwColor


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


def to_blender_vec(v: SwVec3):
    return mathutils.Vector((v.x, v.z, v.y))


def to_blender_quaternion(q: SwQuaternion):
    return mathutils.Quaternion((q.w, q.x, q.z, q.y)).conjugated()


def to_blender_rotation_matrix(r: SwMatrix3):
    return mathutils.Matrix([
        [r.m[0], r.m[6], r.m[3]],
        [r.m[2], r.m[8], r.m[5]],
        [r.m[1], r.m[7], r.m[4]]
    ])


def to_blender_transform_matrix(r: SwMatrix3, t: SwVec3):
    return mathutils.Matrix.LocRotScale(
        to_blender_vec(t),
        to_blender_rotation_matrix(r),
        None
    )


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


def validate_connected_tree(nodes: dict[int, tuple[int, list[int]]]) -> tuple[bool, str | None]:
    n = len(nodes)
    root_candidates = [node_id for node_id, node in nodes.items() if node[0] == -1]
    if len(root_candidates) != 1:
        return (False, 'multiple roots')

    root_id = root_candidates[0]

    edge_count = 0
    for node_id, node in nodes.items():
        edge_count += len(node[1])
        for child_id in node[1]:
            if child_id not in nodes:
                return (False, 'reference to nonexistent node')
            if nodes[child_id][0] != node_id:
                return (False, 'inconsistent parent-child relationships')

    if edge_count != n - 1:
        return (False, 'not a tree')

    visited = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        if current in visited:
            return (False, 'not a tree')
        visited.add(current)
        stack.extend(nodes[current][1])

    if len(visited) != n:
        return (False, 'not connected')

    return (True, None)
