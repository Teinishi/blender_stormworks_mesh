from contextlib import contextmanager
from typing import Generic, TypeVar

import bpy
import bmesh

from .mesh_struct import MeshVec3, MeshVertex, SubMesh, Mesh, SubPhysMesh, PhysicsMesh
from .utils import *


def _vec_min(a: MeshVec3 | mathutils.Vector, b: MeshVec3 | mathutils.Vector | None) -> tuple[float, float, float]:
    if b is None:
        return (a.x, a.y, a.z)
    else:
        return (min(a.x, b.x), min(a.y, b.y), min(a.z, b.z))


def _vec_max(a: MeshVec3 | mathutils.Vector, b: MeshVec3 | mathutils.Vector | None) -> tuple[float, float, float]:
    if b is None:
        return (a.x, a.y, a.z)
    else:
        return (max(a.x, b.x), max(a.y, b.y), max(a.z, b.z))


T = TypeVar('T')
class _PolygonOptimizer(Generic[T]):
    vertices: list[T] = []
    indices: list[int] = []
    _vertex_index_map: dict[T, int] = {}

    def add_vertex(self, vertex: T):
        if vertex in self._vertex_index_map:
            self.indices.append(self._vertex_index_map[vertex])
        else:
            i = len(self.vertices)
            self.vertices.append(vertex)
            self._vertex_index_map[vertex] = i
            self.indices.append(i)


@contextmanager
def _evaluated_mesh(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph, use_transform=True, use_mesh_modifiers=True):
    obj_eval = obj.evaluated_get(depsgraph) if use_mesh_modifiers else obj
    mesh = obj_eval.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    if use_transform:
        mesh.transform(obj.matrix_world)

    try:
        yield mesh
    finally:
        obj_eval.to_mesh_clear()


def save_mesh(ctx_objects: list[bpy.types.Object], depsgraph: bpy.types.Depsgraph, filepath: str, use_transform=True, use_mesh_modifiers=True, name_mode: NameModeEnum = 'NONE'):
    submesh_triangles: dict[int, list[tuple[MeshVertex, ...]]] = {i: [] for i in range(4)}
    submesh_names: dict[int, str] = {}

    for obj in ctx_objects:
        if obj.type != 'MESH':
            continue
        with _evaluated_mesh(obj, depsgraph, use_transform=use_transform, use_mesh_modifiers=use_mesh_modifiers) as mesh:
            # 三角面化
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.to_mesh(mesh)
            bm.free()

            for face in mesh.polygons:
                material = None
                if face.material_index < len(mesh.materials):
                    material = mesh.materials[face.material_index]

                shader_id = 0
                color = from_blender_color((0.6, 0.6, 0.6, 1.0))
                if material is not None:
                    if material.name == 'MATERIALglass':
                        shader_id = 1
                        color = GLASS_COLOR
                    elif material.name == 'MATERIALadditive':
                        shader_id = 2
                        color = ADDITIVE_COLOR
                    elif material.name == 'MATERIALlava':
                        shader_id = 3
                        color = LAVA_COLOR

                    base_color = bsdf_base_color(material)
                    if base_color and not base_color.is_linked:
                        color = from_blender_color(base_color.default_value) # type: ignore

                    if name_mode == 'MATERIAL':
                        submesh_names[shader_id] = material.name

                normal = from_blender_vec(face.normal)

                submesh_triangles[shader_id].append(tuple(MeshVertex(from_blender_vec(mesh.vertices[v].co), color, normal) for v in face.vertices[:3]))

                if name_mode == 'MESH':
                    submesh_names[shader_id] = mesh.name
                elif name_mode == 'OBJECT':
                    submesh_names[shader_id] = obj.name

    poly_opt: _PolygonOptimizer[MeshVertex] = _PolygonOptimizer()
    submeshes = []
    for shader_id in range(4):
        triangles = submesh_triangles[shader_id]
        len_triangles = len(triangles)

        index_buffer_start = len(poly_opt.indices)
        bounds_min, bounds_max = None, None
        for triangle in triangles:
            for vertex in triangle:
                bounds_min = MeshVec3(*_vec_min(vertex.position, bounds_min))
                bounds_max = MeshVec3(*_vec_max(vertex.position, bounds_max))
                poly_opt.add_vertex(vertex)

        if bounds_min is None or bounds_max is None:
            continue
        submeshes.append(SubMesh(index_buffer_start, 3 * len_triangles, shader_id, bounds_min, bounds_max, submesh_names.get(shader_id, '')))

    with open(filepath, 'wb') as f:
        Mesh(poly_opt.vertices, poly_opt.indices, submeshes).to_writer(f)


