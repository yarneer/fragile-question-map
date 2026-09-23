#!/usr/bin/env python3
"""Validate a Prototype Run Brief Markdown file."""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prototype_iteration_common import is_blank, parse_int, read_markdown_fields  # noqa: E402

REQUIRED_FIELDS = [
    "brief_id", "status", "active_region_ref", "parent_seed_ref", "run_mode", "iteration_number",
    "checkpoint", "restored_preconditions", "changed_slice", "evidence_goal", "completion_criteria",
    "appetite", "coverage_limit",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="prototype-run-brief.md")
    path = parser.parse_args().path

    if not os.path.isfile(path):
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1

    errors = []
    artifact = read_markdown_fields(path, REQUIRED_FIELDS)
    if not re.search(r"(?m)^# Prototype Run Brief\s*$", artifact["text"]):
        errors.append("document must start with a Prototype Run Brief heading")

    values = artifact["values"]
    for field in REQUIRED_FIELDS:
        if is_blank(values[field]):
            errors.append(f"{field} must be non-empty")

    if values["status"] is not None and values["status"] not in ("draft", "final"):
        errors.append(f"status '{values['status']}' is invalid")
    if values["run_mode"] is not None and values["run_mode"] not in ("full", "changed_slice"):
        errors.append(f"run_mode '{values['run_mode']}' is invalid")
    parent_seed_ref = values["parent_seed_ref"]
    if parent_seed_ref is not None:
        if not os.path.isabs(parent_seed_ref):
            errors.append("parent_seed_ref must be an absolute file path")
        elif not os.path.isfile(parent_seed_ref):
            errors.append(f"parent_seed_ref file does not exist: {parent_seed_ref}")

    iteration_number = 0
    if values["iteration_number"] is not None:
        parsed = parse_int(values["iteration_number"])
        if parsed is None or parsed < 1:
            errors.append("iteration_number must be a positive integer")
        iteration_number = parsed or 0
    appetite = 0
    if values["appetite"] is not None:
        parsed = parse_int(values["appetite"])
        if parsed is None or parsed < 1:
            errors.append("appetite must be a positive integer")
        appetite = parsed or 0

    if values["run_mode"] == "changed_slice":
        for field in ("parent_seed_ref", "checkpoint", "restored_preconditions", "changed_slice"):
            if values[field] in ("none", "null", "not_applicable"):
                errors.append(f"changed_slice requires concrete {field}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"RESULT: invalid, errors={len(errors)}", file=sys.stderr)
        return 1

    print("PASS: Prototype Run Brief is valid")
    print(f"RESULT: brief_id={values['brief_id']}, run_mode={values['run_mode']}, "
          f"iteration={iteration_number}, appetite={appetite}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
