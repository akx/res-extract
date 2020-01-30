from PIL import Image
from pe_tools import parse_pe
from pe_tools.rsrc import KnownResourceTypes
from pe_tools.struct3 import Struct3, u16, u8, u32
import grope
import os
import argparse
import io
from pprint import pprint

# H/T https://docs.microsoft.com/en-us/previous-versions/ms997538(v=msdn.10)?redirectedfrom=MSDN
# H/T https://devblogs.microsoft.com/oldnewthing/20101019-00/?p=12503
# H/T https://devblogs.microsoft.com/oldnewthing/20120720-00/?p=7083
from ne_resources import read_ne_resources


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


def get_pe_resource_data(resources, type):
    for id, lang_to_res in resources.get(type, {}).items():
        for lang, data in lang_to_res.items():
            yield ((id, lang), bytes(data))


def get_pe_icon_resources(pe):
    resources = pe.parse_resources()
    icon_groups = dict(
        get_pe_resource_data(resources, KnownResourceTypes.RT_GROUP_ICON)
    )
    icon_datas = dict(get_pe_resource_data(resources, KnownResourceTypes.RT_ICON))
    return (icon_datas, icon_groups)


def get_ne_icon_resources(fin):
    ner = list(read_ne_resources(fin))
    icon_groups = {
        (re.res_id, 0): data
        for (re, data) in ner
        if re.type_id == KnownResourceTypes.RT_GROUP_ICON
    }
    icon_datas = {
        (re.res_id, 0): data
        for (re, data) in ner
        if re.type_id == KnownResourceTypes.RT_ICON
    }
    return (icon_datas, icon_groups)


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


def get_icon_resources(fin):
    try:
        pe = parse_pe(grope.wrap_io(fin))
    except RuntimeError as rte:
        if "Not a PE file" in str(rte):
            pe = None
        else:
            raise

    if pe:
        return get_pe_icon_resources(pe)
    # Assume NE then...
    fin.seek(0)
    return get_ne_icon_resources(fin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--ico", default=False, action="store_true")
    ap.add_argument("--png", default=False, action="store_true")
    args = ap.parse_args()
    os.makedirs(args.dir, exist_ok=True)

    with open(args.file, "rb") as fin:
        icon_datas, icon_groups = get_icon_resources(fin)

    for (gid, lang), data in icon_groups.items():
        header = GRPICONDIR.unpack_from(data)
        print(gid, lang, header)
        dents_and_datas = []
        for i in range(header.idCount):
            offset = 6 + i * GRPICONDIRENTRY.calcsize()
            entry = GRPICONDIRENTRY.unpack_from(data[offset:])
            print("  ", i, entry)
            idata = icon_datas[(entry.nId, lang)]
            assert len(idata) >= entry.dwBytesInRes, (len(idata),)
            dents_and_datas.append((entry, idata[: entry.dwBytesInRes]))
        ico_data = reassemble_ico(dents_and_datas)
        if args.ico:
            ico_path = os.path.join(args.dir, f"{gid}_{lang}.ico")
            with open(ico_path, "wb") as outf:
                outf.write(ico_data)
                print("=>", outf.name)
        if args.png:
            img = Image.open(io.BytesIO(ico_data))
            for size in img.info["sizes"]:
                w, h = size
                img.size = size
                img.load()
                png_path = os.path.join(args.dir, f"{gid}_{lang}_{w}x{h}.png")
                img.save(png_path)
                print("=>", png_path)


if __name__ == "__main__":
    main()
