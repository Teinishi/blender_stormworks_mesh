from pathlib import Path
from typing import Iterable, Sequence

import bpy

from .data_struct import SwColor, MeshVertex, Mesh, PhysicsMesh, AnimVertex, Anim
from .utils import *


def _create_mesh_object(obj_name: str, mesh_name: str, collection: bpy.types.Collection, vertices: list[FloatTuple3] | list[mathutils.Vector], triangles: list[IntTuple3], vertex_colors: list[FloatTuple4] | None = None, matrix=None):
    mesh = bpy.data.meshes.new(mesh_name)
    obj = bpy.data.objects.new(obj_name, mesh)
    collection.objects.link(obj)
    mesh.from_pydata(vertices, [], triangles) # type: ignore
    mesh.update()

    if vertex_colors is not None:
        color_layer = mesh.color_attributes.new(name='Col', type='BYTE_COLOR', domain='CORNER')
        for polygon in mesh.polygons:
            for loop_index in polygon.loop_indices:
                vert_index = mesh.loops[loop_index].vertex_index
                color_layer.data[loop_index].color = vertex_colors[vert_index] # type: ignore

    if matrix is not None:
        obj.matrix_world = matrix @ obj.matrix_world
    return obj, mesh


def _create_material(name: str, color: SwColor):
    color_tuple = to_blender_color(color)

    material = bpy.data.materials.new(name)
    material.diffuse_color = color_tuple
    base_color = bsdf_base_color(material)
    if base_color:
        base_color.default_value = color_tuple # type: ignore

    return material


def _get_material(name: str, color: SwColor):
    material = bpy.data.materials.get(name)
    if material is None:
        material = _create_material(name, color)
    return material


class _ObjectMaterialBuilder:
    name: str
    materials: list[bpy.types.Material]
    glass_index: int | None = None
    additive_index: int | None = None
    lava_index: int | None = None
    override1_index: int | None = None
    override2_index: int | None = None
    override3_index: int | None = None
    color_indices: dict[SwColor, int]
    vertices: list[mathutils.Vector]
    triangles: list[IntTuple3]
    polygon_material: list[int]

    def __init__(self, name: str) -> None:
        self.name = name
        self.materials = []
        self.color_indices = {}
        self.vertices = []
        self.triangles = []
        self.polygon_material = []

    def add_submesh(self, shader_id: int, vertices: list[MeshVertex] | list[AnimVertex], indices: list[int]):
        if len(indices) % 3 != 0:
            raise Exception(f'Length of indices must be multiple of 3; {len(indices)} given')

        i_offset = len(self.vertices)

        self.vertices += [to_blender_vec(v.position) for v in vertices]
        for i in range(0, len(indices), 3):
            self.triangles.append((i_offset + indices[i], i_offset + indices[i + 1], i_offset + indices[i + 2]))

        n_triangles = len(indices) // 3

        if shader_id == 1:
            if self.glass_index is None:
                self.glass_index = len(self.materials)
                self.materials.append(_get_material('MATERIALglass', vertices[0].color))
            self.polygon_material += [self.glass_index] * n_triangles

        elif shader_id == 2:
            if self.additive_index is None:
                self.additive_index = len(self.materials)
                self.materials.append(_get_material('MATERIALadditive', vertices[0].color))
            self.polygon_material += [self.additive_index] * n_triangles

        elif shader_id == 3:
            if self.lava_index is None:
                self.lava_index = len(self.materials)
                self.materials.append(_get_material('MATERIALlava', vertices[0].color))
            self.polygon_material += [self.lava_index] * n_triangles

        else:
            for i in range(n_triangles):
                color = vertices[indices[3 * i]].color

                if color == OVERRIDE_COLOR_1:
                    if self.override1_index is None:
                        self.override1_index = len(self.materials)
                        self.materials.append(_get_material('OverrideColor1', color))
                    self.polygon_material.append(self.override1_index)

                elif color == OVERRIDE_COLOR_2:
                    if self.override2_index is None:
                        self.override2_index = len(self.materials)
                        self.materials.append(_get_material('OverrideColor2', color))
                    self.polygon_material.append(self.override2_index)

                elif color == OVERRIDE_COLOR_3:
                    if self.override3_index is None:
                        self.override3_index = len(self.materials)
                        self.materials.append(_get_material('OverrideColor3', color))
                    self.polygon_material.append(self.override3_index)

                elif color in self.color_indices:
                    self.polygon_material.append(self.color_indices[color])

                else:
                    next_index = len(self.materials)
                    self.color_indices[color] = next_index
                    self.polygon_material.append(next_index)
                    self.materials.append(_create_material(f'{self.name}_{len(self.color_indices):02}', color))

    def finalize(self, collection: bpy.types.Collection):
        obj, mesh = _create_mesh_object(self.name, self.name, collection, self.vertices, self.triangles)
        for m in self.materials:
            mesh.materials.append(m)

        for m, polygon in zip(self.polygon_material, mesh.polygons):
            polygon.material_index = m

        return (obj, mesh)


