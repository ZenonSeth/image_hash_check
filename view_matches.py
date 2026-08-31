#!/usr/bin/env python3
import argparse
import io
import json
import re
import sys
from pathlib import Path

import requests
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk, ImageOps

SCRIPT_DIR = Path(__file__).resolve().parent
WEB_CACHE_DIR = SCRIPT_DIR / "web_cache"

MAX_DIM = 384
MAX_THRESHOLD = 40
DEFAULT_THRESHOLD = 2

BG_COLOR = "#1a1a1a"
FG_COLOR = "#e0e0e0"

HEADER_RE = re.compile(r"^== (.+) \((.+)\)$")
MATCH_RE = re.compile(
    r"^- (\w+) \(([\d.]+)\): ([^:]+):(.+?)(?: \[(\w+)\])?  \(phash=(\d+) dhash=(\d+)\)$"
)

# maps a db's pack_name to where its reference images can be fetched from online
REF_SOURCES = {
    "mc-1.13.2": {
        "base_url": "https://raw.githubusercontent.com/Faithful-Pack/Default-Java/1.13.2/assets/minecraft/textures/",
        # these were manually cropped from an atlas
        "unavailable_prefixes": ("painting_manual_split/",),
    },
    "mc-1.21.11": {
        "base_url": "https://raw.githubusercontent.com/Faithful-Pack/Default-Java/1.21.11/assets/minecraft/textures/",
    },
    "mc-26.1": {
        "base_url": "https://raw.githubusercontent.com/Faithful-Pack/Default-Java/26.1/assets/minecraft/textures/",
    },
    # entries' "path" already includes the assets/minecraft/textures/ prefix,
    # unlike the other mc-* dbs, so base_url points at the repo root
    "MCJava26.2-clientjar": {
        "base_url": "https://raw.githubusercontent.com/Faithful-Pack/Default-Java/java-snapshot/",
    },
    # entries' "path" is "<mod>/<file>.png" flattened from mods/<mod>/textures/ per SOURCES.md
    "mtg": {
        "base_url": "https://raw.githubusercontent.com/luanti-org/minetest_game/5.8.0/",
        "flatten_mods": True,
    },
    # mineclonia's mods live nested under category folders: mods/ITEMS/mcl_foo
    # unlike mtg's flat mods/<mod>/, so the <mod>/<file>.png
    # entries' path can't be reconstructed without looking each mod's real
    # location up in the repo tree first (see build_github_mod_lookup).
    # Mirrored from codeberg.org/mineclonia/mineclonia
    "mineclonia": {
        "kind": "github_mod_lookup",
        "repo": "ZenonSeth/mineclonia-mirror",
        "ref": "0.123.0",
    },
    # VoxeLibre's textures are split between a flat top-level textures/ dir and
    # per-mod mods/<CAT>/<mod>/textures/ dirs with no reliable rule for which,
    # so files are looked up by basename only across the whole tree.
    # Mirrored from git.minetest.land/VoxeLibre/VoxeLibre.
    "voxelibre": {
        "kind": "github_basename_lookup",
        "repo": "ZenonSeth/voxelibre-mirror",
        "ref": "0.92.1",
    },
}

GITHUB_API = "https://api.github.com"


def fetch_github_tree(repo, ref):
    """Full recursive file listing of a repo at ref, as a list of {path, type, sha}."""
    commit_resp = requests.get(f"{GITHUB_API}/repos/{repo}/commits/{ref}", timeout=10)
    commit_resp.raise_for_status()
    tree_sha = commit_resp.json()["sha"]

    tree_resp = requests.get(
        f"{GITHUB_API}/repos/{repo}/git/trees/{tree_sha}", params={"recursive": "1"}, timeout=30,
    )
    tree_resp.raise_for_status()
    data = tree_resp.json()
    if data.get("truncated"):
        print(f"warning: {repo}@{ref} tree listing was truncated by GitHub's API", file=sys.stderr)
    return data["tree"]


