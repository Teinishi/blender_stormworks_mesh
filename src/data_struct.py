from dataclasses import dataclass
from io import BufferedReader, BufferedWriter
import struct


def _read_unpack(reader: BufferedReader, fmt: str):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, reader.read(size))


def _pack_write(writer: BufferedWriter, fmt: str, *values):
    writer.write(struct.pack(fmt, *values))


def _read_uint(reader: BufferedReader) -> int:
    return _read_unpack(reader, '<I')[0]


def _read_ushort(reader: BufferedReader) -> int:
    return _read_unpack(reader, '<H')[0]


def _read_name(reader: BufferedReader):
    name_len = _read_ushort(reader)
    return reader.read(name_len).decode('utf-8')


@dataclass(frozen=True)
class SwVec3:
    x: float
    y: float
    z: float

    @staticmethod
    def one():
        return SwVec3(1.0, 1.0, 1.0)

    @staticmethod
    def from_reader(reader: BufferedReader):
        x, y, z = _read_unpack(reader, '<fff')
        return SwVec3(x, y, z)

    def to_writer(self, writer: BufferedWriter):
        _pack_write(writer, '<fff', self.x, self.y, self.z)


@dataclass(frozen=True)
class SwColor:
    r: int
    g: int
    b: int
    a: int

    @staticmethod
    def from_reader(reader: BufferedReader):
        r, g, b, a = _read_unpack(reader, '<BBBB')
        return SwColor(r, g, b, a)

    def to_writer(self, writer: BufferedWriter):
        _pack_write(writer, '<BBBB', self.r, self.g, self.b, self.a)


@dataclass(frozen=True)
class SwQuaternion:
    x: float
    y: float
    z: float
    w: float

    @staticmethod
    def from_reader(reader: BufferedReader):
        x, y, z, w = _read_unpack(reader, '<ffff')
        return SwQuaternion(x, y, z, w)

    def to_writer(self, writer: BufferedWriter):
        _pack_write(writer, '<ffff', self.x, self.y, self.z, self.w)


@dataclass(frozen=True)
class SwMatrix3:
    m: list[float]

    @staticmethod
    def from_reader(reader: BufferedReader):
        m = list(_read_unpack(reader, '<fffffffff'))
        return SwMatrix3(m)


@dataclass(frozen=True)
class MeshVertex:
    position: SwVec3
    color: SwColor
    normal: SwVec3

    @staticmethod
    def from_reader(reader: BufferedReader):
        position = SwVec3.from_reader(reader)
        color = SwColor.from_reader(reader)
        normal = SwVec3.from_reader(reader)
        return MeshVertex(position, color, normal)

    def to_writer(self, writer: BufferedWriter):
        self.position.to_writer(writer)
        self.color.to_writer(writer)
        self.normal.to_writer(writer)


@dataclass(frozen=True)
class SubMesh:
    index_buffer_start: int
    index_buffer_length: int
    shader_id: int
    bounds_min: SwVec3
    bounds_max: SwVec3
    name: str

    @staticmethod
    def from_reader(reader: BufferedReader, strict: bool = True):
        index_buffer_start, index_buffer_length, h2, shader_id = _read_unpack(reader, '<IIHH')
        if strict and h2 != 0:
            raise ValueError(f'Unexpected value')
        if strict and not (0 <= shader_id <= 3):
            raise ValueError(f'Unexpected value')

        bounds_min = SwVec3.from_reader(reader)
        bounds_max = SwVec3.from_reader(reader)


        if strict and _read_ushort(reader) != 0:
            raise ValueError(f'Unexpected value')
        name = _read_name(reader)

        h8 = SwVec3.from_reader(reader)
        if strict and h8 != SwVec3.one():
            raise ValueError(f'Unexpected value')

        return SubMesh(index_buffer_start, index_buffer_length, shader_id, bounds_min, bounds_max, name)

    def to_writer(self, writer: BufferedWriter):
        _pack_write(writer, '<IIHH', self.index_buffer_start, self.index_buffer_length, 0, self.shader_id)

        self.bounds_min.to_writer(writer)
        self.bounds_max.to_writer(writer)

        name_bytes = self.name.encode('utf-8')
        _pack_write(writer, '<HH', 0, len(name_bytes))
        writer.write(name_bytes)

        SwVec3.one().to_writer(writer)