def _resolve_bone_matrices(bone_parent_indices: list[int], local_matrices: list[mathutils.Matrix]):
    resolved: dict[int, mathutils.Matrix] = {}
    q = list(range(len(bone_parent_indices)))
    while len(q) > 0:
        i = q.pop(0)
        p = bone_parent_indices[i]
        m = local_matrices[i]
        if p == -1:
            resolved[i] = m
        elif p in resolved:
            resolved[i] = resolved[p] @ local_matrices[i]
        else:
            q.append(i)
    return resolved


def _set_timestamp(timestamp: int):
    if bpy.context.scene is None:
        raise Exception('Unexpected error')
    t_start = bpy.context.scene.frame_start
    t_end = bpy.context.scene.frame_end
    bpy.context.scene.frame_set(round(t_start + (timestamp / 65535) * (t_end - t_start)))


def load_mesh(file, collection: bpy.types.Collection, name: str, strict_mode=True):
    with open(file, 'rb') as f:
        mesh_data = Mesh.from_reader(f, strict=strict_mode)

    obj_builder = _ObjectMaterialBuilder(name)

    for i, submesh in enumerate(mesh_data.submeshes):
        i = submesh.index_buffer_start
        j = i + submesh.index_buffer_length
        indices = mesh_data.indices[i:j]
        if len(indices) == 0:
            continue

        local_vertex_indices = sorted(set(indices))
        index_map = {k: i for i, k in enumerate(local_vertex_indices)}

        vertices = [mesh_data.vertices[i] for i in local_vertex_indices]
        mapped_indices = [index_map[i] for i in indices]

        obj_builder.add_submesh(submesh.shader_id, vertices, mapped_indices)

    obj_builder.finalize(collection)


def load_phys(file, collection: bpy.types.Collection, name: str, strict_mode=True):
    with open(file, 'rb') as f:
        phys_mesh_data = PhysicsMesh.from_reader(f, strict=strict_mode)

    for i, sub_phys in enumerate(phys_mesh_data.sub_phys_meshes):
        if len(phys_mesh_data.sub_phys_meshes) == 1:
            sub_phys_name = name
        else:
            sub_phys_name = f'{name}_{i:02}'

        triangles = [(i - 2, i - 1, i) for i in range(2, len(sub_phys.vertices), 3)]
        _create_mesh_object(sub_phys_name, sub_phys_name, collection, [to_blender_vec(v) for v in sub_phys.vertices], triangles)


