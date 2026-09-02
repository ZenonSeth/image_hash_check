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

## merge_hashes_db.py

Merges one hash database's entries into another, skipping any entry whose
rot0 phash+dhash already matches one already in the merged set (e.g. a
texture unchanged between two Minecraft versions). Not optimized for speed.

   `python merge_hashes_db.py <base.json> <additional.json> <output.json> [--pack-name NAME]`

- `base` - base hash database JSON
- `additional` - hash database JSON to merge into base
- `output` - path to write the merged database
- `--pack-name` - pack_name recorded in the output db, default: base's pack_name

Entries added from `additional` have their `path` prefixed with
`additional`'s pack_name (e.g. `mc-1.21.11/block/...`), so `check_package.py`
still shows which source db a match actually came from.

## check_package.py

Scans a package's images and reports close matches against one or more hash
databases, checking each reference image's stored orientations and keeping
the closest one.

   `python check_package.py -p <package_dir> -d db1.json [db2.json ...] [--threshold N] [-w]`

- `-p, --package` - directory of the extracted package to scan
- `-d, --db` - one or more hash database JSON files to check against
- `--threshold` - max hamming distance to report as a match, default: 48,
  the "possible" tier bound, or 80 with `-w`. Overrides `-w` when set
- `-w, --include-weak` - also report "weak" tier matches, excluded by
  default as too noisy

Matches are labeled with a confidence tier based on hamming distance (using
16x16 phash/dhash, i.e. 256-bit hashes): 0=exact, <=24=strong, <=48=possible,
<=80=weak. See `TIERS` in check_package.py; these are heuristic starting
points, to be tuned against real test data. Output is grouped by package
file, closest match first within each group:

```
default_chest_lock_flipped_v.png
- exact (0.0): mtg:default/default_chest_lock.png [rot180_flip]  (phash=0 dhash=0)
- possible (48.0): mtg:default/default_chest_front.png [rot180_flip]  (phash=48 dhash=48)
```

See SOURCES.md for how the committed hashdb_*.json files were built.

## split_atlas_frames.py

Copies a texture directory into a cleaned-up output dir, for use as input to
build_ref_hash.py: excludes given directories and slices any
`*.png.mcmeta`-linked vertical animation strip into individual per-frame
images.

   `python split_atlas_frames.py <src_dir> <output_dir> [--exclude DIR ...]`

- `src_dir` - source texture directory to scan recursively
- `output_dir` - directory to write the cleaned/split copy to
- `--exclude` - directory name to exclude (path component match, repeatable),
  default: `font`, `gui`

## view_matches.py

GUI to browse a `check_package.py` result file, viewing each flagged source
image side by side with its matched reference texture (fetched online per db).

   `python view_matches.py [result_file] [-s source_folder]`

- `result_file` - a saved `check_package.py` output file; omitted opens a picker
- `-s, --source-folder` - the package dir passed to `check_package.py -p`; omitted opens a picker

## trim_solid_color_matches.py

Trims a hash database (as built by build_ref_hash.py) of entries that are
near-exact matches to flat/solid reference swatches (sample_colors/ by
default), using check_package.py's combined phash/dhash distance metric.

   `python trim_solid_color_matches.py <input.json> [-o output.json] [--refs-dir DIR] [--threshold N] [--dry-run]`

- `input_json` - hash database JSON to trim
- `-o, --output` - path to write the trimmed database, default:
  `<input>_trimmed.json`
- `--refs-dir` - directory of flat/solid reference swatches, default:
  `sample_colors/`
- `--threshold` - max combined distance (exclusive) to count as a match,
  default: 4
- `--dry-run` - report what would be removed without writing a file

`trim_solid_color_matches.py` and `trim_misc_hashes.py` are obsolete for normal use - their trims now run by default inside `build_ref_hash.py`, with the same flags.
