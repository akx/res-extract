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


class GRPICONDIR(Struct3):
    idReserved: u16
    idType: u16
    idCount: u16


class GRPICONDIRENTRY(Struct3):
    bWidth: u8
    bHeight: u8
    bColorCount: u8
    bReserved: u8
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


def reassemble_ico(dents_and_datas) -> bytes:
    stream = io.BytesIO()
    header = GRPICONDIR(idReserved=0, idType=1, idCount=len(dents_and_datas))
    stream.write(header.pack())
    offsets = []
    offset = stream.tell() + len(dents_and_datas) * ICONDIRENTRY.calcsize()
    for gdent, _ in dents_and_datas:
        vs = vars(gdent).copy()
        vs.pop("nId")
        vs["dwImageOffset"] = offset
        offsets.append(offset)
        offset += vs["dwBytesInRes"]
        fdent = ICONDIRENTRY(**vs)
        stream.write(fdent.pack())
    for offset, (_, data) in zip(offsets, dents_and_datas):
        assert stream.tell() == offset  # sanity check
        stream.write(data)
    stream.flush()
    return stream.getvalue()


def extract_icons(resources: Iterable[ResourceEntry]):
    group_resources = []
    icon_resources = []
    for re in resources:
        if re.type_id == KnownResourceTypes.RT_GROUP_ICON:
            group_resources.append(re)
        elif re.type_id == KnownResourceTypes.RT_ICON:
            icon_resources.append(re)
    icon_datas = {(r.res_id, r.lang_id): r.data for r in icon_resources}
    for r in group_resources:
        ico_data = reassemble_ico_from_group_resource(r, icon_datas)
        yield (r, ico_data)


def reassemble_ico_from_group_resource(
    group_resource: ResourceEntry,
    icon_datas: dict,
) -> bytes:
    header = GRPICONDIR.unpack_from(group_resource.data)
    dents_and_datas = []
    for i in range(header.idCount):
        offset = 6 + i * GRPICONDIRENTRY.calcsize()
        entry = GRPICONDIRENTRY.unpack_from(group_resource.data[offset:])
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
    return reassemble_ico(dents_and_datas)