def load_anim(file, collection: bpy.types.Collection, name: str, strict_mode=True):
    with open(file, 'rb') as f:
        anim_data = Anim.from_reader(f, strict=strict_mode)

    # ボーンの構造をチェック
    is_valid, msg = validate_connected_tree({i: (b.parent_index, b.child_indices) for i, b in enumerate(anim_data.bones)})
    if not is_valid:
        raise Exception(f'Invalid bone structure: {msg}')

    # メッシュのインポート
    obj_builder = _ObjectMaterialBuilder(f'{name}_mesh')
    for anim_mesh in anim_data.meshes:
        obj_builder.add_submesh(anim_mesh.shader_id, anim_mesh.vertices, anim_mesh.indices)
    mesh_obj, mesh = obj_builder.finalize(collection)

    # アーマチュアを作成
    arm_data = bpy.data.armatures.new(name)
    arm_obj = bpy.data.objects.new(name, arm_data)

    mesh_obj.parent = arm_obj
    has_armature = any(m.type == 'ARMATURE' for m in mesh_obj.modifiers)
    if not has_armature:
        mod = mesh_obj.modifiers.new(name='Armature', type='ARMATURE')
        mod.object = arm_obj # type: ignore

    collection.objects.link(arm_obj)

    # 編集モードに入る
    if bpy.context.view_layer is None:
        raise Exception('Unexpected error: bpy.context.view_layer is None')
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')

    # ボーンを作成
    bone_parent_indices = [b.parent_index for b in anim_data.bones]
    bone_matrices = _resolve_bone_matrices(bone_parent_indices, [to_blender_transform_matrix(b.rotation, b.translation) for b in anim_data.bones])
    edit_bones: list[bpy.types.EditBone] = []
    vertex_groups: list[bpy.types.VertexGroup] = []
    for i, b in enumerate(anim_data.bones):
        eb = arm_data.edit_bones.new(b.name)
        edit_bones.append(eb)

        vg = mesh_obj.vertex_groups.new(name=b.name)
        vertex_groups.append(vg)

        eb.matrix = bone_matrices[i]

    for b, eb in zip(anim_data.bones, edit_bones):
        if b.parent_index >= 0:
            eb.parent = edit_bones[b.parent_index]
        if len(b.child_indices) >= 1:
            eb.tail = edit_bones[b.child_indices[0]].head

    # 頂点のボーンウェイトを登録
    index_offset = 0
    for anim_mesh in anim_data.meshes:
        for i, vertex in enumerate(anim_mesh.vertices):
            bone_index_weights = [
                (int(vertex.bone_index_0), vertex.bone_weight_0),
                (int(vertex.bone_index_1), vertex.bone_weight_1)
            ]
            for b, w in bone_index_weights:
                if b >= len(anim_data.bones):
                    raise Exception(f'Vertex bone index {b} is out of bounds. Only {len(anim_data.bones)} bones exist.')
                if w > 0.0:
                    vertex_groups[b].add([i + index_offset], w, 'REPLACE')
        index_offset += len(anim_mesh.vertices)

    # 末端ボーン等の大きさを設定
    for eb, vg in zip(edit_bones, vertex_groups):
        if eb.length < 0.01:
            bone_head = eb.head
            furthest_vertex: tuple[float, mathutils.Vector] | None = None

            for vertex in mesh.vertices:
                for vgel in vertex.groups:
                    if vg.index != vgel.group:
                        continue
                    d = (vertex.co - bone_head).length
                    if furthest_vertex is None or furthest_vertex[0] < d:
                        furthest_vertex = (d, vertex.co)
                    break

            if furthest_vertex is None:
                eb.tail = bone_head + mathutils.Vector((0, 0, 0.1))
            else:
                eb.tail = furthest_vertex[1]

    '''
    bpy.ops.object.mode_set(mode='POSE')

    pose_data: dict[str, list[tuple[mathutils.Quaternion, mathutils.Vector]]] = {}
    for p in anim_data.poses:
        #print(p.name)
        pose_data[p.name] = [(to_blender_rotation_matrix(r).to_quaternion(), to_blender_vec(t)) for r, t in p.bone_transforms]

    # キーフレームをインポート
    if arm_obj.pose is None or bpy.context.scene is None:
        raise Exception('Unexpected error')
    pb_list = arm_obj.pose.bones
    o_frame = bpy.context.scene.frame_current

    for motion in anim_data.motions[:1]:
        #base_pose = pose_data[motion.name]
        bone_motion_dict = {b.bone_index: b for b in motion.bone_motions}

        # ルートから順番に処理、親の回転が確定していることを保証
        q: list[int] = [i for i, b in enumerate(anim_data.bones) if b.parent_index < 0]
        while len(q) > 0:
            bone_index = q.pop(0)
            q.extend(anim_data.bones[bone_index].child_indices)

            parent_index = anim_data.bones[bone_index].parent_index
            bone_motion = bone_motion_dict[bone_index]
            pb = pb_list[bone_index]

            if parent_index < 0:
                parent_rot_inv = mathutils.Quaternion()
            else:
                parent_rot_inv = pb.bone.matrix_local.to_quaternion().inverted()

            # 位置を適用
            # anim ファイルはグローバル系、Blender は親ボーンのローカル系
            for tkf in bone_motion.translation_keyframes:
                _set_timestamp(tkf.timestamp)
                pb.location = parent_rot_inv @ to_blender_vec(tkf.translation)
                pb.keyframe_insert('location')

            # 回転を適用
            prev_rot = None
            for rkf in bone_motion.rotation_keyframes:
                _set_timestamp(rkf.timestamp)
                rot = to_blender_quaternion(rkf.rotation)
                # 逆回転防止
                if prev_rot is not None and prev_rot.dot(rot) < 0:
                    rot.negate()
                pb.rotation_quaternion = rot
                pb.keyframe_insert('rotation_quaternion')
                prev_rot = rot

    bpy.context.scene.frame_set(o_frame)
    '''

    '''
    # ポーズをインポート
    for pose_data in anim_data.poses:
        print(pose_data.name)
        action = bpy.data.actions.new(pose_data.name)
        arm_anim = arm_obj.animation_data_create()
        arm_anim.action = action

        bone_matrices = _resolve_bone_matrices(bone_parent_indices, [to_blender_matrix(r, t) for r, t in pose_data.bone_transforms])

        for i in range(len(anim_data.bones)):
            if arm_obj.pose is None or i >= len(arm_obj.pose.bones):
                continue
            pb = arm_obj.pose.bones[i]
            pb.matrix = bone_matrices[i]

            pb.keyframe_insert('location', frame=0)
            pb.keyframe_insert('rotation_quaternion', frame=0)
            pb.keyframe_insert('scale', frame=0)

        action.use_fake_user = True'''

    #bpy.ops.object.mode_set(mode='OBJECT')


def load(
        mesh_type: MeshTypeEnum,
        context,
        files=[],
        directory='',
        filepath='',
        use_collection=False,
        strict_mode=True
):
    default_layer = context.view_layer.active_layer_collection.collection

    if len(files) == 0:
        directory = Path(filepath).parent
        file_paths = [Path(filepath)]
    else:
        directory = Path(directory)
        file_paths = [directory.joinpath(f.name) for f in files]

    scene = bpy.context.scene
    if scene is None:
        return False
    collection = scene.collection

    for file in file_paths:
        name = Path(file.name).stem
        if use_collection:
            collection = bpy.data.collections.new(name)
            context.scene.collection.children.link(collection)
            context.view_layer.active_layer_collection = context.view_layer.layer_collection.children[collection.name]

        if mesh_type == 'MESH':
            load_mesh(file, collection, name, strict_mode)
        elif mesh_type == 'PHYS':
            load_phys(file, collection, name, strict_mode)
        elif mesh_type == 'ANIM':
            load_anim(file, collection, name, strict_mode)
        else:
            return False

    active = context.view_layer.layer_collection.children.get(default_layer.name)
    if active is not None:
        context.view_layer.active_layer_collection = active

    return True
