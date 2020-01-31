import argparse
import io
import logging
import os

from PIL import Image

from res_extract import icons as libicons

log = logging.getLogger(__name__)


def extract_icons(
    *,
    dest_dir: str,
    source_file,
    extract_ico: bool,
    extract_png: bool,
    name_prefix: str = "",
):
    for r, ico_data in libicons.extract_icons(source_file=source_file):
        if extract_ico:
            ico_path = os.path.join(
                dest_dir, f"{name_prefix}{r.res_id}_{r.lang_id}.ico"
            )
            with open(ico_path, "wb") as outf:
                outf.write(ico_data)
                print("=>", outf.name)

        if extract_png:
            img = Image.open(io.BytesIO(ico_data))
            for size in img.info["sizes"]:
                w, h = size
                img.size = size
                img.load()
                png_path = os.path.join(
                    dest_dir, f"{name_prefix}{r.res_id}_{r.lang_id}_{w}x{h}.png"
                )
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
                    name_prefix=(
                        f"{os.path.basename(source_file)}_"
                        if len(args.file) > 1
                        else ""
                    ),
                )
        except Exception:
            if args.continue_on_errors:
                log.exception(f"Failed extracting from {source_file}", exc_info=True)
            else:
                raise


if __name__ == "__main__":
    main()
