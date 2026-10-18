# MacOS-Like icons

The icon theme recommended by 0-ss/MacShell:
https://github.com/Scrimas/MacOS-Like
Pinned generator: efbc63d48d52bbaf52e9a70fb18e0d0c3c0719b2 (GPL-3.0-or-later).
Base artwork: https://github.com/vinceliuice/MacTahoe-icon-theme
Pinned base: 839848b9a8a38a92a6936e30c4abe35cc6f2546d (GPL-3.0).

The archive contains MacOS-Like-Light and MacOS-Like-Dark, generated for the
openSUSE test installation. Both include the base artwork and internal aliases;
uncovered applications inherit Adwaita and hicolor. Generated artwork and base
artwork keep their respective authors' copyright. The bundled setup.sh is the
unmodified pinned generator, provided as source for reproducing the theme.

To generate tiles for more installed applications, install the pinned MacTahoe
base, Pillow, rsvg-convert and rsync, then run setup.sh --source /path/to/MacTahoe.
The regular MacShell installer installs the prebuilt archive and needs none of
those build dependencies. Checksums are verified by scripts/icons.py.
