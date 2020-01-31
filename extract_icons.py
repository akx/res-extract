import logging

from PIL import Image
from pe_tools import parse_pe
from pe_tools.rsrc import KnownResourceTypes
from pe_tools.struct3 import Struct3, u16, u8, u32
import grope
import os
import argparse
import io
from ne_resources import read_ne_resources

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


def extract_icons(
    *,
    dest_dir: str,
    source_file,
    extract_ico: bool,
    extract_png: bool,
    name_prefix: str = "",
):
    icon_datas, icon_groups = get_icon_resources(source_file)
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

        if extract_ico:
            ico_path = os.path.join(dest_dir, f"{name_prefix}{gid}_{lang}.ico")
            with open(ico_path, "wb") as outf:
                outf.write(ico_data)
                print("=>", outf.name)

        if extract_png:
            img = Image.open(io.BytesIO(ico_data))
            for size in img.info["sizes"]:
                w, h = size
                img.size = size
                img.load()
                png_path = os.path.join(dest_dir, f"{name_prefix}{gid}_{lang}_{w}x{h}.png")
                img.save(png_path)
                print("=>", png_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="+")
    ap.add_argument("-d", "--dir", required=True)
    ap.add_argument("--continue-on-errors", default=False, action="store_true")
    ap.add_argument("--ico", default=False, action="store_true")
    ap.add_argument("--png", default=False, action="store_true")
    args = ap.parse_args()
    dest_dir = args.dir
    os.makedirs(dest_dir, exist_ok=True)
    for source_file in args.file:
        print(source_file)
        try:
            with open(source_file, "rb") as fin:
                extract_icons(
                    dest_dir=dest_dir,
                    source_file=fin,
                    extract_ico=args.ico,
                    extract_png=args.png,
                    name_prefix=(f"{os.path.basename(source_file)}_" if len(args.file) > 1 else ''),
                )
        except Exception:
            if args.continue_on_errors:
                log.exception(f'Failed extracting from {source_file}', exc_info=True)
            else:
                raise


if __name__ == "__main__":
    main()
