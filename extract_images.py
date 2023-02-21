import argparse
import io
import logging
import os
import sys

from pe_tools import KnownResourceTypes
from PIL import Image

from res_extract import icons as libicons
from res_extract.errors import ParseError
from res_extract.resources import get_resources_from_file

log = logging.getLogger(__name__)


def extract_images(
    *,
    dest_dir: str,
    source_file,
    extract_ico: bool,
    extract_png: bool,
    name_prefix: str = "",
    log_prefix: str,
):
    resources = list(get_resources_from_file(source_file))
    image_resources = [
        r for r in resources if r.type_id in (KnownResourceTypes.RT_BITMAP,)
    ]
    for r in image_resources:
        # Here's hoping DibImageFile can handle this!
        img = Image.open(io.BytesIO(r.data))
        img.load()
        if extract_png:
            png_path = os.path.join(dest_dir, f"{name_prefix}bmp_{r.filename_part}.png")
            img.save(png_path)
            print(log_prefix, "=>", png_path)

    for r, ico_data in libicons.extract_icons(resources):
        ico_prefix = f"{name_prefix}ico_{r.filename_part}"
        if extract_ico:
            ico_path = os.path.join(dest_dir, f"{ico_prefix}.ico")
            with open(ico_path, "wb") as outf:
                outf.write(ico_data)
                print(log_prefix, "=>", outf.name)

        if extract_png:
            img = Image.open(io.BytesIO(ico_data))
            for size in img.info["sizes"]:
                w, h = size
                img.size = size
                img.load()
                png_path = os.path.join(dest_dir, f"{ico_prefix}_{w}x{h}.png")
                img.save(png_path)
                print(log_prefix, "=>", png_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="+")
    ap.add_argument("-d", "--dir", required=True)
    ap.add_argument("--continue-on-errors", default=False, action="store_true")
    ap.add_argument("--ico", default=False, action="store_true")
    ap.add_argument("--png", default=False, action="store_true")
    ap.add_argument("--process-images", default=False, action="store_true")
    ap.add_argument("--debug", default=False, action="store_true")
    args = ap.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    dest_dir = args.dir
    os.makedirs(dest_dir, exist_ok=True)
    if not (args.ico or args.png):
        print("Warning: neither --ico nor --png specified, nothing will be extracted")
    for source_file in args.file:
        success = False
        if os.path.getsize(source_file) == 0:
            log.warning("%s: empty file", source_file)
            continue
        try:
            with open(source_file, "rb") as fin:
                extract_images(
                    dest_dir=dest_dir,
                    source_file=fin,
                    extract_ico=args.ico,
                    extract_png=args.png,
                    name_prefix=(
                        f"{os.path.basename(source_file)}_"
                        if len(args.file) > 1
                        else ""
                    ),
                    log_prefix=source_file,
                )
                success = True
        except ParseError as exc:
            log.warning("%s: %s", source_file, exc)
        except Exception:
            if args.continue_on_errors:
                log.exception(f"Failed extracting from {source_file}", exc_info=True)
            else:
                print("Error while extracting", source_file, file=sys.stderr)
                raise
        if not success and args.process_images:
            try:
                im = Image.open(source_file)
                im.load()
                if args.png:
                    dest_file = os.path.join(
                        dest_dir,
                        os.path.basename(source_file) + ".png",
                    )
                    im.save(dest_file)
                    print(
                        f"Image {source_file} ({im.size} {im.format}) converted to {dest_file}",
                    )
            except Exception as exc:
                log.warning("%s: not an image either: %s", source_file, exc)


if __name__ == "__main__":
    main()
