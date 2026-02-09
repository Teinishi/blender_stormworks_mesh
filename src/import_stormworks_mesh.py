from pathlib import Path

import bpy

from .mesh_struct import MeshColor4, Mesh, PhysicsMesh
from .utils import *


def _create_mesh_object(obj_name: str, mesh_name: str, collection, vertices: list[FloatTuple3], triangles: list[IntTuple3], vertex_colors: list[FloatTuple4] | None = None, matrix=None):
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


def _create_material(name: str, color: MeshColor4):
    color_tuple = to_blender_color(color)

    material = bpy.data.materials.new(name)
    material.diffuse_color = color_tuple
    base_color = bsdf_base_color(material)
    if base_color:
        base_color.default_value = color_tuple # type: ignore

    return material

def _get_material(name: str, color: MeshColor4):
    material = bpy.data.materials.get(name)
    if material is None:
        material = _create_material(name, color)
    return material


def load_mesh(file, collection, name: str, strict_mode=True):
    with open(file, 'rb') as f:
        mesh_data = Mesh.from_reader(f, strict=strict_mode)

    color_materials = {}
    glass_material = None
    additive_material = None
    lava_material = None

    for i, submesh in enumerate(mesh_data.submeshes):
        if len(mesh_data.submeshes) == 1:
            obj_name = name
            mesh_name = name
        else:
            obj_name = f'{name}_{i:02}'
            mesh_name = f'{name}_{i:02}'
        if len(submesh.name) > 0:
            mesh_name = submesh.name

        i = submesh.index_buffer_start
        j = i + submesh.index_buffer_length
        indices = mesh_data.indices[i:j]
        if len(indices) == 0:
            continue

        local_vertex_indices = sorted(set(indices))
        index_map = {k: i for i, k in enumerate(local_vertex_indices)}

        vertices = [mesh_data.vertices[i] for i in local_vertex_indices]
        triangles = [(index_map[indices[i - 2]], index_map[indices[i - 1]], index_map[indices[i]]) for i in range(2, len(indices), 3)]

        vertices_pos = [to_blender_vec(v.position) for v in vertices]
        _, mesh = _create_mesh_object(obj_name, mesh_name, collection, vertices_pos, triangles)

        if submesh.shader_id == 1:
            if glass_material is None:
                glass_material = _get_material('MATERIALglass', vertices[0].color)
            mesh.materials.append(glass_material)

        elif submesh.shader_id == 2:
            if additive_material is None:
                additive_material = _get_material('MATERIALadditive', vertices[0].color)
            mesh.materials.append(additive_material)

        elif submesh.shader_id == 3:
            if lava_material is None:
                lava_material = _get_material('MATERIALlava', vertices[0].color)
            mesh.materials.append(lava_material)

        else:
            obj_materials = {}
            for face, tri in zip(mesh.polygons, triangles):
                color = vertices[tri[0]].color

                if color == OVERRIDE_COLOR_1:
                    material = _get_material('OverrideColor1', color)
                elif color == OVERRIDE_COLOR_2:
                    material = _get_material('OverrideColor2', color)
                elif color == OVERRIDE_COLOR_3:
                    material = _get_material('OverrideColor3', color)
                elif color in color_materials:
                    material = color_materials[color]
                else:
                    material = _create_material(f'{name}_{len(color_materials) + 1:02}', color)
                    color_materials[color] = material

                if color not in obj_materials:
                    obj_materials[color] = len(obj_materials)
                    mesh.materials.append(material)

                face.material_index = obj_materials[color]


def load_phys(file, collection, name: str, strict_mode=True):
    with open(file, 'rb') as f:
        phys_mesh_data = PhysicsMesh.from_reader(f, strict=strict_mode)

    for i, sub_phys in enumerate(phys_mesh_data.sub_phys_meshes):
        if len(phys_mesh_data.sub_phys_meshes) == 1:
            sub_phys_name = name
        else:
            sub_phys_name = f'{name}_{i:02}'

        triangles = [(i - 2, i - 1, i) for i in range(2, len(sub_phys.vertices), 3)]
        _create_mesh_object(sub_phys_name, sub_phys_name, collection, [to_blender_vec(v) for v in sub_phys.vertices], triangles)


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
        else:
            return False

    active = context.view_layer.layer_collection.children.get(default_layer.name)
    if active is not None:
        context.view_layer.active_layer_collection = active

    return True
