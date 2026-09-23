"""Shared helpers for Question Map scripts."""

import re


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
