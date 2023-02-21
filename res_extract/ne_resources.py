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


class BadResourceTable(ValueError):
    pass


def read_u8(s) -> int:
    c = s.read(1)
    return struct.unpack("<B", c)[0]


def read_u16(s) -> int:
    c = s.read(2)
    return struct.unpack("<H", c)[0]


def read_u32(s) -> int:
    c = s.read(4)
    return struct.unpack("<I", c)[0]


@dataclass
class NEHeader:
    ne_magic: bytes
    linker_version: int
    linker_revision: int
    entry_table_offset: int
    entry_table_length: int
    file_checksum: int
    prog_flags: int
    appl_flags: int
    auto_data_segment: int
    initial_heap_size: int
    initial_stack_size: int
    entry_point: int
    initial_stack_pointer: int
    segment_count: int
    module_reference_count: int
    non_resident_name_table_size: int
    segment_table_offset: int
    resource_table_offset: int
    resident_name_table_offset: int
    module_reference_table_offset: int
    imported_names_table_offset: int
    non_resident_name_table_offset: int
    movable_entry_point_count: int
    file_alignment_shift_count: int
    resource_table_entries: int
    target_os: int
    other_flags: int
    ret_thunk_offset: int
    seg_ref_thunk_offset: int
    min_code_swap_size: int
    expected_win_version: int

    @classmethod
    def from_stream(cls, s):
        return cls(
            ne_magic=s.read(2),
            linker_version=read_u8(s),
            linker_revision=read_u8(s),
            entry_table_offset=read_u16(s),
            entry_table_length=read_u16(s),
            file_checksum=read_u32(s),
            prog_flags=read_u8(s),
            appl_flags=read_u8(s),
            auto_data_segment=read_u16(s),
            initial_heap_size=read_u16(s),
            initial_stack_size=read_u16(s),
            entry_point=read_u32(s),
            initial_stack_pointer=read_u32(s),
            segment_count=read_u16(s),
            module_reference_count=read_u16(s),
            non_resident_name_table_size=read_u16(s),
            segment_table_offset=read_u16(s),
            resource_table_offset=read_u16(s),
            resident_name_table_offset=read_u16(s),
            module_reference_table_offset=read_u16(s),
            imported_names_table_offset=read_u16(s),
            non_resident_name_table_offset=read_u32(s),
            movable_entry_point_count=read_u16(s),
            file_alignment_shift_count=read_u16(s),
            resource_table_entries=read_u16(s),
            target_os=read_u8(s),
            other_flags=read_u8(s),
            ret_thunk_offset=read_u16(s),
            seg_ref_thunk_offset=read_u16(s),
            min_code_swap_size=read_u16(s),
            expected_win_version=read_u16(s),
        )


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
    if align_shift > 31:
        raise BadResourceTable(
            f"NE resource table align_shift {align_shift} is suspiciously large"
        )
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
                log.debug(f"skipping resource with string-offset type ID {type_id}")
                continue
            if not res_id & 0x8000:
                log.debug(
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
    header = NEHeader.from_stream(exe)
    if header.ne_magic != b"NE":
        raise NotNEFile(
            f"{exe} doesn't look like a NE file (magic {header.ne_magic!r} not 'NE')"
        )
    exe.seek(ne_header_offset + header.resource_table_offset)
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