@dataclass(frozen=True)
class Mesh:
    vertices: list[MeshVertex]
    indices: list[int]
    submeshes: list[SubMesh]

    @staticmethod
    def from_reader(reader: BufferedReader, strict: bool = True):
        if strict and reader.read(4) != b'mesh':
            raise ValueError('Not a valid stormworks mesh file.')

        h0, h1, vertex_count, h3, h4 = _read_unpack(reader, '<HHHHH')
        if strict and h0 != 7:
            raise ValueError(f'Unexpected value')
        if strict and h1 != 1:
            raise ValueError(f'Unexpected value')
        if strict and h3 != 19:
            raise ValueError(f'Unexpected value')
        if strict and h4 != 0:
            raise ValueError(f'Unexpected value')

        vertices = []
        for _ in range(vertex_count):
            vertices.append(MeshVertex.from_reader(reader))

        index_count = _read_uint(reader)
        if strict and index_count % 3 != 0:
            raise ValueError(f'Unexpected value')
        indices = []
        for _ in range(index_count):
            v = _read_ushort(reader)
            if strict and not (0 <= v < vertex_count):
                raise ValueError( f'Index {v} is out of the range [{0}, {vertex_count}).')
            indices.append(v)

        submesh_count =_read_ushort(reader)
        submeshes = []
        for _ in range(submesh_count):
            submeshes.append(SubMesh.from_reader(reader, strict=strict))

        tail = _read_ushort(reader)
        if strict and tail != 0:
            raise ValueError(f'Unexpected value')

        return Mesh(vertices, indices, submeshes)

    def to_writer(self, writer: BufferedWriter):
        writer.write(b'mesh')
        _pack_write(writer, '<HHHHH', 7, 1, len(self.vertices), 19, 0)

        for vertex in self.vertices:
            vertex.to_writer(writer)

        _pack_write(writer, '<I', len(self.indices))
        for v in self.indices:
            _pack_write(writer, '<H', v)

        _pack_write(writer, '<H', len(self.submeshes))
        for submesh in self.submeshes:
            submesh.to_writer(writer)

        _pack_write(writer, '<H', 0)


@dataclass(frozen=True)
class SubPhysMesh:
    vertices: list[SwVec3]
    indices: list[int]

    @staticmethod
    def from_reader(reader: BufferedReader):
        vertex_count = _read_ushort(reader)
        vertices = []
        for _ in range(vertex_count):
            vertices.append(SwVec3.from_reader(reader))

        index_count = _read_ushort(reader)
        indices = []
        for _ in range(index_count):
            indices.append(_read_unpack(reader, '<I'))

        return SubPhysMesh(vertices, indices)

    def to_writer(self, writer: BufferedWriter):
        _pack_write(writer, '<H', len(self.vertices))
        for vertex in self.vertices:
            vertex.to_writer(writer)

        _pack_write(writer, '<H', len(self.indices))
        for index in self.indices:
            _pack_write(writer, '<I', index)


@dataclass(frozen=True)
class PhysicsMesh:
    sub_phys_meshes: list[SubPhysMesh]

    @staticmethod
    def from_reader(reader: BufferedReader, strict: bool = True):
        if strict and reader.read(4) != b'phys':
            raise ValueError('Not a valid stormworks physics mesh file.')

        h0, sub_phys_count = _read_unpack(reader, '<HH')
        if strict and h0 != 2:
            raise ValueError(f'Unexpected value')

        sub_phys_meshes = []
        for _ in range(sub_phys_count):
            sub_phys_meshes.append(SubPhysMesh.from_reader(reader))

        return PhysicsMesh(sub_phys_meshes)

    def to_writer(self, writer: BufferedWriter):
        writer.write(b'phys')
        _pack_write(writer, '<HH', 2, len(self.sub_phys_meshes))

        for sub_phys in self.sub_phys_meshes:
            sub_phys.to_writer(writer)


@dataclass(frozen=True)
class AnimVertex:
    position: SwVec3
    color: SwColor
    uv: tuple[float, float]
    normal: SwVec3
    bone_index_0: float
    bone_index_1: float
    bone_weight_0: float
    bone_weight_1: float

    @staticmethod
    def from_reader(reader: BufferedReader):
        position = SwVec3.from_reader(reader)
        color = SwColor.from_reader(reader)
        uv = _read_unpack(reader, '<ff')
        normal = SwVec3.from_reader(reader)
        bone_index_0, bone_index_1, bone_weight_0, bone_weight_1 = _read_unpack(reader, '<ffff')
        return AnimVertex(position, color, uv, normal, bone_index_0, bone_index_1, bone_weight_0, bone_weight_1)

    def to_writer(self, writer: BufferedWriter):
        self.position.to_writer(writer)
        self.color.to_writer(writer)
        _pack_write(writer, '<ff', self.uv[0], self.uv[1])
        self.normal.to_writer(writer)
        _pack_write(writer, '<ffff', self.bone_index_0, self.bone_index_1, self.bone_weight_0, self.bone_weight_1)


