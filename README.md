Resource extraction tools
=========================

All instructions assume you have successfully installed the requirements.

Requires Python 3.

Extract icons from a PE or NE file (.exe)
-----------------------------------------

```
python extract_icons.py /Volumes/OFFPRO_Z/EXCEL/EXCEL.EXE --png --ico --dir=./excel
```

will extract reconstituted ICO files as well as PNG files into `./excel`.

Extract (multiple) diskette images into a directory
---------------------------------------------------

Requires the `mtools` package (available in Homebrew and Apt).

```
python3 extract_diskettes.py excel_5_diskettes/*.img -d excel_5_diskette_contents/
```

will extract all files off the diskette images into `excel_5_diskette_contents`.



Expand Microsoft compressed data
--------------------------------

Requires `msextract` from [`libmspack`](https://github.com/kyz/libmspack/blob/master/libmspack/examples/msexpand.c)
to be on your path. (On macOS, that tool compiles without any fuss if you have `automake` and `autoconf` installed.)

```
python3 expand_ms_compress.py --in-dir excel_5_diskette_contents/ --legacy-inf=excel_5_diskette_contents/EXCEL5.INF --out-dir=excel_5_expanded
```

will expand all underscorey files from your (previously extracted) Excel 5 diskettes into `excel_5_expanded`.


