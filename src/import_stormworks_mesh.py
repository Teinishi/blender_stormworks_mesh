from pathlib import Path

import bpy

from .data_struct import SwColor, MeshVertex, Mesh, PhysicsMesh, AnimVertex, Anim
from .utils import *


def _create_mesh_object(obj_name: str, mesh_name: str, collection: bpy.types.Collection, vertices: list[FloatTuple3], triangles: list[IntTuple3], vertex_colors: list[FloatTuple4] | None = None, matrix=None):
    mesh = bpy.data.meshes.new(mesh_name)
    obj = bpy.data.objects.new(obj_name, mesh)
    collection.objects.link(obj)
    mesh.from_pydata(vertices, [], triangles)
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
    vertices: list[FloatTuple3]
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
                    self.materials.append(_create_material(f'{self.name}_{len(self.color_indices) + 1:02}', color))

    def finalize(self, collection: bpy.types.Collection):
        obj, mesh = _create_mesh_object(self.name, self.name, collection, self.vertices, self.triangles)
        for m in self.materials:
            mesh.materials.append(m)

        for m, polygon in zip(self.polygon_material, mesh.polygons):
            polygon.material_index = m

        return (obj, mesh)


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

    # メッシュのインポート
    obj_builder = _ObjectMaterialBuilder(name)
    for anim_mesh in anim_data.meshes:
        obj_builder.add_submesh(anim_mesh.shader_id, anim_mesh.vertices, anim_mesh.indices)
    obj_builder.finalize(collection)


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
