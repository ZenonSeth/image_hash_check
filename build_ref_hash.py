import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps
import imagehash

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}
DEFAULT_SOLID_REFS_DIR = Path(__file__).parent / "sample_colors"
DEFAULT_EXCLUDE_DIRS = {"font", "gui"}
DEFAULT_EXCLUDE_PATHS = ["trims/entity", "trims/color_palettes"]
DEFAULT_EXCLUDE_FILES = ["misc/vignette.png", "misc/shadow.png", "misc/nausea.png", "misc/credits_vignette.png"]

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


# Same weighting check_package.py uses for real match scoring, so "close enough
# to trim" means the same thing as "close enough to have been flagged".
def combined_distance(phash_dist, dhash_dist):
    smaller, larger = (phash_dist, dhash_dist) if phash_dist <= dhash_dist else (dhash_dist, phash_dist)
    return (2 * smaller + larger) / 3


def hamming(hex_a, hex_b):
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")


def load_solid_refs(refs_dir):
    refs = []
    for path in sorted(Path(refs_dir).rglob("*")):
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        img = Image.open(path).convert("RGBA")
        refs.append({
            "name": path.name,
            "phash": str(imagehash.phash(img, hash_size=16)),
            "dhash": str(imagehash.dhash(img, hash_size=16)),
        })
    return refs


def solid_match(entry_hashes, refs, threshold):
    best = None
    for ref in refs:
        phash_dist = hamming(entry_hashes["phash"], ref["phash"])
        dhash_dist = hamming(entry_hashes["dhash"], ref["dhash"])
        dist = combined_distance(phash_dist, dhash_dist)
        if best is None or dist < best[1]:
            best = (ref["name"], dist, phash_dist, dhash_dist)
    if best and best[1] < threshold:
        return best
    return None


# Same dir-name / subpath matching split_atlas_frames.py uses when building
# full/, so a db built here follows the same exclusion rules.
def is_excluded_path(rel_path, exclude_dirs, exclude_paths, exclude_files):
    if any(part in exclude_dirs for part in rel_path.parts[:-1]):
        return True
    rel_str = rel_path.as_posix()
    for p in exclude_paths:
        if rel_str == p or rel_str.startswith(p + "/"):
            return True
        if rel_str.endswith("/" + p) or ("/" + p + "/") in rel_str:
            return True
    return any(rel_str == f or rel_str.endswith("/" + f) for f in exclude_files)


def trim_misc_paths(entries, exclude_dirs, exclude_paths, exclude_files):
    kept = []
    removed = 0
    for entry in entries:
        if is_excluded_path(Path(entry["path"]), exclude_dirs, exclude_paths, exclude_files):
            removed += 1
        else:
            kept.append(entry)
    return kept, removed


def trim_solid_colors(entries, refs_dir, threshold):
    refs = load_solid_refs(refs_dir)
    if not refs:
        print(f"no solid reference images found in {refs_dir}, skipping solid trim", file=sys.stderr)
        return entries, 0

    kept = []
    removed = 0
    for entry in entries:
        base = entry["hashes"].get("rot0")
        if base is not None and solid_match(base, refs, threshold):
            removed += 1
        else:
            kept.append(entry)
    return kept, removed


def main():
    parser = argparse.ArgumentParser(
        description="Compute perceptual hashes, phash and dhash, for every image in a texture "
                     "directory, across all 8 rotate/flip orientations, and write them to a "
                     "JSON database, for later comparison with check_package.py. By default also "
                     "trims noisy/not-comparable paths and near-solid-color entries, same as running "
                     "trim_misc_hashes.py and trim_solid_color_matches.py on the output afterwards."
    )
    parser.add_argument("textures_dir", help="directory to scan recursively for png/jpg/jpeg/tga/bmp files")
    parser.add_argument("output_json", help="path to write the resulting hash database as JSON")
    parser.add_argument("--pack-name", default=None, help="name recorded in the database, default: textures_dir name")

    parser.add_argument("--no-trim-misc", action="store_true",
                         help="disable the misc-path trim (font/, gui/, trims/entity/, etc. by default)")
    parser.add_argument("--exclude", action="append", default=None,
                         help="directory name to exclude (path component match, repeatable, matches at "
                              f"any depth). Default: {sorted(DEFAULT_EXCLUDE_DIRS)}")
    parser.add_argument("--exclude-path", action="append", default=None,
                         help="relative subpath to exclude (repeatable), matched at any depth. "
                              f"Default: {DEFAULT_EXCLUDE_PATHS}")
    parser.add_argument("--exclude-file", action="append", default=None,
                         help="relative file path suffix to exclude (repeatable). "
                              f"Default: {DEFAULT_EXCLUDE_FILES}")

    parser.add_argument("--no-trim-solid", action="store_true",
                         help="disable the solid-color trim against --solid-refs-dir")
    parser.add_argument("--solid-refs-dir", default=str(DEFAULT_SOLID_REFS_DIR),
                         help=f"directory of flat/solid reference swatches to trim against. Default: {DEFAULT_SOLID_REFS_DIR}")
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
        exclude_dirs = set(args.exclude) if args.exclude else set(DEFAULT_EXCLUDE_DIRS)
        exclude_paths = args.exclude_path if args.exclude_path is not None else list(DEFAULT_EXCLUDE_PATHS)
        exclude_files = args.exclude_file if args.exclude_file is not None else list(DEFAULT_EXCLUDE_FILES)
        entries, removed = trim_misc_paths(entries, exclude_dirs, exclude_paths, exclude_files)
        print(f"trim-misc: removed {removed} of {total} entries", file=sys.stderr)

    if not args.no_trim_solid:
        before = len(entries)
        entries, removed = trim_solid_colors(entries, args.solid_refs_dir, args.solid_threshold)
        print(f"trim-solid: removed {removed} of {before} entries", file=sys.stderr)

    with open(args.output_json, "w") as f:
        json.dump({"pack_name": pack_name, "entries": entries}, f, indent=2)

    print(f"wrote {len(entries)} entries to {args.output_json}")


if __name__ == "__main__":
    main()
