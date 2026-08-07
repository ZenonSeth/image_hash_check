import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}
DEFAULT_EXCLUDE_DIRS = {"font", "gui"}


def is_excluded(rel_path, exclude_dirs, exclude_paths=(), exclude_files=()):
    if any(part in exclude_dirs for part in rel_path.parts[:-1]):
        return True
    rel_str = rel_path.as_posix()
    if rel_str in exclude_files:
        return True
    return any(rel_str == p or rel_str.startswith(p + "/") for p in exclude_paths)


def split_frames(img, frame_size):
    frames = img.height // frame_size
    for i in range(frames):
        yield img.crop((0, i * frame_size, img.width, (i + 1) * frame_size))


def main():
    parser = argparse.ArgumentParser(
        description="Copy a texture directory into a cleaned-up output dir for build_ref_hash.py: "
                     "*.png.mcmeta-linked vertical animation strips into individual square frame "
                     "images, so atlases aren't hashed as a single distorted image."
    )
    parser.add_argument("src_dir", help="source texture directory to scan recursively")
    parser.add_argument("output_dir", help="directory to write the cleaned/split copy to")
    parser.add_argument(
        "--exclude", action="append", default=None,
        help="directory name to exclude (path component match, repeatable, matches at any depth "
             f"e.g. 'gui' matches gui/ and foo/gui/). Default: {sorted(DEFAULT_EXCLUDE_DIRS)}"
    )
    parser.add_argument(
        "--exclude-path", action="append", default=[],
        help="relative subpath to exclude (repeatable), e.g. 'trims/entity' - excludes that path "
             "and everything under it, without matching 'entity' elsewhere (unlike --exclude)"
    )
    parser.add_argument(
        "--exclude-file", action="append", default=[],
        help="exact relative file path to exclude (repeatable), e.g. 'misc/vignette.png'"
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    exclude_dirs = set(args.exclude) if args.exclude else set(DEFAULT_EXCLUDE_DIRS)

    src = Path(args.src_dir)
    out = Path(args.output_dir)

    copied = 0
    split = 0
    excluded = 0
    skipped_uneven = 0

    for path in sorted(src.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue

        rel = path.relative_to(src)
        if is_excluded(rel, exclude_dirs, args.exclude_path, args.exclude_file):
            excluded += 1
            continue

        dest_dir = out / rel.parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        mcmeta = path.with_name(path.name + ".mcmeta")
        if mcmeta.exists():
            try:
                img = Image.open(path)
                w, h = img.size
            except Exception as e:
                print(f"skip {path}: {e}", file=sys.stderr)
                continue

            if h > w and h % w == 0 and h // w > 1:
                for i, frame in enumerate(split_frames(img, w)):
                    frame.save(dest_dir / f"{path.stem}_frame{i}{path.suffix}")
                split += 1
                continue
            elif h != w:
                print(f"note: {rel} has .mcmeta but isn't an even vertical frame strip "
                      f"({w}x{h}) - copied as-is", file=sys.stderr)
                skipped_uneven += 1

        shutil.copy2(path, dest_dir / path.name)
        copied += 1

    print(f"copied {copied}, split {split} atlas(es) into frames, "
          f"excluded {excluded} (dirs: {sorted(exclude_dirs)}), "
          f"{skipped_uneven} mcmeta file(s) not evenly splittable (copied as-is)")


if __name__ == "__main__":
    main()
