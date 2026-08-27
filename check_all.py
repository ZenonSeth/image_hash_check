import sys
from pathlib import Path

import check_package

HASHESDB_DIR = Path(__file__).parent / "hashesdb"
DB_NAMES = [
    "hashdb_mc_1.13.2.json",
    "hashdb_mc_1.21.11.json",
    "hashdb_mineclonia.json",
    "hashdb_mtg.json",
    "hashdb_voxelibre.json",
]


def main():
    dbs = [str(HASHESDB_DIR / name) for name in DB_NAMES]
    sys.argv = [sys.argv[0]] + sys.argv[1:] + ["-d"] + dbs
    check_package.main()


if __name__ == "__main__":
    main()
