import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps
import imagehash

import trim_misc_hashes
import trim_solid_color_matches

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}


# Precomputed so check_package.py can match a package image's single hash
# against every rotation/flip of a reference texture without re-deriving
# orientations at query time.
def orientation_variants(img):
    variants = {}
    for deg in (0, 90, 180, 270):
        rotated = img.rotate(deg, expand=True) if deg else img
        variants[f"rot{deg}"] = rotated
        variants[f"rot{deg}_flip"] = ImageOps.mirror(rotated)
    return variants


def main():
    parser = argparse.ArgumentParser(
        description="Compute perceptual hashes, phash and dhash, for every image in a texture "
                     "directory, across all 8 rotate/flip orientations, and write them to a "
                     "JSON database, for later comparison with check_package.py. By default also "
                     "trims noisy/not-comparable paths and near-solid-color entries, by calling "
                     "trim_misc_hashes.trim_entries() and trim_solid_color_matches.trim_entries()."
    )
    parser.add_argument("textures_dir", help="directory to scan recursively for png/jpg/jpeg/tga/bmp files")
    parser.add_argument("output_json", help="path to write the resulting hash database as JSON")
    parser.add_argument("--pack-name", default=None, help="name recorded in the database, default: textures_dir name")

    parser.add_argument("--no-trim-misc", action="store_true",
                         help="disable the misc-path trim (font/, gui/, trims/entity/, etc. by default)")
    parser.add_argument("--exclude", action="append", default=None,
                         help="directory name to exclude (path component match, repeatable, matches at "
                              f"any depth). Default: {sorted(trim_misc_hashes.DEFAULT_EXCLUDE_DIRS)}")
    parser.add_argument("--exclude-path", action="append", default=None,
                         help="relative subpath to exclude (repeatable), matched at any depth. "
                              f"Default: {trim_misc_hashes.DEFAULT_EXCLUDE_PATHS}")
    parser.add_argument("--exclude-file", action="append", default=None,
                         help="relative file path suffix to exclude (repeatable). "
                              f"Default: {trim_misc_hashes.DEFAULT_EXCLUDE_FILES}")

    parser.add_argument("--no-trim-solid", action="store_true",
                         help="disable the solid-color trim against --solid-refs-dir")
    parser.add_argument("--solid-refs-dir", default=str(trim_solid_color_matches.DEFAULT_REFS_DIR),
                         help=f"directory of flat/solid reference swatches to trim against. Default: {trim_solid_color_matches.DEFAULT_REFS_DIR}")
    parser.add_argument("--solid-threshold", type=float, default=4,
                         help="max combined phash/dhash distance (exclusive) to count as a solid-color "
                              "match. Default: 4 (near-exact only)")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    src = Path(args.textures_dir)
    pack_name = args.pack_name or src.name

    entries = []
    for path in sorted(src.rglob("*")):
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            print(f"skip {path}: {e}", file=sys.stderr)
            continue

        hashes = {}
        for name, variant in orientation_variants(img).items():
            hashes[name] = {
                "phash": str(imagehash.phash(variant, hash_size=16)),
                "dhash": str(imagehash.dhash(variant, hash_size=16)),
            }

        entries.append({
            "path": str(path.relative_to(src)),
            "width": img.width,
            "height": img.height,
            "hashes": hashes,
        })

    total = len(entries)

    if not args.no_trim_misc:
        exclude_dirs = set(args.exclude) if args.exclude else set(trim_misc_hashes.DEFAULT_EXCLUDE_DIRS)
        exclude_paths = args.exclude_path if args.exclude_path is not None else list(trim_misc_hashes.DEFAULT_EXCLUDE_PATHS)
        exclude_files = args.exclude_file if args.exclude_file is not None else list(trim_misc_hashes.DEFAULT_EXCLUDE_FILES)
        entries, removed = trim_misc_hashes.trim_entries(entries, exclude_dirs, exclude_paths, exclude_files)
        print(f"trim-misc: removed {len(removed)} of {total} entries", file=sys.stderr)

    if not args.no_trim_solid:
        before = len(entries)
        refs = trim_solid_color_matches.load_reference_hashes(args.solid_refs_dir)
        if not refs:
            print(f"no solid reference images found in {args.solid_refs_dir}, skipping solid trim", file=sys.stderr)
        else:
            entries, removed = trim_solid_color_matches.trim_entries(entries, refs, args.solid_threshold)
            print(f"trim-solid: removed {len(removed)} of {before} entries", file=sys.stderr)

    with open(args.output_json, "w") as f:
        json.dump({"pack_name": pack_name, "entries": entries}, f, indent=2)

    print(f"wrote {len(entries)} entries to {args.output_json}")


if __name__ == "__main__":
    main()
