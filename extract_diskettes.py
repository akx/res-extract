import argparse
import os
import shutil
import sys

from fs import open_fs


def main():
    ap = argparse.ArgumentParser(
        description="extract diskette images into a directory using pyfatfs",
    )
    ap.add_argument("image", nargs="+")
    ap.add_argument("-d", "--dir", required=True, help="output directory")
    args = ap.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    for image_filename in args.image:
        with open_fs(f"fat://{image_filename}") as fs:
            for file in fs.walk.files():
                dest_path = os.path.join(args.dir, file.removeprefix("/"))
                with fs.open(file, "rb") as inf:
                    with open(dest_path, "wb") as outf:
                        shutil.copyfileobj(inf, outf)
                        print(
                            f"{image_filename}#{file} => {dest_path}, {outf.tell()} bytes",
                            file=sys.stderr,
                        )
                    try:
                        fi = fs.getinfo(file)
                        os.utime(dest_path, (fi.modified, fi.modified))
                    except Exception:
                        pass


if __name__ == "__main__":
    main()
