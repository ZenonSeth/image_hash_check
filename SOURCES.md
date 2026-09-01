# Reference texture pack sources

Each hashdb_*.json is generated with build_ref_hash.py. Record source, version/commit, and license here when a db is added.

hashdb_*.json here is trimmed, see "Trimmed variants" below. full/hashdb_*.json
holds the untrimmed originals.

All hashdb_*.json here use imagehash's 16x16 (hash_size=16) phash/dhash grid,
not the library default of 8x8. Rebuilt 2026-08-27 for this reason - any db
built with the old 8x8 hashes is incompatible and must be rebuilt, not just
re-trimmed.

- hashdb_mtg.json: Minetest Game, release 38214. CC BY-SA 3.0 media. Built
  from a local game install, images not copied into this repo, 447 entries.
- hashdb_mineclonia.json: Mineclonia, release 37652. GPLv3-or-later code,
  CC BY-SA 4.0 media (see LEGAL.md), based on Pixel Perfection / Pixel
  Perfection Legacy. Built from a local game install, images not copied
  into this repo, 3236 entries.
- hashdb_voxelibre.json: VoxeLibre (MineClone2), 0.92.1, release 37921.
  GPLv3-or-later code, CC BY-SA 4.0 / CC BY 4.0 media (see LEGAL.md), based
  on Pixel Perfection by XSSheep. Built from a local game install, images
  not copied into this repo, 2883 entries.
  - mtg/mineclonia/voxelibre were each flattened (mods/<mod>/textures/*.png
    -> <mod>/*.png) before hashing; no mod name collisions across the three.
- hashdb_mc_1.13.2.json / hashdb_mc_1.21.11.json / hashdb_mc_26.1.json:
  Minecraft Java Edition default resource pack, versions 1.13.2, 1.21.11,
  26.1, sourced from https://github.com/Faithful-Pack/Default-Java branches
  "1.13.2"/"1.21.11"/"26.1", not the original jars. All rights reserved by
  Mojang/Microsoft, hashes/filenames only, no images redistributed. 1580 /
  3513 / 3660 entries in full/. particle/sculk_charge_0.png excluded from
  all three (too many false positives). 1.13.2 only had sprite-sheet
  atlases needing split_atlas_frames.py (paintings split by hand, other
  animation strips auto-split via *.png.mcmeta); 1.21.11/26.1 ship
  per-frame files already, no atlas splitting needed. font/, gui/,
  trims/entity/ (1.21.11+26.1 only), and misc vignette/shadow/nausea/
  credits_vignette (1.21.11+26.1 only) excluded as noisy/not comparable.
- hashdb_mc_26.2.json: Minecraft Java Edition default resource pack,
  version 26.2, sourced from the official client jar (no matching branch on
  Faithful-Pack/Default-Java; that repo's java-latest branch has many/most
  of the same textures but isn't the source used here). No atlases.
  particle/sculk_charge_0.png excluded from full/ by hand. font/, gui/,
  trims/entity/, and misc vignette/shadow/nausea/credits_vignette - the
  same exclusion list as 1.21.11/26.1 - removed by hand from the trimmed
  json only, not from full/ 
- hashdb_faithful32x_26.1.json / hashdb_faithful64x_26.1.json: Faithful 32x
  / Faithful 64x resource packs (Minecraft Java Edition), branch 26.1,
  commits 2b4da74 / dca492c, from
  https://github.com/Faithful-Resource-Pack/Faithful-32x-Java and
  Faithful-64x-Java. Faithful License v4 (custom, attribution-based, not
  FOSS - see LICENSE.txt in each source dir). Source trees kept locally
  under _tools/faithful_32x/26.1/ and _tools/faithful_64x/26.1/, not
  copied into hashesdb/. No full/ variant kept for these two - built and
  trimmed in place. 57 atlases split via split_atlas_frames.py in each
  before hashing; font/, gui/, trims/entity/, trims/color_palettes, and
  misc vignette/shadow/nausea/credits_vignette excluded same as mc_26.2.
  3580 / 3584 entries after trimming.

## Trimmed variants

`hashdb_*.json` are trimmed database versions, with `trim_solid_color_matches.py` applied to `full/hashdb_*.json`, against sample_colors/, threshold 2, using check_package.py's combined phash/dhash distance metric. Drops entries that are themselves near-flat/near-transparent which would otherwise match any solid-colored submission texture and generate false-positive noise.

Counts trimmed, removed over total:
- mc_1.13.2: 21/1580
- mc_1.21.11: 27/3513
- mc_26.1: 28/3660
- mc_26.2: 50/??
- mtg: 4/447
- mineclonia: 552/3236
- voxelibre: 546/2883
- faithful32x_26.1: 84/3664 (48 solid + 36 misc-path)
- faithful64x_26.1: 78/3662 (42 solid + 36 misc-path)
