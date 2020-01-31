import argparse
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(
        description="extract diskette images into a directory using the mtools package",
    )
    ap.add_argument("image", nargs="+")
    ap.add_argument("-d", "--dir", required=True, help="output directory")
    args = ap.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    for image_filename in args.image:
        print(image_filename, file=sys.stderr)
        subprocess.check_call(
            [
                "/usr/bin/env",  # todo: not portable
                "mcopy",
                "-i",  # using image
                image_filename,
                "-s",  # recursive
                "-m",  # copy mtimes
                "-p",  # copy attributes
                "::",  # everything from disk root
                args.dir,  # to the target directory
            ]
        )


if __name__ == "__main__":
    main()
