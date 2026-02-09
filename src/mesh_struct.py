from dataclasses import dataclass
from io import BufferedReader, BufferedWriter
import struct


def _read_unpack(reader: BufferedReader, fmt: str):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, reader.read(size))


def _pack_write(writer: BufferedWriter, fmt: str, *values):
    writer.write(struct.pack(fmt, *values))


@dataclass(frozen=True)
class MeshVec3:
    x: float
    y: float
    z: float

    @staticmethod
    def one():
        return MeshVec3(1.0, 1.0, 1.0)

    @staticmethod
    def from_reader(reader: BufferedReader):
        x, y, z = _read_unpack(reader, '<fff')
        return MeshVec3(x, y, z)

    def to_writer(self, writer: BufferedWriter):
        _pack_write(writer, '<fff', self.x, self.y, self.z)


@dataclass(frozen=True)
class MeshColor4:
    r: int
    g: int
    b: int
    a: int

    @staticmethod
    def from_reader(reader: BufferedReader):
        r, g, b, a = _read_unpack(reader, '<BBBB')
        return MeshColor4(r, g, b, a)

    def to_writer(self, writer: BufferedWriter):
        _pack_write(writer, '<BBBB', self.r, self.g, self.b, self.a)


@dataclass(frozen=True)
class MeshVertex:
    position: MeshVec3
    color: MeshColor4
    normal: MeshVec3

    @staticmethod
    def from_reader(reader: BufferedReader):
        position = MeshVec3.from_reader(reader)
        color = MeshColor4.from_reader(reader)
        normal = MeshVec3.from_reader(reader)
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
    bounds_min: MeshVec3
    bounds_max: MeshVec3
    name: str

    @staticmethod
    def from_reader(reader: BufferedReader, strict: bool = True):
        index_buffer_start, index_buffer_length, h2, shader_id = _read_unpack(reader, '<IIHH')
        if strict and h2 != 0:
            raise ValueError(
                f'Unexpected value. Expected 0x{0:04x}, found 0x{h2:04x}.')
        if strict and not (0 <= shader_id <= 3):
            raise ValueError(f'Unexpected shader id. Expected value between 0 and 3, found {shader_id}.')

        bounds_min = MeshVec3.from_reader(reader)
        bounds_max = MeshVec3.from_reader(reader)

        h6, name_len = _read_unpack(reader, '<HH')
        if strict and h6 != 0:
            raise ValueError(
                f'Unexpected value. Expected 0x{0:04x}, found 0x{h6:04x}.')
        name = reader.read(name_len).decode('utf-8')

        h8 = MeshVec3.from_reader(reader)
        if strict and h8 != MeshVec3.one():
            raise ValueError(f'Unexpected value. Expected {MeshVec3.one()}, found {h8}.')

        return SubMesh(index_buffer_start, index_buffer_length, shader_id, bounds_min, bounds_max, name)

    def to_writer(self, writer: BufferedWriter):
        _pack_write(writer, '<IIHH', self.index_buffer_start, self.index_buffer_length, 0, self.shader_id)

        self.bounds_min.to_writer(writer)
        self.bounds_max.to_writer(writer)

        name_bytes = self.name.encode('utf-8')
        _pack_write(writer, '<HH', 0, len(name_bytes))
        writer.write(name_bytes)

        MeshVec3.one().to_writer(writer)


@dataclass(frozen=True)
class Mesh:
    vertices: list[MeshVertex]
    indices: list[int]
    # triangles: list[tuple[int, int, int]]
    submeshes: list[SubMesh]

    @staticmethod
    def from_reader(reader: BufferedReader, strict: bool = True):
        if strict and reader.read(4) != b'mesh':
            raise ValueError('Not a valid stormworks mesh file.')

        h0, h1, vertex_count, h3, h4 = _read_unpack(reader, '<HHHHH')
        if strict and h0 != 7:
            raise ValueError(f'Unexpected value at byte offset 5-6. Expected 0x{7:04x}, found 0x{h0:04x}.')
        if strict and h1 != 1:
            raise ValueError(f'Unexpected value at byte offset 7-8. Expected 0x{1:04x}, found 0x{h1:04x}.')
        if strict and h3 != 19:
            raise ValueError(f'Unexpected value at byte offset 11-12. Expected 0x{19:04x}, found 0x{h3:04x}.')
        if strict and h4 != 0:
            raise ValueError(f'Unexpected value at byte offset 13-14. Expected 0x{0:04x}, found 0x{h4:04x}.')

        vertices = []
        for _ in range(vertex_count):
            vertices.append(MeshVertex.from_reader(reader))

        index_count = _read_unpack(reader, '<I')[0]
        if strict and index_count % 3 != 0:
            raise ValueError(f'Unexpected value at field index_count. Expected a multiple of 3, found {index_count}.')
        indices = []
        for _ in range(index_count):
            v = _read_unpack(reader, '<H')[0]
            if strict and not (0 <= v < vertex_count):
                raise ValueError( f'Index {v} is out of the range [{0}, {vertex_count}).')
            indices.append(v)

        submesh_count = _read_unpack(reader, '<H')[0]
        submeshes = []
        for _ in range(submesh_count):
            submeshes.append(SubMesh.from_reader(reader, strict=strict))

        tail = _read_unpack(reader, '<H')[0]
        if strict and tail != 0:
            raise ValueError(f'Unexpected value at the last of the data. Expected 0x{0:04x}, found 0x{tail:04x}.')

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
    vertices: list[MeshVec3]
    indices: list[int]

    @staticmethod
    def from_reader(reader: BufferedReader):
        vertex_count = _read_unpack(reader, '<H')[0]
        vertices = []
        for _ in range(vertex_count):
            vertices.append(MeshVec3.from_reader(reader))

        index_count = _read_unpack(reader, '<H')[0]
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
            raise ValueError(f'Unexpected value at byte offset 5-6. Expected 0x{2:04x}, found 0x{h0:04x}.')

        sub_phys_meshes = []
        for _ in range(sub_phys_count):
            sub_phys_meshes.append(SubPhysMesh.from_reader(reader))

        return PhysicsMesh(sub_phys_meshes)

    def to_writer(self, writer: BufferedWriter):
        writer.write(b'phys')
        _pack_write(writer, '<HH', 2, len(self.sub_phys_meshes))

        for sub_phys in self.sub_phys_meshes:
            sub_phys.to_writer(writer)
