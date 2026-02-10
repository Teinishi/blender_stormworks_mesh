# Blender add-on: Stormworks Mesh IO

This Blender add-on enables direct import and export of Stormworks 3D model files (.mesh) and terrain files (.phys). It simplifies work compared to using the SDK's mesh_compiler via intermediate formats (.dae or .fbx). It also serves as an alternative since COLLADA (.dae) import/export functionality has been removed in Blender 5.0 and later.

## Installation

Download the latest stormworks_mesh_io-\*.\*.\*.zip, and install it by dragging and dropping the zip file directly into Blender.

## Using from Blender Python API

You can integrate this add-on's functionality into automation using the Blender Python API.

```python
bpy.ops.stormworks_mesh_io.import_mesh(*, filepath='', use_collection=False, strict_mode=True)
```

Load a .mesh file.

- **filepath**: `str` - File path to import.
- **use_collection**: `bool` - Whether to group loaded objects into a collection.
- **strict_mode**: `bool` - When `True`, errors occur if the file contents differ from normal; when `False`, errors that can be ignored are ignored.

```python
bpy.ops.stormworks_mesh_io.import_phys(*, filepath='', use_collection=False, strict_mode=True)
```

Load a .phys file.

- **filepath**: `str` - File path to import.
- **use_collection**: `bool` - Whether to group loaded objects into a collection.
- **strict_mode**: `bool` - When `True`, errors occur if the file contents differ from normal; when `False`, errors that can be ignored are ignored.

```python
bpy.ops.stormworks_mesh_io.export_mesh(*, filepath='', selected=False, apply_transform=True, apply_modifiers=True, name_mode='NONE')
```

Save a .mesh file.

- **filepath**: `str` - File path to export.
- **selected**: `bool` - Only export selected objects.
- **apply_transform**: `bool` - Output the object with the transform applied.
- **apply_modifiers**: `bool` - Output with modifiers applied.
- **name_mode**: `'MESH', 'OBJECT', 'MATERIAL', 'NONE'` - The mesh name to embed in the .mesh file; if `‘NONE’`, no name is embedded

```python
bpy.ops.stormworks_mesh_io.export_phys(*, filepath='', selected=False, apply_transform=True, apply_modifiers=True, divide_grid=True)
```

Save a .phys file.

- **filepath**: `str` - File path to export.
- **selected**: `bool` - Only export selected objects.
- **apply_transform**: `bool` - Output the object with the transform applied.
- **apply_modifiers**: `bool` - Output with modifiers applied.
- **divide_grid**: `bool` - As with regular .phys files, divide into 128m grids.
