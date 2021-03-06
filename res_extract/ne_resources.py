"""
Read resource entries from NE binaries.
"""
import logging
import struct
from dataclasses import dataclass

from pe_tools import KnownResourceTypes

from res_extract.resources import ResourceEntry

log = logging.getLogger(__name__)


class NotNEFile(ValueError):
    pass


def read_u16(s):
    c = s.read(2)
    return struct.unpack("<H", c)[0]


def read_u32(s):
    c = s.read(4)
    return struct.unpack("<I", c)[0]


@dataclass
class NEResourceEntry:
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
        count = read_u16(res_table_stream)
        reserved = read_u32(res_table_stream)
        for i in range(count):
            res_offset = read_u16(res_table_stream) * (1 << align_shift)
            res_length = read_u16(res_table_stream) * (1 << align_shift)
            res_flags = read_u16(res_table_stream)
            res_id = read_u16(res_table_stream)
            res_handle = read_u16(res_table_stream)
            res_usage = read_u16(res_table_stream)

            # Do these skips here so we read the table correctly without needing to seek
            if not type_id & 0x8000:
                log.warning(f"skipping resource with string-offset type ID {type_id}")
                continue
            if not res_id & 0x8000:
                log.warning(
                    f"skipping resource of type {type_id} with string-offset ID {res_id}"
                )
                continue
            yield NEResourceEntry(
                type_id=(type_id & 0x7FFF),
                res_id=(res_id & 0x7FFF),
                res_offset=res_offset,
                res_length=res_length,
            )
    # TODO: read rscResourceNames here if required


def read_ne_resources(exe):
    signature = exe.read(2)
    if signature == b"MZ":
        # If the word value at offset 18h is 40h or greater, the word
        # value at 3Ch is typically an offset to a Windows header.
        exe.seek(0x18)
        word_18 = read_u16(exe)
        if word_18 >= 0x40:
            exe.seek(0x3C)
            ne_header_offset = read_u16(exe)
        else:
            ne_header_offset = 0x480  # Just a guess!
    else:
        raise NotNEFile(
            f"{exe} doesn't look like a NE file (initial MZ signature is {signature!r})"
        )
    exe.seek(ne_header_offset)
    ne_magic = exe.read(2)
    if ne_magic != b"NE":
        raise NotNEFile(
            f"{exe} doesn't look like a NE file (magic {ne_magic!r} not 'NE')"
        )
    exe.seek(ne_header_offset + 0x24)
    res_table_off = read_u16(exe)
    exe.seek(ne_header_offset + res_table_off)
    resource_entries = list(read_ne_resource_table(exe))
    for re in resource_entries:
        exe.seek(re.res_offset)
        data = exe.read(re.res_length)
        assert len(data) == re.res_length
        yield ResourceEntry(type_id=re.type_id, res_id=re.res_id, lang_id=0, data=data)


def main():
    with open("./excel5.exe", "rb") as infp:
        for re in read_ne_resources(infp):
            print(re)


if __name__ == "__main__":
    main()
