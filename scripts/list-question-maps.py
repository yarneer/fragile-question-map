#!/usr/bin/env python3
"""List Question Maps stored under <root>/.question-map/, most recently updated first."""

import argparse
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prototype_iteration_common import is_blank, use_utf8_output  # noqa: E402

MAP_DIR_NAME = ".question-map"


def cell(value, default="none"):
    if is_blank(value):
        return default
    return str(value).replace("|", "\\|").replace("\n", " ")


def summarize(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            document = json.load(handle)
    except (ValueError, OSError) as exc:
        return {"id": "unreadable", "closure": "unreadable", "iteration": "unreadable", "destination": str(exc)}
    if not isinstance(document, dict):
        document = {}
    closure = document.get("closure") if isinstance(document.get("closure"), dict) else {}
    iteration = document.get("iteration") if isinstance(document.get("iteration"), dict) else None
    if iteration is None:
        iteration_text = "none"
    else:
        iteration_text = f"{cell(iteration.get('state'))} @ {cell(iteration.get('active_region_ref'))}"
    return {
        "id": cell(document.get("question_map_id")),
        "closure": cell(closure.get("status"), "not declared"),
        "iteration": iteration_text,
        "destination": cell(document.get("destination")),
    }


def main():
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="project root (default: current directory)")
    root = os.path.abspath(parser.parse_args().root)

    if not os.path.isdir(root):
        print(f"ERROR: directory not found: {root}", file=sys.stderr)
        return 1

    store = os.path.join(root, MAP_DIR_NAME)
    paths = glob.glob(os.path.join(store, "*", "question-map.json"))
    if not paths:
        print(f"No Question Maps found under {store}")
        return 0

    paths.sort(key=os.path.getmtime, reverse=True)
    lines = [
        f"# Question Maps under {store}",
        "",
        "| Map | ID | Closure | Iteration | Updated | Destination |",
        "|---|---|---|---|---|---|",
    ]
    for path in paths:
        info = summarize(path)
        updated = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
        relative = os.path.relpath(path, root).replace(os.sep, "/")
        lines.append(f"| {relative} | {info['id']} | {info['closure']} | {info['iteration']} | {updated} "
                     f"| {info['destination']} |")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
