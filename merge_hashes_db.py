#!/usr/bin/env python3
import argparse
import json
import sys


def load_db(path):
    with open(path) as f:
        data = json.load(f)
    return data["pack_name"], data["entries"]


def main():
    parser = argparse.ArgumentParser(
        description="Merge ADDITIONAL's entries into BASE, skipping any entry whose rot0 "
                     "phash+dhash already exists in the merged set, and write the result to "
                     "OUTPUT. Not optimized for speed - just plain string-equality dedup."
    )
    parser.add_argument("base", help="base hash database JSON")
    parser.add_argument("additional", help="hash database JSON to merge into base")
    parser.add_argument("output", help="path to write the merged database JSON")
    parser.add_argument("--pack-name", default=None,
                         help="pack_name recorded in the output db, default: base's pack_name")

    positional = []
    skip_next = False
    for arg in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg == "--pack-name":
            skip_next = True
            continue
        if not arg.startswith("-"):
            positional.append(arg)

    if len(positional) != 3:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    base_name, base_entries = load_db(args.base)
    additional_name, additional_entries = load_db(args.additional)

    seen = {(e["hashes"]["rot0"]["phash"], e["hashes"]["rot0"]["dhash"]) for e in base_entries}

    merged_entries = list(base_entries)
    added = 0
    skipped = 0
    for entry in additional_entries:
        key = (entry["hashes"]["rot0"]["phash"], entry["hashes"]["rot0"]["dhash"])
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        entry = dict(entry)
        entry["path"] = f"{additional_name}/{entry['path']}"
        merged_entries.append(entry)
        added += 1

    output_data = {
        "pack_name": args.pack_name or base_name,
        "entries": merged_entries,
    }
    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"base: {len(base_entries)} entries, additional: {len(additional_entries)} entries "
          f"({added} added, {skipped} skipped as duplicates) -> {len(merged_entries)} total in {args.output}")


if __name__ == "__main__":
    main()