@dataclass(frozen=True)
class AnimMesh:
    shader_id: int
    vertices: list[AnimVertex]
    indices: list[int]

    @staticmethod
    def from_reader(reader: BufferedReader, strict=True):
        h0, h1, h2 = _read_unpack(reader, '<IIH')
        if strict and h0 != 151:
            raise Exception('Unexpected value')
        if strict and h2 != 0:
            raise Exception('Unexpected value')


        vertices_size = _read_uint(reader)
        if vertices_size % 52 != 0:
            raise Exception('Unexpected value')
        vertices = []
        for _ in range(vertices_size // 52):
            vertices.append(AnimVertex.from_reader(reader))

        indices_size = _read_uint(reader)
        if indices_size % 12 != 0:
            raise Exception('Unexpected value')
        indices = []
        for _ in range(indices_size // 4):
            indices.append(_read_uint(reader))

        return AnimMesh(h1, vertices, indices)


@dataclass(frozen=True)
class Bone:
    name: str
    rotation: SwMatrix3
    translation: SwVec3
    parent_index: int
    child_indices: list[int]

    @staticmethod
    def from_reader(reader: BufferedReader):
        name = _read_name(reader)

        rotation = SwMatrix3.from_reader(reader)
        translation = SwVec3.from_reader(reader)

        parent_index, n_children = _read_unpack(reader, '<iI')
        child_indices = []
        for _ in range(n_children):
            child_indices.append(_read_uint(reader))

        return Bone(name, rotation, translation, parent_index, child_indices)


@dataclass(frozen=True)
class Pose:
    name: str
    bone_transforms: list[tuple[SwMatrix3, SwVec3]]

    @staticmethod
    def from_reader(reader: BufferedReader):
        name = _read_name(reader)

        n_bones = _read_uint(reader)
        bone_matrices = []
        for _ in range(n_bones):
            rotation = SwMatrix3.from_reader(reader)
            translation = SwVec3.from_reader(reader)
            bone_matrices.append((rotation, translation))

        return Pose(name, bone_matrices)


@dataclass(frozen=True)
class TranslationKeyframe:
    timestamp: int
    translation: SwVec3

    @staticmethod
    def from_reader(reader: BufferedReader):
        timestamp = _read_ushort(reader)
        translation = SwVec3.from_reader(reader)
        return TranslationKeyframe(timestamp, translation)


@dataclass(frozen=True)
class RotationKeyframe:
    timestamp: int
    rotation: SwQuaternion

    @staticmethod
    def from_reader(reader: BufferedReader):
        timestamp = _read_ushort(reader)
        rotation = SwQuaternion.from_reader(reader)
        return RotationKeyframe(timestamp, rotation)


@dataclass(frozen=True)
class BoneAnimation:
    bone_index: int
    translations: list[TranslationKeyframe]
    rotations: list[RotationKeyframe]

    @staticmethod
    def from_reader(reader: BufferedReader):
        bone_index = _read_uint(reader)

        n_translations = _read_uint(reader)
        translations = []
        for _ in range(n_translations):
            translations.append(TranslationKeyframe.from_reader(reader))

        n_rotations = _read_uint(reader)
        rotations = []
        for _ in range(n_rotations):
            rotations.append(RotationKeyframe.from_reader(reader))

        return BoneAnimation(bone_index, translations, rotations)


@dataclass(frozen=True)
class Animation:
    name: str
    bone_animations: list[BoneAnimation]

    @staticmethod
    def from_reader(reader: BufferedReader):
        name = _read_name(reader)

        n_bones = _read_uint(reader)
        bone_animations = []
        for _ in range(n_bones):
            bone_animations.append(BoneAnimation.from_reader(reader))

        return Animation(name, bone_animations)


@dataclass
class Data3:
    h0: int
    m0: SwMatrix3
    v0: SwVec3
    p0: tuple[float, float]
    m1: SwMatrix3
    m2: SwMatrix3
    p1: tuple[float, float]

    @staticmethod
    def from_reader(reader: BufferedReader):
        h0 = _read_uint(reader)

        m0 = SwMatrix3.from_reader(reader)
        v0 = SwVec3.from_reader(reader)
        p0 = _read_unpack(reader, '<ff')
        m1 = SwMatrix3.from_reader(reader)
        m2 = SwMatrix3.from_reader(reader)
        p1 = _read_unpack(reader, '<ff')

        return Data3(h0, m0, v0, p0, m1, m2, p1)


@dataclass(frozen=True)
class Anim:
    meshes: list[AnimMesh]
    bones: list[Bone]
    poses: list[Pose]
    animations: list[Animation]
    data3s: list[Data3]

    @staticmethod
    def from_reader(reader: BufferedReader, strict=True):
        if strict and reader.read(4) != b'anim':
            raise ValueError('Not a valid stormworks anim file.')
        h0, n_meshes = _read_unpack(reader, '<II')
        if strict and h0 != 1:
            raise Exception('Unexpected value')

        meshes = []
        for _ in range(n_meshes):
            meshes.append(AnimMesh.from_reader(reader, strict))

        n_bones = _read_uint(reader)
        bones = []
        for _ in range(n_bones):
            bones.append(Bone.from_reader(reader))

        n_poses = _read_uint(reader)
        poses = []
        for _ in range(n_poses):
            poses.append(Pose.from_reader(reader))

        n_animations = _read_uint(reader)
        animations = []
        for _ in range(n_animations):
            animations.append(Animation.from_reader(reader))

        n_data3s = _read_uint(reader)
        data3s = []
        for _ in range(n_data3s):
            data3s.append(Data3.from_reader(reader))

        return Anim(meshes, bones, poses, animations, data3s)
