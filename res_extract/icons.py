import io
import logging
from collections.abc import Iterable

from pe_tools import Struct3, u8, u16, u32
from pe_tools.rsrc import KnownResourceTypes

from res_extract.resources import ResourceEntry

log = logging.getLogger(__name__)


# H/T https://docs.microsoft.com/en-us/previous-versions/ms997538(v=msdn.10)?redirectedfrom=MSDN
# H/T https://devblogs.microsoft.com/oldnewthing/20101019-00/?p=12503
# H/T https://devblogs.microsoft.com/oldnewthing/20120720-00/?p=7083
# H/T https://github.com/katahiromz/RisohEditor/blob/master/src/IconRes.cpp


class IconOrCursorHeader(Struct3):  # née GRPICONDIR
    idReserved: u16
    idType: u16
    idCount: u16


class ResourceIconDirEntry(Struct3):  # née GRPICONDIRENTRY
    bWidth: u8
    bHeight: u8
    bColorCount: u8
    bReserved: u8
    wPlanes: u16
    wBitCount: u16
    dwBytesInRes: u32
    nId: u16


class ResourceCursorDirEntry(Struct3):  # née GRPCURSORDIRENTRY
    bWidth: u16
    bHeight: u16
    wPlanes: u16
    wBitCount: u16
    dwBytesInRes: u32
    nId: u16


class ICONDIRENTRY(Struct3):
    bWidth: u8
    bHeight: u8
    bColorCount: u8
    bReserved: u8
    wPlanes: u16
    wBitCount: u16
    dwBytesInRes: u32
    dwImageOffset: u32


def reassemble_ico(dents_and_datas, idType: int, height_divisor: int = 1) -> bytes:
    stream = io.BytesIO()
    header = IconOrCursorHeader(
        idReserved=0, idType=idType, idCount=len(dents_and_datas)
    )
    stream.write(header.pack())
    offsets = []
    offset = stream.tell() + len(dents_and_datas) * ICONDIRENTRY.calcsize()
    for gdent, _ in dents_and_datas:
        vs = vars(gdent).copy()
        vs.pop("nId")
        vs["dwImageOffset"] = offset
        vs["bHeight"] //= height_divisor  # For cursors; the actual data may have a trailing 1-bit mask
        offsets.append(offset)
        offset += vs["dwBytesInRes"]
        fdent = ICONDIRENTRY(**vs)
        stream.write(fdent.pack())
    for offset, (_, data) in zip(offsets, dents_and_datas):
        assert stream.tell() == offset  # sanity check
        stream.write(data)
    stream.flush()
    return stream.getvalue()


def _assemble_group_resources(resources, assembler, data_type, group_type):
    group_resources = []
    icon_resources = []
    for re in resources:
        if re.type_id == group_type:
            group_resources.append(re)
        elif re.type_id == data_type:
            icon_resources.append(re)
    icon_datas = {(r.res_id, r.lang_id): r.data for r in icon_resources}
    for r in group_resources:
        yield (r, assembler(r, icon_datas))


def _reassemble_ico_from_group_resource(
    group_resource: ResourceEntry,
    icon_datas: dict,
) -> bytes:
    header = IconOrCursorHeader.unpack_from(group_resource.data)
    dents_and_datas = []
    for i in range(header.idCount):
        offset = 6 + i * ResourceIconDirEntry.calcsize()
        entry = ResourceIconDirEntry.unpack_from(group_resource.data[offset:])
        log.debug(
            "%s: header %s, %d/%d: %s",
            group_resource,
            header,
            i + 1,
            header.idCount,
            entry,
        )
        idata = icon_datas[(entry.nId, group_resource.lang_id)]
        assert len(idata) >= entry.dwBytesInRes, (len(idata),)
        dents_and_datas.append((entry, idata[: entry.dwBytesInRes]))
    return reassemble_ico(dents_and_datas, idType=header.idType)


def _reassemble_cur_from_group_resource(
    group_resource: ResourceEntry,
    cur_datas: dict,
) -> bytes:
    header = IconOrCursorHeader.unpack_from(group_resource.data)
    dents_and_datas = []
    for i in range(header.idCount):
        offset = 6 + i * ResourceCursorDirEntry.calcsize()
        entry = ResourceCursorDirEntry.unpack_from(group_resource.data[offset:])
        cdata = cur_datas[(entry.nId, group_resource.lang_id)]
        assert len(cdata) >= entry.dwBytesInRes, (len(cdata),)
        this_ent_data = cdata[: entry.dwBytesInRes]
        this_ent_data = this_ent_data[4:]  # Drop LOCALHEADER (4 bytes, hotspot x/y)
        dents_and_datas.append((entry, this_ent_data))
    return reassemble_ico(dents_and_datas, idType=header.idType, height_divisor=2)


def extract_icons(resources: Iterable[ResourceEntry]):
    return _assemble_group_resources(
        resources,
        assembler=_reassemble_ico_from_group_resource,
        data_type=KnownResourceTypes.RT_ICON,
        group_type=KnownResourceTypes.RT_GROUP_ICON,
    )


def extract_cursors(resources: Iterable[ResourceEntry]):
    return _assemble_group_resources(
        resources,
        assembler=_reassemble_cur_from_group_resource,
        data_type=KnownResourceTypes.RT_CURSOR,
        group_type=KnownResourceTypes.RT_GROUP_CURSOR,
    )
