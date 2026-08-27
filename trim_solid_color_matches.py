import argparse
import json
import sys
from pathlib import Path

from PIL import Image
import imagehash

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}
DEFAULT_REFS_DIR = Path(__file__).parent / "sample_colors"


def hamming(hex_a, hex_b):
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")


# Same weighting check_package.py uses for real match scoring, so "close enough
# to trim" means the same thing as "close enough to have been flagged".
def combined_distance(phash_dist, dhash_dist):
    smaller, larger = (phash_dist, dhash_dist) if phash_dist <= dhash_dist else (dhash_dist, phash_dist)
    return (2 * smaller + larger) / 3


def load_reference_hashes(refs_dir):
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


def main():
    parser = argparse.ArgumentParser(
        description="Trim a reference hash database (as built by build_ref_hash.py) of entries "
                     "that are near-exact matches to flat/solid reference swatches (solid colors, "
                     "transparent, etc.). Flat textures like white_terracotta.png otherwise match "
                     "against any package image that happens to be a similar flat color, wasting "
                     "reviewer time on noise rather than real reused-texture leads."
    )
    parser.add_argument("input_json", help="hash database JSON to trim (as produced by build_ref_hash.py)")
    parser.add_argument(
        "-o", "--output", default=None,
        help="path to write the trimmed database. Default: <input>_trimmed.json. Ignored with --dry-run"
    )
    parser.add_argument(
        "--refs-dir", default=str(DEFAULT_REFS_DIR),
        help=f"directory of flat/solid reference swatches to trim against. Default: {DEFAULT_REFS_DIR}"
    )
    parser.add_argument(
        "--threshold", type=float, default=4,
        help="max combined phash/dhash distance (exclusive) to count as a solid-color match, using "
             "the same (2*lower + higher)/3 weighting check_package.py uses for real matches. "
             "Default: 4 (near-exact only)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would be removed without writing an output file"
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    with open(args.input_json) as f:
        db = json.load(f)

    refs = load_reference_hashes(args.refs_dir)
    if not refs:
        print(f"no reference images found in {args.refs_dir}", file=sys.stderr)
        sys.exit(1)

    kept = []
    removed = []
    for entry in db.get("entries", []):
        base = entry["hashes"].get("rot0")
        if base is None:
            kept.append(entry)
            continue
        match = solid_match(base, refs, args.threshold)
        if match:
            ref_name, dist, phash_dist, dhash_dist = match
            removed.append((entry["path"], ref_name, dist, phash_dist, dhash_dist))
        else:
            kept.append(entry)

    for path, ref_name, dist, phash_dist, dhash_dist in removed:
        print(f"remove: {path}  (matches {ref_name}, dist={dist:.2f}, phash_dist={phash_dist} dhash_dist={dhash_dist})")

    total = len(db.get("entries", []))
    print(f"\n{len(removed)} of {total} entries match a solid reference (threshold<{args.threshold}); "
          f"{len(kept)} kept")

    if args.dry_run:
        print("dry-run: no file written")
        return

    output_path = Path(args.output) if args.output else Path(args.input_json).with_name(
        Path(args.input_json).stem + "_trimmed.json"
    )
    db["entries"] = kept
    with open(output_path, "w") as f:
        json.dump(db, f, indent=2)
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
