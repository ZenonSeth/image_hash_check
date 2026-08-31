import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image
import imagehash
import numpy

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}
DEFAULT_SOLID_REFS_DIR = Path(__file__).parent / "sample_colors"


def hash_to_int(h):
    return int.from_bytes(numpy.packbits(h.hash.flatten()).tobytes(), "big")


def hamming(a, b):
    return (a ^ b).bit_count()

# Profiling counters, gated behind --profile, printed at the end of main().
PROFILE_ENABLED = False
PROFILE_TIMES = defaultdict(float)
PROFILE_COUNTS = defaultdict(int)


def profile(label, fn, *args, **kwargs):
    if not PROFILE_ENABLED:
        return fn(*args, **kwargs)
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    PROFILE_TIMES[label] += time.perf_counter() - start
    PROFILE_COUNTS[label] += 1
    return result


def print_profile():
    print("\n--- profiling ---", file=sys.stderr)
    for label in sorted(PROFILE_TIMES, key=lambda l: -PROFILE_TIMES[l]):
        total = PROFILE_TIMES[label]
        count = PROFILE_COUNTS[label]
        per_call = (total / count * 1000) if count else 0.0
        print(f"{label}: {total:.3f}s total, {count} calls, {per_call:.4f}ms/call", file=sys.stderr)

# This tool surfaces *possible* matches for a human reviewer to judge, so it
# leans toward over-reporting rather than silently dropping anything that
# might be a renamed/edited/rotated reuse. Tiers are upper-bound hamming
# distances, can be tunned
TIERS = [
    (0, "exact"),
    (24, "strong"),
    (48, "possible"),
    (80, "weak"),
]


def tier_for(dist):
    for bound, name in TIERS:
        if dist <= bound:
            return name
    return "outlier"


def load_db(path):
    with open(path) as f:
        data = json.load(f)
    entries = data["entries"]
    # Parse hex hashes to ints once here instead of re-parsing per package image in best_match.
    for entry in entries:
        for hashes in entry["hashes"].values():
            hashes["phash"] = int(hashes["phash"], 16)
            hashes["dhash"] = int(hashes["dhash"], 16)
    return data["pack_name"], entries


# Weighted toward whichever of phash/dhash agrees more, but still pulled up
# somewhat by the one that disagrees, so a single-hash coincidence doesn't
# score identically to a true exact match. The 2:1 weighting is a subjective
# call, leaning toward surfacing more false positives than risking a missed
# real reuse, since a human reviewer judges the flagged list anyway.
def combined_distance(pd, dd):
    smaller, larger = (pd, dd) if pd <= dd else (dd, pd)
    return (2 * smaller + larger) / 3


# Same weighting as combined_distance above, used to decide if a package image
# is itself close to a flat/solid swatch (sample_colors), same logic as
# trim_solid_color_matches.py uses to trim solid entries out of the ref DBs.
def load_solid_refs(refs_dir):
    refs = []
    for path in sorted(Path(refs_dir).rglob("*")):
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        img = Image.open(path).convert("RGBA")
        phash = profile("phash_compute", imagehash.phash, img, hash_size=16)
        dhash = profile("dhash_compute", imagehash.dhash, img, hash_size=16)
        refs.append({"phash": hash_to_int(phash), "dhash": hash_to_int(dhash)})
    return refs


def is_solid(phash, dhash, solid_refs, threshold):
    start = time.perf_counter() if PROFILE_ENABLED else None
    found = False
    for ref in solid_refs:
        dist = combined_distance(hamming(phash, ref["phash"]), hamming(dhash, ref["dhash"]))
        if dist < threshold:
            found = True
            break
    if PROFILE_ENABLED:
        PROFILE_TIMES["solid_compare"] += time.perf_counter() - start
        PROFILE_COUNTS["solid_compare"] += 1
    return found


def best_match(phash, dhash, entry):
    start = time.perf_counter() if PROFILE_ENABLED else None
    best = None
    for transform, hashes in entry["hashes"].items():
        if PROFILE_ENABLED:
            hamming_start = time.perf_counter()
        pd = hamming(phash, hashes["phash"])
        dd = hamming(dhash, hashes["dhash"])
        if PROFILE_ENABLED:
            PROFILE_TIMES["hamming_distance"] += time.perf_counter() - hamming_start
            PROFILE_COUNTS["hamming_distance"] += 2

        dist = combined_distance(pd, dd)
        if best is None or dist < best[0]:
            best = (dist, transform, pd, dd)
    if PROFILE_ENABLED:
        PROFILE_TIMES["best_match"] += time.perf_counter() - start
        PROFILE_COUNTS["best_match"] += 1
    return best


def main():
    global PROFILE_ENABLED
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
    parser.add_argument("--solid-refs-dir", default=str(DEFAULT_SOLID_REFS_DIR),
                         help=f"directory of flat/solid reference swatches to skip package images against, "
                              f"same refs trim_solid_color_matches.py uses. Default: {DEFAULT_SOLID_REFS_DIR}")
    parser.add_argument("--solid-threshold", type=float, default=4,
                         help="max combined phash/dhash distance (exclusive) for a package image to be "
                              "treated as solid/flat and skipped entirely. Default: 4 (near-exact only)")
    parser.add_argument("--no-solid-skip", action="store_true",
                         help="disable the solid-color pre-filter and compare every image against the db(s)")
    parser.add_argument("--profile", action="store_true",
                         help="print timing/call-count profiling breakdown to stderr when done")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    PROFILE_ENABLED = args.profile
    wall_start = time.perf_counter() if PROFILE_ENABLED else None

    if args.threshold is None:
        args.threshold = next(bound for bound, name in TIERS if name == args.confidence)

    dbs = [profile("load_db", load_db, p) for p in args.db]

    solid_refs = [] if args.no_solid_skip else load_solid_refs(args.solid_refs_dir)
    if not args.no_solid_skip and not solid_refs:
        print(f"no solid reference images found in {args.solid_refs_dir}", file=sys.stderr)

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
        phash = hash_to_int(profile("phash_compute", imagehash.phash, img, hash_size=16))
        dhash = hash_to_int(profile("dhash_compute", imagehash.dhash, img, hash_size=16))

        if solid_refs and is_solid(phash, dhash, solid_refs, args.solid_threshold):
            continue

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

    if PROFILE_ENABLED:
        print(f"\ntotal wall time: {time.perf_counter() - wall_start:.3f}s", file=sys.stderr)
        print_profile()


if __name__ == "__main__":
    main()
