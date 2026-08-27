import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image
import imagehash

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}

# This tool surfaces *possible* matches for a human reviewer to judge, so it
# leans toward over-reporting rather than silently dropping anything that
# might be a renamed/edited/rotated reuse. Tiers are upper-bound hamming
# distances, can be tunned
TIERS = [
    (0, "exact"),
    (6, "strong"),
    (12, "possible"),
    (20, "weak"),
]


def tier_for(dist):
    for bound, name in TIERS:
        if dist <= bound:
            return name
    return "outlier"


def load_db(path):
    with open(path) as f:
        data = json.load(f)
    return data["pack_name"], data["entries"]


# Weighted toward whichever of phash/dhash agrees more, but still pulled up
# somewhat by the one that disagrees, so a single-hash coincidence doesn't
# score identically to a true exact match. The 2:1 weighting is a subjective
# call, leaning toward surfacing more false positives than risking a missed
# real reuse, since a human reviewer judges the flagged list anyway.
def combined_distance(pd, dd):
    smaller, larger = (pd, dd) if pd <= dd else (dd, pd)
    return (2 * smaller + larger) / 3


def best_match(phash, dhash, entry):
    best = None
    for transform, hashes in entry["hashes"].items():
        pd = phash - imagehash.hex_to_hash(hashes["phash"])
        dd = dhash - imagehash.hex_to_hash(hashes["dhash"])
        dist = combined_distance(pd, dd)
        if best is None or dist < best[0]:
            best = (dist, transform, pd, dd)
    return best


def main():
    parser = argparse.ArgumentParser(
        description="Check a mod/game/texture pack's images against one or more reference hash "
                     "databases, built with build_ref_hash.py, and report close matches, which may "
                     "indicate reused/renamed/rotated/flipped textures from another package. This is "
                     "a lead-generation tool for a human reviewer, not a verdict - it favors flagging "
                     "low-confidence matches over missing real reuse."
    )
    parser.add_argument("-p", "--package", required=True, help="directory of the extracted package to scan")
    parser.add_argument("-d", "--db", nargs="+", required=True, help="one or more hash database JSON files to check against")
    tier_names = [name for _, name in TIERS]
    parser.add_argument("-c", "--confidence", choices=tier_names, default="possible",
                         help=f"lowest-confidence tier to report, one of {tier_names}. Matches at or above "
                              f"this tier's confidence, i.e. hamming distance at or below its bound, are "
                              f"printed. Default: possible ({TIERS[2][0]})")
    parser.add_argument("--threshold", type=int, default=None,
                         help="max hamming distance to report as a match, overrides --confidence when set")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.threshold is None:
        args.threshold = next(bound for bound, name in TIERS if name == args.confidence)

    dbs = [load_db(p) for p in args.db]

    pkg_dir = Path(args.package)
    results = []
    for path in sorted(pkg_dir.rglob("*")):
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            print(f"skip {path}: {e}", file=sys.stderr)
            continue
        phash = imagehash.phash(img)
        dhash = imagehash.dhash(img)

        for pack_name, entries in dbs:
            for entry in entries:
                dist, transform, pd, dd = best_match(phash, dhash, entry)
                if dist <= args.threshold:
                    tier = tier_for(dist)
                    results.append((dist, tier, str(path.relative_to(pkg_dir)), pack_name, entry["path"], transform, pd, dd))

    by_pkg_path = defaultdict(list)
    for dist, tier, pkg_path, pack_name, ref_path, transform, pd, dd in results:
        by_pkg_path[pkg_path].append((dist, tier, pack_name, ref_path, transform, pd, dd))

    for i, pkg_path in enumerate(sorted(by_pkg_path)):
        if i:
            print()
        print(pkg_path)
        for dist, tier, pack_name, ref_path, transform, pd, dd in sorted(by_pkg_path[pkg_path]):
            orientation = "" if transform == "rot0" else f" [{transform}]"
            print(f"- {tier} ({dist:.1f}): {pack_name}:{ref_path}{orientation}  (phash={pd} dhash={dd})")

    if not results:
        print("no matches found")


if __name__ == "__main__":
    main()
