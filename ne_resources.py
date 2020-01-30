"""
Read resource entries from NE binaries.
"""
import io
import struct
from dataclasses import dataclass

from pe_tools import KnownResourceTypes


def read_u16(s):
    c = s.read(2)
    return struct.unpack("<H", c)[0]


def read_u32(s):
    c = s.read(4)
    return struct.unpack("<I", c)[0]


@dataclass
class ResourceEntry:
    type_id: int
    res_id: int
    res_offset: int
    res_length: int

    @property
    def type(self):
        return KnownResourceTypes.get_type_name(self.type_id)


def read_ne_resource_table(res_table_stream):
    align_shift = read_u16(res_table_stream)
    while True:
        type_id = read_u16(res_table_stream)
        if type_id == 0:
            break
        assert type_id & 0x8000  # no support for string offsets right now
        type_id &= 0x7FFF
        count = read_u16(res_table_stream)
        reserved = read_u32(res_table_stream)
        for i in range(count):
            res_offset = read_u16(res_table_stream) * (1 << align_shift)
            res_length = read_u16(res_table_stream) * (1 << align_shift)
            res_flags = read_u16(res_table_stream)
            res_id = read_u16(res_table_stream)
            res_handle = read_u16(res_table_stream)
            res_usage = read_u16(res_table_stream)
            assert res_id & 0x8000  # no support for string offsets right now
            yield ResourceEntry(
                type_id=type_id,
                res_id=res_id & 0x7FFF,
                res_offset=res_offset,
                res_length=res_length,
            )
    # TODO: read rscResourceNames here if required


def read_ne_resources(exe):
    signature = exe.read(2)
    if signature == b"MZ":
        ne_header_offset = 0x480  # TODO: should read this from the MZ header really
    else:
        ne_header_offset = 0
    exe.seek(ne_header_offset)
    assert exe.read(2) == b"NE"
    exe.seek(ne_header_offset + 0x24)
    res_table_off = read_u16(exe)
    exe.seek(ne_header_offset + res_table_off)
    resource_entries = list(read_ne_resource_table(exe))
    for re in resource_entries:
        exe.seek(re.res_offset)
        data = exe.read(re.res_length)
        assert len(data) == re.res_length
        yield (re, data)


def main():
    with open("./excel5.exe", "rb") as infp:
        for re in read_ne_resources(infp):
            print(re)


if __name__ == "__main__":
    main()
