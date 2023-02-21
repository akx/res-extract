import argparse
import collections
import io
import os
import shutil
import subprocess
import sys
import tempfile


def main():
    ap = argparse.ArgumentParser(
        description="extract Microsoft legacy compressed files (using msexpand)",
    )
    ap.add_argument("--in-dir", required=True, help="input directory")
    ap.add_argument(
        "--legacy-inf",
        help="(try to) read a legacy setup.inf file (e.g. excel 5) to guess true file extensions",
    )
    ap.add_argument("--out-dir", required=False, help="output directory")
    args = ap.parse_args()
    if not args.out_dir:
        args.out_dir = args.in_dir.rstrip(os.sep) + "_expanded"
    os.makedirs(args.out_dir, exist_ok=True)
    input_files = [
        sde
        for sde in os.scandir(args.in_dir)
        if sde.is_file() and sde.name.endswith("_")
    ]
    if not input_files:
        raise ValueError(f"No files found in {args.in_dir}")

    filename_map = {}  # destination <-> [scandir entries]
    if args.legacy_inf:
        input_filenames = {sde.name.lower(): sde for sde in input_files}
        with open(args.legacy_inf, "r") as f:
            parse_legacy_inf(filename_map, input_filenames, f)

    # TODO: add support for no filename_map (i.e. guess from extensions)

    if not filename_map:
        raise NotImplementedError(
            "Support for _not_ reading an INF file is not yet around"
        )

    for dest_filename, source_sdes in sorted(filename_map.items()):
        dest_path = os.path.join(args.out_dir, dest_filename)
        print(dest_path, "<-", source_sdes)
        buf = io.BytesIO()
        for sde in source_sdes:
            with tempfile.NamedTemporaryFile(prefix="ms_compress_") as tf:
                subprocess.check_call(
                    [
                        "/usr/bin/env",  # todo: not portable
                        "msexpand",
                        sde.path,
                        tf.name,
                    ],
                )
                tf.seek(0)
                shutil.copyfileobj(tf, buf)

        with open(dest_path, "wb") as outf:
            buf.seek(0)
            shutil.copyfileobj(buf, outf)


def parse_legacy_inf(filename_map: dict, input_filenames: dict, fp):
    artifact_info = collections.defaultdict(list)
    group_name = None
    for line in fp:
        line = line.strip()
        if line.startswith("["):
            group_name = line.strip("[]")
            continue
        if not line.startswith('"'):
            continue
        if " = " not in line:
            continue
        artifact_name, bits = line.split(" = ", 1)
        bits = [(bit.strip() or None) for bit in bits.split(",")]
        if len(bits) == 1:
            continue
        artifact_name = artifact_name.strip('"')
        src_or_dest = bits[1]
        dest_or_none = bits[2]
        artifact_info[(group_name, artifact_name)].append((src_or_dest, dest_or_none))
    for key, infos in artifact_info.items():
        if len(infos) == 1:
            src_or_dest, dest_or_none = infos[0]
            source_file_guess = src_or_dest[:-1].lower() + "_"
            if source_file_guess in input_filenames:
                filename_map[src_or_dest] = [input_filenames[source_file_guess]]
            else:
                print("Legacy INF: unable to map source file for", key, src_or_dest)
        else:
            source_files = [s[0] for s in infos]
            dest_file = next((s[1] for s in infos if s[1]), None)
            if dest_file and all(sf in input_filenames for sf in source_files):
                filename_map[dest_file] = [input_filenames[sf] for sf in source_files]
            else:
                print(
                    "Legacy INF: unable to map source file for concatenation",
                    key,
                    infos,
                )


if __name__ == "__main__":
    main()