def build_github_mod_lookup(repo, ref):
    """Maps mod name -> its dir prefix (the part before /textures/) by walking
    the repo's git tree once, caching the result to disk."""
    cache_file = WEB_CACHE_DIR / f"github_{repo.replace('/', '_')}_{ref}_mod_paths.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    mods = {}
    for e in fetch_github_tree(repo, ref):
        m = re.search(r"(?:^|/)([^/]+)/textures/[^/]+\.png$", e["path"])
        if m:
            mods.setdefault(m.group(1), e["path"].rsplit("/textures/", 1)[0])

    WEB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(mods))
    return mods


def build_github_basename_lookup(repo, ref):
    """Maps a png's basename -> its full repo path, across the whole tree
    regardless of nesting, by walking the repo's git tree once, caching the
    result to disk. First occurrence wins on a basename collision."""
    cache_file = WEB_CACHE_DIR / f"github_{repo.replace('/', '_')}_{ref}_basenames.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    by_basename = {}
    for e in fetch_github_tree(repo, ref):
        if e["path"].endswith(".png"):
            fname = e["path"].rsplit("/", 1)[-1]
            by_basename.setdefault(fname, e["path"])

    WEB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(by_basename))
    return by_basename


def fetch_reference_image(pack_name, ref_path):
    """Returns (PIL.Image or None, error_text or None)."""
    source = REF_SOURCES.get(pack_name)
    if source is None:
        return None, f"no web source configured for '{pack_name}' yet"

    for prefix in source.get("unavailable_prefixes", ()):
        if ref_path.startswith(prefix):
            return None, "atlas-split reference, no direct upstream file (special case, not handled yet)"

    cache_path = WEB_CACHE_DIR / pack_name / ref_path
    if cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGBA"), None
        except Exception:
            pass

    kind = source.get("kind")
    if kind == "github_mod_lookup":
        mod, _, filename = ref_path.partition("/")
        try:
            mod_paths = build_github_mod_lookup(source["repo"], source["ref"])
        except Exception as e:
            return None, f"repo tree lookup failed: {e}"
        prefix = mod_paths.get(mod)
        if prefix is None:
            return None, f"mod '{mod}' not found in {source['repo']}@{source['ref']}"
        url = f"https://raw.githubusercontent.com/{source['repo']}/{source['ref']}/{prefix}/textures/{filename}"
        content, error = get_url_bytes(url)
    elif kind == "github_basename_lookup":
        _, _, filename = ref_path.partition("/")
        try:
            basenames = build_github_basename_lookup(source["repo"], source["ref"])
        except Exception as e:
            return None, f"repo tree lookup failed: {e}"
        path = basenames.get(filename)
        if path is None:
            return None, f"'{filename}' not found in {source['repo']}@{source['ref']}"
        content, error = get_url_bytes(f"https://raw.githubusercontent.com/{source['repo']}/{source['ref']}/{path}")
    else:
        flatten_mods = source.get("flatten_mods")
        if flatten_mods is True:
            mod, _, filename = ref_path.partition("/")
            remote_path = f"mods/{mod}/textures/{filename}"
        elif flatten_mods:
            _, _, filename = ref_path.partition("/")
            remote_path = f"{flatten_mods}/{filename}"
        else:
            remote_path = ref_path
        content, error = get_url_bytes(source["base_url"] + remote_path)

    if content is None:
        return None, error
    try:
        img = Image.open(io.BytesIO(content)).convert("RGBA")
    except Exception as e:
        return None, f"failed to decode remote image: {e}"

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(content)
    return img, None


def get_url_bytes(url):
    try:
        resp = requests.get(url, timeout=10)
    except Exception as e:
        return None, f"request failed: {e}"
    if resp.status_code != 200:
        return None, f"not found on remote (HTTP {resp.status_code})"
    return resp.content, None


def apply_transform(img, transform):
    if transform == "rot0":
        return img
    deg_part, _, flip_part = transform.partition("_")
    deg = int(deg_part.replace("rot", ""))
    if deg:
        img = img.rotate(deg, expand=True)
    if flip_part == "flip":
        img = ImageOps.mirror(img)
    return img


