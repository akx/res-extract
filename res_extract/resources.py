from dataclasses import dataclass
from typing import Iterable

import grope
from pe_tools import KnownResourceTypes, parse_pe


@dataclass
class ResourceEntry:
    type_id: int
    res_id: int
    lang_id: int
    data: bytes

    @property
    def type(self):
        return KnownResourceTypes.get_type_name(self.type_id)


def get_resources_from_file(exe_fp) -> Iterable[ResourceEntry]:
    try:
        pe = parse_pe(grope.wrap_io(exe_fp))
    except RuntimeError as rte:
        if "Not a PE file" in str(rte):
            pe = None
        else:
            raise

    if pe:
        for type_id, resources_of_type_map in pe.parse_resources().items():
            for res_id, lang_to_res in resources_of_type_map.items():
                for lang, data in lang_to_res.items():
                    yield ResourceEntry(
                        type_id=type_id, res_id=res_id, lang_id=lang, data=bytes(data)
                    )
        return
    # Assume NE then...
    exe_fp.seek(0)
    from res_extract.ne_resources import read_ne_resources

    yield from read_ne_resources(exe_fp)
