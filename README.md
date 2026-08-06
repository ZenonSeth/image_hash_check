# Luanti Texture Hash Checker

Detect reused/renamed textures in a submission by comparing perceptual hashes against reference texture packs.

Install deps:

`pip install -r requirements.txt`

This is a lead-generation tool for a human reviewer, not a verdict: it favors
false positives over false negatives, so expect to see - and dismiss -
weak/possible matches that turn out to be unrelated.

## build_ref_hash.py

Computes phash/dhash for every image in a directory, across all 8
rotate/flip orientations, and writes them to a JSON database. Storing all
orientations in the reference DB means a package image only needs to be
hashed once at check time to catch reused textures that were rotated or
flipped.

   `python build_ref_hash.py <textures_dir> <output.json> [--pack-name NAME]`

- `textures_dir` - directory to scan recursively for png/jpg/jpeg/tga/bmp
- `output_json` - path to write the hash database
- `--pack-name` - name recorded in the database, default: textures_dir name

## check_package.py

Scans a package's images and reports close matches against one or more hash
databases, checking each reference image's stored orientations and keeping
the closest one.

   `python check_package.py -p <package_dir> -d db1.json [db2.json ...] [--threshold N] [-w]`

- `-p, --package` - directory of the extracted package to scan
- `-d, --db` - one or more hash database JSON files to check against
- `--threshold` - max hamming distance to report as a match, default: 12,
  the "possible" tier bound, or 20 with `-w`. Overrides `-w` when set
- `-w, --include-weak` - also report "weak" tier matches, excluded by
  default as too noisy

Matches are labeled with a confidence tier based on hamming distance:
0=exact, <=6=strong, <=12=possible, <=20=weak. See `TIERS` in
check_package.py; these are heuristic starting points, to be tuned against
real test data. Output is grouped by package file, closest match first
within each group:

```
default_chest_lock_flipped_v.png
- exact (0.0): mtg:default/default_chest_lock.png [rot180_flip]  (phash=0 dhash=0)
- possible (12.0): mtg:default/default_chest_front.png [rot180_flip]  (phash=12 dhash=12)
```

See SOURCES.md for how the committed hashdb_*.json files were built.
