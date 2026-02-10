# Blender add-on: Stormworks Mesh IO
Stormworks 専用の3Dモデルファイル (.mesh) と地形ファイル (.phys) を Blender 上で直接インポート・エクスポートするアドオンです。中間形式 (.dae や .fbx) を経由して SDK の mesh_compiler を使用する方法に比べて作業が簡略化されるほか、Blender 5.0 以降では COLLADA (.dae) インポート・エクスポート機能が削除されているため、その代替でもあります。

## インストール
[リリース](https://github.com/Teinishi/blender_stormworks_mesh/releases) から最新の stormworks_mesh_io-\*.\*.\*.zip をダウンロードし、zip のまま Blender にドラッグ&ドロップしてインストールできます。

## Blender Python API からの利用
Blender Python API を用いた自動化に本アドオンの処理を組み込むことができます。

```python
bpy.ops.stormworks_mesh_io.import_mesh(*, filepath='', use_collection=False, strict_mode=True)
```

.mesh ファイルをロードします。

- **filepath**: `str` - インポートするファイルのパス
- **use_collection**: `bool` - ロードしたオブジェクトをコレクションにまとめる
- **strict_mode**: `bool` - 厳格モード `True`のときファイルの内容の一部が通常と異なる場合にエラー、`False`のとき無視できるエラーは無視する

```python
bpy.ops.stormworks_mesh_io.import_phys(*, filepath='', use_collection=False, strict_mode=True)
```

.phys ファイルをロードします。

- **filepath**: `str` - インポートするファイルのパス
- **use_collection**: `bool` - ロードしたオブジェクトをコレクションにまとめる
- **strict_mode**: `bool` - 厳格モード `True`のときファイルの内容の一部が通常と異なる場合にエラー、`False`のとき無視できるエラーは無視する

```python
bpy.ops.stormworks_mesh_io.export_mesh(*, filepath='', selected=False, apply_transform=True, apply_modifiers=True, name_mode='NONE')
```

.mesh ファイルをロードします。

- **filepath**: `str` - インポートするファイルのパス
- **selected**: `bool` - 選択物のみ
- **apply_transform**: `bool` - オブジェクトのトランスフォームを適用したものを出力
- **apply_modifiers**: `bool` - モディファイアーを適用したものを出力
- **name_mode**: `'MESH', 'OBJECT', 'MATERIAL', 'NONE'` - .mesh ファイルに埋め込むメッシュ名

```python
bpy.ops.stormworks_mesh_io.export_phys(*, filepath='', selected=False, apply_transform=True, apply_modifiers=True, divide_grid=True)
```

.phys ファイルをロードします。

- **filepath**: `str` - インポートするファイルのパス
- **selected**: `bool` - 選択物のみ
- **apply_transform**: `bool` - オブジェクトのトランスフォームを適用したものを出力
- **apply_modifiers**: `bool` - モディファイアーを適用したものを出力
- **divide_grid**: `bool` - 出力時に自動的に 128m ごとのグリッドで区切る
