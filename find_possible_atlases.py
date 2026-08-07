import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image

from split_atlas_frames import IMAGE_EXTS, DEFAULT_EXCLUDE_DIRS, is_excluded

DEFAULT_MIN_SIZE = 32


def is_handled_by_split(path, w, h):
    mcmeta = path.with_name(path.name + ".mcmeta")
    return mcmeta.exists() and h > w and h % w == 0 and h // w > 1


def main():
    parser = argparse.ArgumentParser(
        description="Scan a texture directory for images split_atlas_frames.py would NOT split or "
                     "exclude, but that are large enough to plausibly be an atlas/sprite sheet (e.g. "
                     "map_icons.png - a grid atlas with no .mcmeta sidecar to key off of). Copies "
                     "candidates into an output dir for manual review."
    )
    parser.add_argument("src_dir", help="source texture directory to scan recursively")
    parser.add_argument(
        "-o", "--output-dir", default=None,
        help="directory to copy candidates into. Default: <src_dir>/possible_atlas"
    )
    parser.add_argument(
        "--min-size", type=int, default=DEFAULT_MIN_SIZE,
        help=f"flag images whose width or height exceeds this. Default: {DEFAULT_MIN_SIZE}"
    )
    parser.add_argument(
        "--exclude", action="append", default=None,
        help="directory name to exclude (path component match, repeatable), same as "
             f"split_atlas_frames.py. Default: {sorted(DEFAULT_EXCLUDE_DIRS)}"
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    exclude_dirs = set(args.exclude) if args.exclude else set(DEFAULT_EXCLUDE_DIRS)

    src = Path(args.src_dir)
    out = Path(args.output_dir) if args.output_dir else src / "possible_atlas"

    flagged = 0
    for path in sorted(src.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue

        rel = path.relative_to(src)
        if is_excluded(rel, exclude_dirs) or out in path.parents:
            continue

        try:
            img = Image.open(path)
            w, h = img.size
        except Exception as e:
            print(f"skip {path}: {e}", file=sys.stderr)
            continue

        if max(w, h) <= args.min_size or is_handled_by_split(path, w, h):
            continue

        dest_dir = out / rel.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest_dir / path.name)
        flagged += 1

    print(f"flagged {flagged} candidate(s) into {out}")


if __name__ == "__main__":
    main()
