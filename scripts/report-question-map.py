#!/usr/bin/env python3
"""Print a read-only Markdown summary of a Question Map JSON file."""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prototype_iteration_common import display, is_blank  # noqa: E402


def get(obj, name):
    if not isinstance(obj, dict):
        return None
    return obj.get(name)


def get_array(obj, name):
    value = get(obj, name)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def format_counts(items, selector):
    if not items:
        return "none"
    counts = Counter(selector(item) for item in items)
    return ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def display_value(obj, name, default="none"):
    value = get(obj, name)
    return default if is_blank(value) else str(value)


def preferred_display_value(obj, selected_name, recommended_name):
    selected = display_value(obj, selected_name)
    if selected != "none":
        return selected
    return display_value(obj, recommended_name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="question-map.json")
    path = parser.parse_args().path

    if not os.path.isfile(path):
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    try:
        with open(path, encoding="utf-8-sig") as handle:
            document = json.load(handle)
    except (ValueError, OSError) as exc:
        print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
        return 1

    questions = get_array(document, "questions")
    insights = get_array(document, "insights")
    possible_gaps = get_array(document, "possible_gaps")
    baseline = get(document, "design_baseline")
    intents = get_array(baseline, "intents")
    nodes = get_array(baseline, "nodes")
    changes = get_array(get(document, "delta"), "changes")
    closure = get(document, "closure")
    iteration = get(document, "iteration")
    acceptance = get(document, "acceptance")
    integration = get(acceptance, "integration")
    closure_status = get(closure, "status")
    if is_blank(closure_status):
        closure_status = "legacy / not declared"
    next_skill = get(closure, "next_skill")
    if is_blank(next_skill):
        next_skill = "none"

    mode_summary = format_counts(
        questions, lambda q: "unknown" if is_blank(get(q, "mode")) else str(get(q, "mode")))
    status_summary = format_counts(
        questions, lambda q: "legacy" if is_blank(get(q, "status")) else str(get(q, "status")))

    blockers = []
    for question in questions:
        if get(question, "status") in ("resolved", "superseded"):
            continue
        relations = get(question, "relations")
        for relation_name in ("blocks_decision", "blocks_verification", "blocks_build"):
            for target in get_array(relations, relation_name):
                blockers.append(f"{display(get(question, 'id'))} [{relation_name}] -> {display(target)}")

    remaining = set()
    for question_id in get_array(closure, "remaining_verifications"):
        if isinstance(question_id, str):
            remaining.add(question_id)
    for question in questions:
        if get(question, "mode") != "verify":
            continue
        if get(get(question, "verification"), "status") != "passed":
            question_id = get(question, "id")
            if isinstance(question_id, str):
                remaining.add(question_id)

    rerun_count = 0 if iteration is None else display(get(iteration, "rerun_count"))
    acceptance_status = "not declared" if acceptance is None else display(get(acceptance, "status"))
    integration_status = "not declared" if integration is None else display(get(integration, "status"))
    closure_rationale = get(closure, "rationale")

    lines = [
        "# Question Map Report",
        "",
        f"- Question Map: {display(get(document, 'question_map_id'))}",
        f"- Destination: {display(get(document, 'destination'))}",
        f"- Closure: {closure_status}",
        f"- Next skill: {next_skill}",
        f"- Active region: {display_value(iteration, 'active_region_ref')}",
        f"- Iteration state: {display_value(iteration, 'state')}",
        f"- Rerun count: {rerun_count}",
        f"- Next run: {preferred_display_value(iteration, 'selected_run_mode', 'recommended_run_mode')}",
        f"- Handoff: {preferred_display_value(iteration, 'selected_handoff', 'recommended_handoff')}",
        f"- Brief: {display_value(iteration, 'brief_ref')}",
        f"- Recommended run: {display_value(iteration, 'recommended_run_mode')}",
        f"- Selected run: {display_value(iteration, 'selected_run_mode')}",
        f"- Recommended handoff: {display_value(iteration, 'recommended_handoff')}",
        f"- Selected handoff: {display_value(iteration, 'selected_handoff')}",
        f"- Acceptance: {acceptance_status}",
        f"- Integration: {integration_status}",
        "",
        "## Counts",
        "",
        "| Item | Count |",
        "|---|---:|",
        f"| Questions | {len(questions)} |",
        f"| Insights | {len(insights)} |",
        f"| Possible gaps | {len(possible_gaps)} |",
        f"| Intents | {len(intents)} |",
        f"| Nodes | {len(nodes)} |",
        f"| Delta changes | {len(changes)} |",
        "",
        "## Modes",
        "",
        mode_summary,
        "",
        "## Statuses",
        "",
        status_summary,
        "",
        "## Current blockers",
        "",
        *([f"- {blocker}" for blocker in blockers] or ["- none"]),
        "",
        "## Remaining verifications",
        "",
        *([f"- {question_id}" for question_id in sorted(remaining)] or ["- none"]),
        "",
        "## Closure rationale",
        "",
        "not declared" if is_blank(closure_rationale) else str(closure_rationale),
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
