import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty, BoolProperty, CollectionProperty, EnumProperty
from bpy.types import Operator

from . import import_stormworks_mesh
from . import export_stormworks_mesh

bl_info = {
    'name': 'Stormworks Mesh IO',
    'author': 'Teinishi',
    'description': 'Import/export add-on for Stormworks mesh (.mesh) and physics mesh (.phys)',
    'blender': (2, 80, 0),
    'version': (1, 0, 0),
    'location': 'File > Import-Export',
    'category': 'Import-Export'
}

def execute(context: bpy.types.Context, fn):
    if context.window:
        context.window.cursor_set('WAIT')
    success = fn()
    if context.window:
        context.window.cursor_set('DEFAULT')
    if success:
        return {'FINISHED'}
    else:
        return {'CANCELLED'}


# File > Import > Import Stormworks Mesh (.mesh)
class ImportStormworksMesh(Operator, ImportHelper):
    bl_idname = 'blender_stormworks_mesh.import_mesh'
    bl_label = 'Import MESH'
    filename_ext = '.mesh'

    filter_glob: StringProperty(default='*.mesh', options={'HIDDEN'})
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    directory: StringProperty(subtype='DIR_PATH')

    use_collection: BoolProperty(
        name='Collection',
        description='Create a new collection',
        default=False
    )
    strict_mode: BoolProperty(
        name='Strict Mode',
        default=True
    )

    def execute(self, context):
        if not self.filepath: # type: ignore
            raise Exception('filepath not set')

        kwargs: dict = self.as_keywords(ignore=('filter_glob',)) # type: ignore
        return execute(context, lambda: import_stormworks_mesh.load('MESH', context, **kwargs))


# File > Import > Import Stormworks Physics Mesh (.phys)
class ImportStormworksPhys(Operator, ImportHelper):
    bl_idname = 'blender_stormworks_mesh.import_phys'
    bl_label = 'Import PHYS'
    filename_ext = '.phys'

    filter_glob: StringProperty(default='*.phys', options={'HIDDEN'})
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    directory: StringProperty(subtype='DIR_PATH')

    use_collection: BoolProperty(
        name='Collection',
        description='Create a new collection',
        default=False
    )
    strict_mode: BoolProperty(
        name='Strict Mode',
        default=True
    )

    def execute(self, context):
        if not self.filepath: # type: ignore
            raise Exception('filepath not set')

        kwargs: dict = self.as_keywords(ignore=('filter_glob',)) # type: ignore
        return execute(context, lambda: import_stormworks_mesh.load('PHYS', context, **kwargs))


# File > Export > Export Stormworks Mesh (.mesh)
class ExportStormworksMesh(Operator, ExportHelper):
    bl_idname = 'blender_stormworks_mesh.export_mesh'
    bl_label = 'Export MESH'
    filename_ext = '.mesh'

    filter_glob: StringProperty(default='*.mesh', options={'HIDDEN'})

    use_selection: BoolProperty(
        name='Selected Objects',
        description='Export selected objects only',
        default=False,
    )
    use_transform: BoolProperty(
        name='Apply Object Transform',
        description='Apply object transform.',
        default=True,
    )
    use_mesh_modifiers: BoolProperty(
        name='Apply Modifiers',
        description='Apply modifiers to exported mesh (non destructive).',
        default=True,
    )
    name_mode: EnumProperty(
        name='Name Mode',
        description='Choose which name to include in the exported file. Note: Only one name slot is available for each type of materials (normal, glass, additive, lava).',
        default='NONE',
        items=[
            ('MESH', 'Mesh', "Use mesh's name"),
            ('OBJECT', 'Object', "Use Object's name"),
            ('MATERIAL', 'Material', "Use Material's name"),
            ('NONE', 'None', 'Never export a name'),
        ]
    )

    def execute(self, context):
        if not self.filepath: # type: ignore
            raise Exception('filepath not set')

        kwargs: dict = self.as_keywords(ignore=('filter_glob', 'check_existing')) # type: ignore
        return execute(context, lambda: export_stormworks_mesh.save('MESH', context, **kwargs))


# File > Export > Export Stormworks Physics Mesh (.phys)
class ExportStormworksPhys(Operator, ExportHelper):
    bl_idname = 'blender_stormworks_mesh.export_phys'
    bl_label = 'Export PHYS'
    filename_ext = '.phys'

    filter_glob: StringProperty(default='*.phys', options={'HIDDEN'})

    use_selection: BoolProperty(
        name='Selected Objects',
        description='Export selected objects only',
        default=False,
    )
    use_transform: BoolProperty(
        name='Apply Object Transform',
        description='Apply object transform.',
        default=True,
    )
    use_mesh_modifiers: BoolProperty(
        name='Apply Modifiers',
        description='Apply modifiers to exported mesh (non destructive).',
        default=True,
    )
    divide_grid: BoolProperty(
        name='Divide voxel grid',
        description='Divide mesh by 128m voxel grid.',
        default=True,
    )

    def execute(self, context):
        if not self.filepath: # type: ignore
            raise Exception('filepath not set')

        kwargs: dict = self.as_keywords(ignore=('filter_glob', 'check_existing')) # type: ignore
        return execute(context, lambda: export_stormworks_mesh.save('PHYS', context, **kwargs))


def menu_func_import_mesh(self, context):
    self.layout.operator(
        ImportStormworksMesh.bl_idname,
        text='Stormworks Mesh (.mesh)'
    )


def menu_func_import_phys(self, context):
    self.layout.operator(
        ImportStormworksPhys.bl_idname,
        text='Stormworks Physics Mesh (.phys)'
    )


def menu_func_export_mesh(self, context):
    self.layout.operator(
        ExportStormworksMesh.bl_idname,
        text='Stormworks Mesh (.mesh)'
    )


def menu_func_export_phys(self, context):
    self.layout.operator(
        ExportStormworksPhys.bl_idname,
        text='Stormworks Physics Mesh (.phys)'
    )


# クラスの登録リスト
classes = (
    ImportStormworksMesh,
    ImportStormworksPhys,
    ExportStormworksMesh,
    ExportStormworksPhys,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_mesh)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_phys)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_mesh)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_phys)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_mesh)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_phys)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_mesh)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_phys)
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