def save_phys(ctx_objects: list[bpy.types.Object], depsgraph: bpy.types.Depsgraph, filepath: str, use_transform=True, use_mesh_modifiers=True, divide_grid=True):
    submesh_triangles: list[list[tuple[MeshVec3, ...]]] = []

    for obj in ctx_objects:
        if obj.type != 'MESH':
            continue
        with _evaluated_mesh(obj, depsgraph, use_transform=use_transform, use_mesh_modifiers=use_mesh_modifiers) as mesh:
            if divide_grid:
                # 128m のボクセルで分割
                bounds_min, bounds_max = None, None
                for vertex in mesh.vertices:
                    bounds_min = mathutils.Vector(_vec_min(vertex.co, bounds_min))
                    bounds_max = mathutils.Vector(_vec_max(vertex.co, bounds_max))
                if bounds_min is None or bounds_max is None:
                    continue

                grid_origin = mathutils.Vector((-500, -500, -1000))
                grid_size = mathutils.Vector((128, 128, 128))

                bm = bmesh.new()
                bm.from_mesh(mesh)

                for ax in range(3):
                    o, s = grid_origin[ax], grid_size[ax]
                    for i in range(int((bounds_min[ax] - o)//s) + 1, int((bounds_max[ax] - o)//s) + 1):
                        co = mathutils.Vector((0, 0, 0))
                        co[ax] = o + s*i
                        no = mathutils.Vector((0, 0, 0))
                        no[ax] = 1
                        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
                        ret = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no) # type: ignore

                bmesh.ops.triangulate(bm, faces=bm.faces[:])
                bm.to_mesh(mesh)
                bm.free()

                voxel_triangles: dict[tuple[int, int, int], list[tuple[MeshVec3, ...]]] = {}
                for face in mesh.polygons:
                    d = face.center - grid_origin
                    voxel_key = (int(d.x // grid_size.x), int(d.y // grid_size.y), int(d.z // grid_size.z))
                    if voxel_key not in voxel_triangles:
                        voxel_triangles[voxel_key] = []
                    voxel_triangles[voxel_key].append(tuple(from_blender_vec(mesh.vertices[v].co) for v in face.vertices[:3]))

                for i, key in enumerate(sorted(voxel_triangles.keys(), key=lambda k: (k[0], k[2], k[1]))):
                    submesh_triangles.append(voxel_triangles[key])

            else:
                # 128m ごとに分割しない
                bm = bmesh.new()
                bm.from_mesh(mesh)
                bmesh.ops.triangulate(bm, faces=bm.faces[:])
                bm.to_mesh(mesh)
                bm.free()

                triangles: list[tuple[MeshVec3, ...]] = []
                for face in mesh.polygons:
                    triangles.append(tuple(from_blender_vec(mesh.vertices[v].co) for v in face.vertices[:3]))

                submesh_triangles.append(triangles)

    sub_phys_meshes: list[SubPhysMesh] = []
    for triangles in submesh_triangles:
        vertices: list[MeshVec3] = []

        for triangle in triangles:
            for vertex in triangle:
                vertices.append(vertex)

        sub_phys_meshes.append(SubPhysMesh(vertices, []))

    with open(filepath, 'wb') as f:
        PhysicsMesh(sub_phys_meshes).to_writer(f)


def save(
        mesh_type: MeshTypeEnum,
        context,
        filepath='',
        use_selection=False,
        use_transform=True,
        use_mesh_modifiers=True,
        name_mode: NameModeEnum = 'NONE',
        divide_grid=True
):
    context.window.cursor_set('WAIT')

    active_object = context.view_layer.objects.active

    org_mode = None
    if active_object and active_object.mode != 'OBJECT':
        org_mode = active_object.mode
    if bpy.ops.object.mode_set.poll(): # type: ignore
        bpy.ops.object.mode_set(mode='OBJECT')

    if use_selection:
        ctx_objects = context.selected_objects
    else:
        ctx_objects = context.view_layer.objects
    ctx_objects = sorted(ctx_objects, key=lambda o: o.name)
    depsgraph = context.evaluated_depsgraph_get()

    if mesh_type == 'MESH':
        save_mesh(ctx_objects, depsgraph, filepath, use_transform, use_mesh_modifiers, name_mode)
    elif mesh_type == 'PHYS':
        save_phys(ctx_objects, depsgraph, filepath, use_transform, use_mesh_modifiers, divide_grid)
    else:
        return False

    if active_object and org_mode:
        context.view_layer.objects.active = active_object
        if bpy.ops.object.mode_set.poll(): # type: ignore
            bpy.ops.object.mode_set(mode=org_mode)

    context.window.cursor_set('DEFAULT')
    return True
