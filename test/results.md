# Test results

## Command

```
python3 check_package.py -p test -d hashdb_mtg.json
```

## Output

```
default_chest_lock_flipped_v.png
- exact (0.0): mtg:default/default_chest_lock.png [rot180_flip]  (phash=0 dhash=0)
- possible (12.0): mtg:default/default_chest_front.png [rot180_flip]  (phash=12 dhash=12)

default_chest_lock_hushifted_a.png
- strong (2.7): mtg:default/default_chest_lock.png  (phash=2 dhash=4)
- possible (12.0): mtg:default/default_chest_front.png  (phash=12 dhash=12)

default_chest_lock_majormod.png
- possible (11.7): mtg:default/default_fence_rail_overlay.png [rot90]  (phash=17 dhash=9)

default_chest_lock_rotated.png
- exact (0.0): mtg:default/default_chest_lock.png [rot270]  (phash=0 dhash=0)
- possible (8.7): mtg:default/default_chest_front.png [rot270]  (phash=12 dhash=7)
- possible (10.0): mtg:default/default_chest_side.png [rot270]  (phash=14 dhash=8)

default_chest_lock_slightmod.png
- strong (6.0): mtg:default/default_chest_lock.png  (phash=10 dhash=4)
- possible (12.0): mtg:default/default_chest_front.png  (phash=12 dhash=12)
```
