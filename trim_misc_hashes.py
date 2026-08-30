import argparse
import json
import sys
from pathlib import Path

DEFAULT_EXCLUDE_DIRS = {"font", "gui"}
DEFAULT_EXCLUDE_PATHS = ["trims/entity", "trims/color_palettes"]
# Matched by suffix, not exact path, since dbs vary in root prefix (e.g.
# assets/minecraft/textures/misc/vignette.png vs a flattened misc/vignette.png).
DEFAULT_EXCLUDE_FILES = ["misc/vignette.png", "misc/shadow.png", "misc/nausea.png", "misc/credits_vignette.png"]


# Same dir-name / subpath matching split_atlas_frames.py uses when building
# full/, so a db can be re-trimmed after the fact with the same rules.
def is_excluded(rel_path, exclude_dirs, exclude_paths, exclude_files):
    if any(part in exclude_dirs for part in rel_path.parts[:-1]):
        return True
    rel_str = rel_path.as_posix()
    for p in exclude_paths:
        if rel_str == p or rel_str.startswith(p + "/"):
            return True
        if rel_str.endswith("/" + p) or ("/" + p + "/") in rel_str:
            return True
    return any(rel_str == f or rel_str.endswith("/" + f) for f in exclude_files)


def main():
    parser = argparse.ArgumentParser(
        description="Trim a reference hash database (as built by build_ref_hash.py) of entries "
                     "under noisy/not-comparable paths - font/, gui/, trims/entity/ by default - "
                     "by path alone, without re-hashing. For use on hashesdb/hashdb_*.json; leave "
                     "the untrimmed full/hashdb_*.json alone so it can be re-trimmed from scratch."
    )
    parser.add_argument("input_json", help="hash database JSON to trim (as produced by build_ref_hash.py)")
    parser.add_argument(
        "-o", "--output", default=None,
        help="path to write the trimmed database. Default: <input>_trimmed.json. Ignored with --dry-run"
    )
    parser.add_argument(
        "--exclude", action="append", default=None,
        help="directory name to exclude (path component match, repeatable, matches at any depth "
             f"e.g. 'gui' matches gui/ and foo/gui/). Default: {sorted(DEFAULT_EXCLUDE_DIRS)}"
    )
    parser.add_argument(
        "--exclude-path", action="append", default=None,
        help="relative subpath to exclude (repeatable), e.g. 'trims/entity' - excludes that path "
             "and everything under it, matched at any depth (so it also works under a root prefix "
             f"like assets/minecraft/textures/), without matching 'entity' elsewhere. Default: {DEFAULT_EXCLUDE_PATHS}"
    )
    parser.add_argument(
        "--exclude-file", action="append", default=None,
        help="relative file path suffix to exclude (repeatable), e.g. 'misc/vignette.png' - matches "
             f"that exact file regardless of root prefix. Default: {DEFAULT_EXCLUDE_FILES}"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would be removed without writing an output file"
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    exclude_dirs = set(args.exclude) if args.exclude else set(DEFAULT_EXCLUDE_DIRS)
    exclude_paths = args.exclude_path if args.exclude_path is not None else list(DEFAULT_EXCLUDE_PATHS)
    exclude_files = args.exclude_file if args.exclude_file is not None else list(DEFAULT_EXCLUDE_FILES)

    with open(args.input_json) as f:
        db = json.load(f)

    kept = []
    removed = []
    for entry in db.get("entries", []):
        rel_path = Path(entry["path"])
        if is_excluded(rel_path, exclude_dirs, exclude_paths, exclude_files):
            removed.append(entry["path"])
        else:
            kept.append(entry)

    for path in removed:
        print(f"remove: {path}")

    total = len(db.get("entries", []))
    print(f"\n{len(removed)} of {total} entries under excluded paths "
          f"(dirs: {sorted(exclude_dirs)}, subpaths: {exclude_paths}, files: {exclude_files}); {len(kept)} kept")

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
