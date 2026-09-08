#!/usr/bin/env python3
"""
Auto-generates index.html as a collapsible Finder-style file navigator,
based on the CURRENT repo file tree. Run by the GitHub Actions workflow
on every push to main. Safe to run locally too (no dependencies).
"""
import os
import json
import urllib.parse

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(REPO_ROOT, "nav.config.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "index.html")

HARD_EXCLUDES = {".git", ".github", "node_modules", ".DS_Store"}
SELF_EXCLUDES = {"index.html", "nav.config.json", "build_index.py", "README.md", "LICENSE"}

ICONS = {
    ".html": "\U0001F4C4", ".htm": "\U0001F4C4", ".txt": "\U0001F4DD", ".json": "\U0001F9E9",
    ".jpg": "\U0001F5BC\uFE0F", ".jpeg": "\U0001F5BC\uFE0F", ".png": "\U0001F5BC\uFE0F", ".gif": "\U0001F5BC\uFE0F", ".svg": "\U0001F5BC\uFE0F",
    ".xlsx": "\U0001F4CA", ".xls": "\U0001F4CA", ".csv": "\U0001F4CA",
    ".mp3": "\U0001F3B5", ".wav": "\U0001F3B5",
    ".py": "\U0001F40D", ".js": "\U0001F4DC", ".css": "\U0001F3A8",
    ".pdf": "\U0001F4D5", ".zip": "\U0001F5DC\uFE0F",
}
DEFAULT_FILE_ICON = "\U0001F4C4"
FOLDER_ICON = "\U0001F4C1"


def load_config():
    default = {"exclude": ["data"], "labels": {}}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            default["exclude"] = cfg.get("exclude", default["exclude"])
            default["labels"] = cfg.get("labels", {})
        except Exception as e:
            print(f"Warning: could not parse nav.config.json ({e}), using defaults")
    return default


def is_excluded(rel_path, exclude_list):
    norm = rel_path.replace(os.sep, "/")
    for ex in exclude_list:
        ex_norm = ex.strip("/")
        if norm == ex_norm or norm.startswith(ex_norm + "/"):
            return True
    return False


def prettify(name):
    stem, _ = os.path.splitext(name)
    words = stem.replace("_", " ").replace("-", " ").split()
    return " ".join(w.capitalize() if not w.isupper() else w for w in words) or name


def icon_for(name):
    _, ext = os.path.splitext(name.lower())
    return ICONS.get(ext, DEFAULT_FILE_ICON)


def build_tree(cur_dir, rel_path, exclude_list):
    entries = []
    try:
        names = sorted(os.listdir(cur_dir), key=lambda s: s.lower())
    except FileNotFoundError:
        return entries

    for name in names:
        if name in HARD_EXCLUDES or name in SELF_EXCLUDES:
            continue
        if name.startswith("."):
            continue
        full = os.path.join(cur_dir, name)
        rel = os.path.join(rel_path, name) if rel_path else name
        if is_excluded(rel, exclude_list):
            continue
        if os.path.isdir(full):
            children = build_tree(full, rel, exclude_list)
            if children:
                entries.append(("dir", name, rel, children))
        else:
            entries.append(("file", name, rel, None))

    dirs = [e for e in entries if e[0] == "dir"]
    files = [e for e in entries if e[0] == "file"]
    return dirs + files


def href_for(rel_path):
    parts = rel_path.replace(os.sep, "/").split("/")
    return "/".join(urllib.parse.quote(p) for p in parts)


def render_tree(entries, labels, depth=1):
    html = []
    pad_summary = 0.9 + depth * 0.7
    pad_file = 1.6 + (depth - 1) * 0.7
    for kind, name, rel, children in entries:
        rel_norm = rel.replace(os.sep, "/")
        label = labels.get(rel_norm, prettify(name) if kind == "dir" else name)
        if kind == "dir":
            html.append(f'<details class="folder">')
            html.append(
                f'<summary style="padding-left:{pad_summary}rem">'
                f'<span class="chev">\u25b6</span><span class="icon">{FOLDER_ICON}</span>{label}</summary>'
            )
            html.append('<div class="body-wrap"><div class="body-inner">')
            html.append(render_tree(children, labels, depth + 1))
            html.append('</div></div></details>')
        else:
            icon = icon_for(name)
            html.append(
                f'<a class="file-row" style="padding-left:{pad_file}rem" target="_blank" '
                f'href="{href_for(rel)}"><span class="icon">{icon}</span>{name}</a>'
            )
    return "\n".join(html)


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kevin's Public Projects</title>
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#1d1d1f">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="KP Projects">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<style>
  :root{{
    --bg:#f5f5f7; --panel:#ffffff; --border:#d8d8dc; --text:#1d1d1f;
    --muted:#6e6e73; --accent:#0071e3; --row-hover:#eef4ff;
  }}
  *{{box-sizing:border-box;}}
  body{{
    margin:0; padding:2rem 1rem 4rem; background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  }}
  h1{{font-size:1.5rem; font-weight:600; text-align:center; margin:0 0 .25rem;}}
  p.sub{{text-align:center; color:var(--muted); margin:0 0 .35rem; font-size:.9rem;}}
  p.updated{{text-align:center; color:var(--muted); margin:0 0 1.5rem; font-size:.75rem;}}
  .finder{{
    max-width:720px; margin:0 auto; background:var(--panel);
    border:1px solid var(--border); border-radius:12px; overflow:hidden;
    box-shadow:0 1px 3px rgba(0,0,0,.06);
  }}
  .toolbar{{
    display:flex; justify-content:flex-end; gap:.5rem; padding:.6rem .9rem;
    border-bottom:1px solid var(--border); background:#fafafa;
  }}
  .toolbar button{{
    font-size:.78rem; padding:.35rem .7rem; border-radius:6px; border:1px solid var(--border);
    background:#fff; color:var(--text); cursor:pointer;
  }}
  .toolbar button:hover{{background:var(--row-hover);}}
  details{{border-bottom:1px solid #ececec;}}
  details:last-child{{border-bottom:none;}}
  summary{{
    list-style:none; cursor:pointer; padding:.55rem .9rem;
    display:flex; align-items:center; gap:.5rem; user-select:none;
    font-size:.92rem; font-weight:500;
  }}
  summary::-webkit-details-marker{{display:none;}}
  summary:hover{{background:var(--row-hover);}}
  summary .chev{{
    display:inline-block; width:.7rem; transition:transform .15s ease;
    color:var(--muted); font-size:.75rem; flex-shrink:0;
  }}
  details[open] > summary .chev{{transform:rotate(90deg);}}
  summary .icon{{flex-shrink:0; font-size:1rem;}}
  .body-wrap{{
    display:grid; grid-template-rows:0fr; transition:grid-template-rows .18s ease;
  }}
  details[open] > .body-wrap{{grid-template-rows:1fr;}}
  .body-inner{{overflow:hidden;}}
  .file-row{{
    display:flex; align-items:center; gap:.5rem; padding:.5rem .9rem .5rem 1.6rem;
    font-size:.88rem; text-decoration:none; color:var(--text);
    border-bottom:1px solid #f2f2f2;
  }}
  .file-row:hover{{background:var(--row-hover); color:var(--accent);}}
  .file-row .icon{{flex-shrink:0; font-size:.95rem;}}
  .footer-note{{
    max-width:720px; margin:1.25rem auto 0; font-size:.8rem; color:var(--muted); text-align:center;
  }}
</style>
</head>
<body>

<h1>Kevin's Public Projects</h1>
<p class="sub">Click any folder to expand it, click a file to open it in a new tab.</p>
<p class="updated">Auto-generated from the repo file structure &mdash; always in sync with the latest commit.</p>

<div class="finder">
  <div class="toolbar">
    <button id="expandAll">Expand All</button>
    <button id="collapseAll">Collapse All</button>
  </div>
{tree}
</div>

<p class="footer-note">Excluded from this listing: <code>/data</code> and repo housekeeping files. Edit <code>nav.config.json</code> to change what's shown or how it's labeled.</p>

<script>
  document.getElementById('expandAll').addEventListener('click', () => {{
    document.querySelectorAll('details').forEach(d => d.open = true);
  }});
  document.getElementById('collapseAll').addEventListener('click', () => {{
    document.querySelectorAll('details').forEach(d => d.open = false);
  }});
  if ('serviceWorker' in navigator) {{
    window.addEventListener('load', () => {{
      navigator.serviceWorker.register('sw.js').catch(console.error);
    }});
  }}
</script>
</body>
</html>
"""


def main():
    cfg = load_config()
    tree = build_tree(REPO_ROOT, "", cfg["exclude"])
    tree_html = render_tree(tree, cfg["labels"], depth=1)
    page = PAGE_TEMPLATE.format(tree=tree_html)

    old = None
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            old = f.read()

    if old == page:
        print("index.html already up to date, no changes.")
        return

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(page)
    print("index.html regenerated.")


if __name__ == "__main__":
    main()
