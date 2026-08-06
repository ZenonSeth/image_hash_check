import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps
import imagehash

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
                     "JSON database, for later comparison with check_package.py."
    )
    parser.add_argument("textures_dir", help="directory to scan recursively for png/jpg/jpeg/tga/bmp files")
    parser.add_argument("output_json", help="path to write the resulting hash database as JSON")
    parser.add_argument("--pack-name", default=None, help="name recorded in the database, default: textures_dir name")

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
                "phash": str(imagehash.phash(variant)),
                "dhash": str(imagehash.dhash(variant)),
            }

        entries.append({
            "path": str(path.relative_to(src)),
            "width": img.width,
            "height": img.height,
            "hashes": hashes,
        })

    with open(args.output_json, "w") as f:
        json.dump({"pack_name": pack_name, "entries": entries}, f, indent=2)

    print(f"wrote {len(entries)} entries to {args.output_json}")


if __name__ == "__main__":
    main()
