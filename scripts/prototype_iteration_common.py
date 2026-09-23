"""Shared helpers for Question Map scripts."""

import os
import re
import sys


def get_markdown_field(text, name):
    pattern = r"(?m)^\s*-\s*`" + re.escape(name) + r"`:\s*(.+?)\s*$"
    match = re.search(pattern, text)
    if match is None:
        return None
    return match.group(1).strip()


def read_markdown_fields(path, names):
    with open(path, encoding="utf-8-sig") as handle:
        text = handle.read()
    values = {name: get_markdown_field(text, name) for name in names}
    return {"text": text, "values": values}


def resolve_ref(ref, base_dir):
    """Resolve a file reference: absolute as-is, relative to the file that declares it."""
    if not isinstance(ref, str):
        return None
    path = os.path.expanduser(ref)
    if not os.path.isabs(path):
        path = os.path.join(base_dir, path)
    return os.path.normpath(os.path.abspath(path))


def same_ref(left, left_base, right, right_base):
    if left is None or right is None:
        return left is None and right is None
    return resolve_ref(left, left_base) == resolve_ref(right, right_base)


def is_blank(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def parse_int(value):
    if not isinstance(value, str) or not re.fullmatch(r"\s*[+-]?\d+\s*", value):
        return None
    return int(value)


def display(value):
    return "" if value is None else str(value)


def use_utf8_output():
    """Keep non-ASCII map content printable when output is piped on Windows."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