def parse_results(path):
    items = []
    game_dir = None
    game_label = None
    current_source = None
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("=="):
            m = HEADER_RE.match(line)
            if m:
                game_label, game_dir = m.group(1), m.group(2)
            continue
        if line.startswith("- "):
            m = MATCH_RE.match(line)
            if not m or current_source is None:
                continue
            tier, dist, pack_name, ref_path, transform, phash, dhash = m.groups()
            items.append({
                "source_path": current_source,
                "game_dir": game_dir,
                "game_label": game_label,
                "tier": tier,
                "dist": float(dist),
                "pack_name": pack_name,
                "ref_path": ref_path,
                "transform": transform or "rot0",
                "phash": int(phash),
                "dhash": int(dhash),
            })
        else:
            current_source = line.strip()
    return items


def resolve_source_path(source_folder, item):
    # the result file's source paths are relative to the scanned package dir;
    # source_folder may itself be that package dir, or a parent containing
    # several games' package dirs (matching the header's "(game_dir)" part)
    direct = Path(source_folder) / item["source_path"]
    if direct.exists() or item["game_dir"] is None:
        return direct
    return Path(source_folder) / item["game_dir"] / item["source_path"]


class Viewer(tk.Tk):
    def __init__(self, items, source_folder):
        super().__init__()
        self.items = items
        self.source_folder = source_folder
        self.index = 0
        self.threshold = DEFAULT_THRESHOLD
        self.title("Texture match viewer")
        self.configure(bg=BG_COLOR)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG_COLOR, foreground=FG_COLOR)
        style.configure("TButton", background="#333333", foreground=FG_COLOR)
        style.map("TButton", background=[("active", "#444444")])

        self.info_label = ttk.Label(self, font=("TkDefaultFont", 11))
        self.info_label.pack(pady=6)

        images_frame = ttk.Frame(self)
        images_frame.pack(padx=10, pady=10)

        left = ttk.Frame(images_frame)
        left.grid(row=0, column=0, padx=20)
        self.source_canvas = tk.Label(left, bg=BG_COLOR, fg=FG_COLOR)
        self.source_canvas.pack()
        self.source_caption = ttk.Label(left, wraplength=MAX_DIM, justify="center")
        self.source_caption.pack(pady=4)

        right = ttk.Frame(images_frame)
        right.grid(row=0, column=1, padx=20)
        self.ref_canvas = tk.Label(right, bg=BG_COLOR, fg=FG_COLOR)
        self.ref_canvas.pack()
        self.ref_caption = ttk.Label(right, wraplength=MAX_DIM, justify="center")
        self.ref_caption.pack(pady=4)

        threshold_frame = ttk.Frame(self)
        threshold_frame.pack(pady=(0, 6))
        ttk.Label(threshold_frame, text="Max distance (confidence):").pack(side="left", padx=(0, 8))
        ttk.Button(threshold_frame, text="-1", width=3, command=lambda: self.adjust_threshold(-1)).pack(side="left")
        ttk.Button(threshold_frame, text="-0.1", width=4, command=lambda: self.adjust_threshold(-0.1)).pack(side="left")
        self.threshold_value_label = ttk.Label(threshold_frame, text=str(self.threshold), width=5, anchor="center")
        self.threshold_value_label.pack(side="left", padx=4)
        ttk.Button(threshold_frame, text="+0.1", width=4, command=lambda: self.adjust_threshold(0.1)).pack(side="left")
        ttk.Button(threshold_frame, text="+1", width=3, command=lambda: self.adjust_threshold(1)).pack(side="left")

        controls = ttk.Frame(self)
        controls.pack(pady=10)
        ttk.Button(controls, text="<< Prev source", command=self.prev_source).grid(row=0, column=0, padx=4)
        ttk.Button(controls, text="< Prev match", command=self.prev_match).grid(row=0, column=1, padx=4)
        ttk.Button(controls, text="Next match >", command=self.next_match).grid(row=0, column=2, padx=4)
        ttk.Button(controls, text="Next source >>", command=self.next_source).grid(row=0, column=3, padx=4)

        self.bind("<Left>", lambda e: self.prev_match())
        self.bind("<Right>", lambda e: self.next_match())
        self.bind("<Prior>", lambda e: self.prev_source())
        self.bind("<Next>", lambda e: self.next_source())

        self.set_threshold(self.threshold)

    def load_thumbnail(self, path):
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            return None, f"failed to load: {e}"
        scale = max(1, MAX_DIM // max(img.width, img.height))
        resized = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        return ImageTk.PhotoImage(resized), f"{img.width}x{img.height}"

    def visible_indices(self):
        return [i for i, it in enumerate(self.items) if it["dist"] <= self.threshold]

    def adjust_threshold(self, delta):
        self.set_threshold(self.threshold + delta)

    def set_threshold(self, value):
        value = round(max(0, min(MAX_THRESHOLD, value)), 2)
        self.threshold = value
        self.threshold_value_label.configure(text=f"{value:g}")

        visible = self.visible_indices()
        if not visible:
            self.show_current()
            return
        if self.index not in visible:
            self.index = next((i for i in visible if i > self.index), visible[0])
        self.show_current()

    def show_current(self):
        visible = self.visible_indices()
        if not visible:
            self._source_photo = None
            self._ref_photo = None
            self.source_canvas.configure(image="", text="")
            self.source_caption.configure(text="")
            self.ref_canvas.configure(image="", text="")
            self.ref_caption.configure(text="")
            self.info_label.configure(text="no matches at or below the current confidence threshold")
            return

        item = self.items[self.index]

        source_full = resolve_source_path(self.source_folder, item)
        photo, dims = self.load_thumbnail(source_full)
        self._source_photo = photo
        self.source_canvas.configure(image=photo, text="" if photo else dims)
        self.source_caption.configure(text=f"{item['source_path']}\n{dims}")

        ref_img, ref_error = fetch_reference_image(item["pack_name"], item["ref_path"])
        if ref_img is not None:
            ref_img = apply_transform(ref_img, item["transform"])
            scale = max(1, MAX_DIM // max(ref_img.width, ref_img.height))
            resized = ref_img.resize((ref_img.width * scale, ref_img.height * scale), Image.NEAREST)
            ref_photo = ImageTk.PhotoImage(resized)
            ref_dims = f"{ref_img.width}x{ref_img.height}"
        else:
            ref_photo = None
            ref_dims = ref_error
        self._ref_photo = ref_photo
        self.ref_canvas.configure(image=ref_photo, text="" if ref_photo else ref_dims)
        self.ref_caption.configure(
            text=f"{item['pack_name']}:{item['ref_path']}\n"
                 f"{item['tier']} ({item['dist']:.1f})  transform={item['transform']}\n"
                 f"phash={item['phash']} dhash={item['dhash']}"
        )

        same_source_visible = [i for i in visible if self.items[i]["source_path"] == item["source_path"]]
        match_pos = same_source_visible.index(self.index) + 1
        self.info_label.configure(
            text=f"[{item['game_label']}]  match {match_pos}/{len(same_source_visible)} for this source  "
                 f"(overall {visible.index(self.index) + 1}/{len(visible)}, "
                 f"threshold <= {self.threshold})"
        )

    def next_match(self):
        visible = self.visible_indices()
        if not visible:
            return
        pos = visible.index(self.index) if self.index in visible else -1
        self.index = visible[(pos + 1) % len(visible)]
        self.show_current()

    def prev_match(self):
        visible = self.visible_indices()
        if not visible:
            return
        pos = visible.index(self.index) if self.index in visible else 0
        self.index = visible[(pos - 1) % len(visible)]
        self.show_current()

    def next_source(self):
        visible = self.visible_indices()
        if not visible:
            return
        current = self.items[self.index]["source_path"]
        for i in visible:
            if i > self.index and self.items[i]["source_path"] != current:
                self.index = i
                self.show_current()
                return

    def prev_source(self):
        visible = self.visible_indices()
        if not visible:
            return
        current = self.items[self.index]["source_path"]
        pos = visible.index(self.index) if self.index in visible else 0
        first_of_current = pos
        while first_of_current > 0 and self.items[visible[first_of_current - 1]]["source_path"] == current:
            first_of_current -= 1
        if first_of_current == 0:
            return
        prev_source_name = self.items[visible[first_of_current - 1]]["source_path"]
        first_of_prev = first_of_current - 1
        while first_of_prev > 0 and self.items[visible[first_of_prev - 1]]["source_path"] == prev_source_name:
            first_of_prev -= 1
        self.index = visible[first_of_prev]
        self.show_current()


class LauncherWindow(tk.Tk):
    def __init__(self, result_file=None, source_folder=None):
        super().__init__()
        self.title("Texture match viewer - setup")
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)
        self.result_file = result_file
        self.source_folder = source_folder
        self.confirmed = False

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG_COLOR, foreground=FG_COLOR)
        style.configure("TButton", background="#333333", foreground=FG_COLOR)
        style.map("TButton", background=[("active", "#444444")])

        frame = ttk.Frame(self, padding=16)
        frame.pack()

        ttk.Button(frame, text="Select result file...", command=self.pick_result_file, width=22).grid(
            row=0, column=0, sticky="w", pady=4)
        self.result_label = ttk.Label(frame, text=self._display(self.result_file), wraplength=380, justify="left")
        self.result_label.grid(row=0, column=1, sticky="w", padx=8)

        ttk.Button(frame, text="Select source folder...", command=self.pick_source_folder, width=22).grid(
            row=1, column=0, sticky="w", pady=4)
        self.source_label = ttk.Label(frame, text=self._display(self.source_folder), wraplength=380, justify="left")
        self.source_label.grid(row=1, column=1, sticky="w", padx=8)

        self.ok_button = ttk.Button(frame, text="OK", command=self.confirm, state="disabled")
        self.ok_button.grid(row=2, column=0, columnspan=2, pady=(16, 0))

        self.update_ok_state()

    def _display(self, path):
        return path if path else "(not selected)"

    def pick_result_file(self):
        path = filedialog.askopenfilename(
            title="Select a result_check_*.txt file", filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.result_file = path
            self.result_label.configure(text=path)
            self.update_ok_state()

    def pick_source_folder(self):
        path = filedialog.askdirectory(title="Select source package folder")
        if path:
            self.source_folder = path
            self.source_label.configure(text=path)
            self.update_ok_state()

    def update_ok_state(self):
        self.ok_button.configure(state="normal" if (self.result_file and self.source_folder) else "disabled")

    def confirm(self):
        self.confirmed = True
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="Browse check_package.py result files, viewing source/reference texture matches side by side")
    parser.add_argument("result_file", nargs="?", default=None,
                         help="path to a result_check_*.txt file. If omitted, a picker window is shown.")
    parser.add_argument("-s", "--source-folder", default=None,
                         help="folder the result file's source paths are relative to, i.e. the "
                              "package dir passed to check_package.py -p (or its parent, if the "
                              "result file covers several games). If omitted, a picker window is shown.")
    args = parser.parse_args()

    result_file = args.result_file
    source_folder = args.source_folder

    if result_file is None or source_folder is None:
        launcher = LauncherWindow(result_file=result_file, source_folder=source_folder)
        launcher.mainloop()
        if not launcher.confirmed:
            sys.exit(0)
        result_file = launcher.result_file
        source_folder = launcher.source_folder

    items = parse_results(result_file)
    if not items:
        print("no matches found in file", file=sys.stderr)
        sys.exit(1)

    app = Viewer(items, source_folder)
    app.mainloop()


if __name__ == "__main__":
    main()
