# Reference texture pack sources

Each hashdb_*.json is generated with build_ref_hash.py. Record source, version/commit, and license here when a db is added.

hashdb_*.json here is trimmed, see "Trimmed variants" below. full/hashdb_*.json
holds the untrimmed originals.

- hashdb_mtg.json: Minetest Game by the Luanti core team, release 30744. No
  commit hash available. Media is CC BY-SA 3.0, see mtg_textures/LICENSE.txt.
  Source images copied into mtg_textures/, per-mod textures/ dirs, along
  with each mod's README.txt for author attribution referenced by
  LICENSE.txt.
- hashdb_mineclonia.json: Mineclonia, release 33876. No commit hash
  available. Code is GPLv3-or-later; media is CC BY-SA 4.0 per-asset, see
  LEGAL.md, based substantially on the Pixel Perfection and Pixel
  Perfection Legacy resource packs. Source images were NOT copied into this
  repo - only hashes/filenames were recorded, 2859 entries.
- hashdb_voxelibre.json: VoxeLibre, formerly MineClone2, version 0.89.3,
  release 30845. No commit hash available. Code is GPLv3-or-later; media is
  CC BY-SA 4.0 / CC BY 4.0 per-asset, see LEGAL.md, based substantially on
  the Pixel Perfection resource pack by XSSheep. Source images were NOT
  copied into this repo - only hashes/filenames were recorded, 2874
  entries, same policy as hashdb_mc_1.13.2.json below.
- hashdb_mc_1.13.2.json / hashdb_mc_1.21.11.json: Minecraft Java Edition
  default resource pack, versions 1.13.2 and 1.21.11, source jars/repos not
  tracked here. All rights reserved by Mojang/Microsoft - used strictly for
  lead-generation hash comparison, no images redistributed, hashes and
  filenames only, 1580 / 3514 entries in full/. Pre-processed with
  split_atlas_frames.py before hashing:
  - excludes font/ and gui/ - glyph atlases and UI chrome, not comparable to
    in-game textures a package might reuse
  - excludes trims/entity/, 1.21.11 only - thin trim overlay line patterns,
    too generic to be useful reference textures
  - excludes specific generic/low-value files: map/map_icons.png,
    particle/particles.png, 1.13.2 only, tiny generic icon atlases,
    misc/vignette.png, misc/shadow.png, misc/nausea.png,
    mob_effect/nausea.png, misc/credits_vignette.png, 1.21.11 only
  - slices any *.png.mcmeta-linked vertical animation strip into individual
    per-frame images, e.g. campfire_fire.png, 16x128, splits into 8 stacked
    16x16 frames
  - block/item/entity textures needed no splitting, already individual
    files in this source. 1.21.11's painting/ is likewise already
    individual files. 1.13.2's old painting/paintings_kristoffer_zetterstrand.png
    sprite sheet was excluded and manually split by hand into
    painting_manual_split/ instead, since it isn't auto-splittable - variable-sized
    regions, not a uniform grid

## Trimmed variants

`hashdb_*.json` are trimmed database versions, with `trim_solid_color_matches.py` applied to `full/hashdb_*.json`, against sample_colors/, threshold 2, using check_package.py's combined phash/dhash distance metric. Drops entries that are themselves near-flat/near-transparent which would otherwise match any solid-colored submission texture and generate false-positive noise.

Counts trimmed, removed over total:
- mc_1.13.2: 21/1580
- mc_1.21.11: 35/3514
- mtg: 4/447
- mineclonia: 338/2859
- voxelibre: 546/2874
