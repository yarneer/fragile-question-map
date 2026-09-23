#!/usr/bin/env python3
"""Validate a Question Map JSON file (v0.1 legacy, v0.2, v0.3)."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prototype_iteration_common import (  # noqa: E402
    use_utf8_output, display, is_blank, is_int, parse_int, read_markdown_fields, resolve_ref, same_ref,
)

ALLOWED_MODES = ("discuss", "verify", "fact", "park")
ALLOWED_CONFIDENCE = ("provisional", "supported", "uncertain")
ALLOWED_QUESTION_STATUSES = ("open", "resolved", "superseded", "deferred")
ALLOWED_VERIFICATION_STATUSES = ("not_planned", "planned", "running", "passed", "failed", "partial")
ALLOWED_CLOSURE_STATUSES = ("active", "design_closed", "fully_verified", "superseded")
ALLOWED_ITERATION_STATES = ("exploring", "ready_for_rerun", "brief_ready", "awaiting_seed",
                            "evidence_received", "stalled", "accepted")
ALLOWED_ACCEPTANCE_STATUSES = ("not_requested", "pending", "accepted_with_unverified_integration", "validated")
ALLOWED_INTEGRATION_STATUSES = ("not_verified", "planned", "running", "passed", "failed", "partial")
RELATION_NAMES = ("blocks_decision", "blocks_verification", "blocks_build", "depends_on", "informs", "conflicts_with")
ALLOWED_NODE_STATUSES = ("mvp", "later", "fog", "deferred", "rejected")
SCOPE_RELATIONS = ("current", "bubble_up", "informs", "park", "build_dependency")
CHANGE_TYPES = ("clarified", "split", "linked", "invalidated", "new_intent", "scope_change")
BRIEF_FIELDS = [
    "brief_id", "status", "active_region_ref", "parent_seed_ref", "run_mode", "iteration_number",
    "checkpoint", "restored_preconditions", "changed_slice", "evidence_goal", "completion_criteria",
    "appetite", "coverage_limit",
]
SEED_FIELDS = [
    "seed_id", "status", "parent_seed_ref", "run_mode", "tested_slice", "input_brief_ref",
    "starting_checkpoint", "restored_preconditions",
]
POST_BRIEF_STATES = ("brief_ready", "awaiting_seed", "evidence_received", "stalled", "accepted")
SCHEMA_VERSIONS = ("0.1", "0.2", "0.3")

errors = []
warnings = []
# Directory of the Question Map file; relative file references resolve against it.
map_dir = os.getcwd()


def add_error(message):
    errors.append(message)


def add_warning(message):
    warnings.append(message)


def get(obj, name):
    if not isinstance(obj, dict):
        return None
    return obj.get(name)


def has(obj, name):
    return isinstance(obj, dict) and name in obj


def require_text(obj, name, context):
    value = get(obj, name)
    if not isinstance(value, str) or value.strip() == "":
        add_error(f"{context}.{name} must be non-empty text")
        return None
    return value


def nullable_text(obj, name, context, required=True):
    if not has(obj, name):
        if required:
            add_error(f"{context}.{name} is required")
        return None
    value = get(obj, name)
    if value is not None and (not isinstance(value, str) or value.strip() == ""):
        add_error(f"{context}.{name} must be non-empty text or null")
        return None
    return value


def nullable_timestamp(obj, name, context, required=True):
    if not has(obj, name):
        if required:
            add_error(f"{context}.{name} is required")
        return None
    value = get(obj, name)
    if value is not None and (not isinstance(value, str) or value.strip() == ""):
        add_error(f"{context}.{name} must be timestamp text or null")
        return None
    return value


def array_items(obj, name, context, required=True):
    value = get(obj, name)
    if value is None:
        if required:
            add_error(f"{context}.{name} must be an array")
        return []
    if isinstance(value, (str, dict)):
        add_error(f"{context}.{name} must be an array")
        return []
    return value if isinstance(value, list) else [value]


def assert_text_items(items, context):
    for item in items:
        if not isinstance(item, str) or item.strip() == "":
            add_error(f"{context} must contain only non-empty text")


def assert_known_properties(obj, allowed, context):
    if not isinstance(obj, dict):
        return
    for property_name in obj:
        if property_name not in allowed:
            add_warning(f"{context}.{property_name} is an undeclared extension field")


def add_unique_id(id_set, item_id, context):
    if is_blank(item_id):
        return
    if item_id in id_set:
        add_error(f"{context} id '{item_id}' is duplicated")
    id_set.add(item_id)


def read_referenced_markdown_fields(referenced_path, names, context):
    resolved = resolve_ref(referenced_path, map_dir)
    if resolved is None:
        add_error(f"{context} must be a file path")
        return None
    if not os.path.isfile(resolved):
        add_error(f"{context} file does not exist: {referenced_path} (resolved: {resolved})")
        return None
    try:
        artifact = read_markdown_fields(resolved, names)
    except (OSError, UnicodeDecodeError) as exc:
        add_error(f"{context} could not be read: {exc}")
        return None
    artifact["dir"] = os.path.dirname(resolved)
    return artifact


def assert_markdown_field_equals(fields, name, expected, context):
    actual = fields.get(name)
    if is_blank(actual):
        add_error(f"{context}.{name} must be non-empty")
    elif actual != expected:
        add_error(f"{context}.{name} '{actual}' does not match '{display(expected)}'")


def assert_markdown_ref_equals(artifact, name, expected, context):
    """Compare a path field declared in a Markdown file against a path declared in the map."""
    actual = artifact["values"].get(name)
    if is_blank(actual):
        add_error(f"{context}.{name} must be non-empty")
    elif not same_ref(actual, artifact["dir"], expected, map_dir):
        add_error(f"{context}.{name} '{actual}' does not match '{display(expected)}'")


def find_question(questions, question_id):
    matches = [q for q in questions if get(q, "id") == question_id]
    return matches[0] if matches else None


def validate(document):
    assert_known_properties(document, (
        "question_map_id", "destination", "scope", "out_of_scope", "source_lineage", "questions", "insights",
        "possible_gaps", "design_baseline", "mvp_seed", "delta", "iteration", "acceptance", "closure",
        "schema_version",
    ), "root")

    require_text(document, "question_map_id", "root")
    require_text(document, "destination", "root")
    assert_text_items(array_items(document, "scope", "root"), "root.scope")
    assert_text_items(array_items(document, "out_of_scope", "root"), "root.out_of_scope")

    questions = array_items(document, "questions", "root")
    if not questions:
        add_error("root.questions must contain at least one question")
    baseline = get(document, "design_baseline")
    mvp_seed = get(document, "mvp_seed")
    if baseline is None:
        add_error("root.design_baseline is required")
    if mvp_seed is None:
        add_error("root.mvp_seed is required")

    has_v03_fields = has(document, "iteration") or has(document, "acceptance")
    has_v02_fields = (has(document, "closure") or has(document, "possible_gaps") or has(document, "source_lineage")
                      or any(has(q, "status") or has(q, "resolution") or has(q, "verification") for q in questions))
    inferred_version = "0.3" if has_v03_fields else "0.2" if has_v02_fields else "0.1"
    schema_version = inferred_version
    if not has(document, "schema_version"):
        add_warning(f"root.schema_version is not declared; inferred '{inferred_version}' from present fields")
    else:
        declared = get(document, "schema_version")
        if declared not in SCHEMA_VERSIONS:
            add_error(f"root.schema_version '{display(declared)}' is invalid; expected one of {', '.join(SCHEMA_VERSIONS)}")
        else:
            schema_version = declared
            if declared < inferred_version:
                add_error(f"root.schema_version '{declared}' is older than the fields present, which require '{inferred_version}'")
    is_v03 = schema_version == "0.3"
    is_v02_or_later = schema_version in ("0.2", "0.3")

    question_ids = set()
    for index, question in enumerate(questions):
        add_unique_id(question_ids, require_text(question, "id", f"questions[{index}]"), "question")

    intent_ids = set()
    node_ids = set()
    intents = []
    nodes = []
    expected_baseline_ref = None
    if baseline is not None:
        assert_known_properties(baseline, ("id", "revision", "intents", "nodes"), "design_baseline")
        baseline_id = require_text(baseline, "id", "design_baseline")
        revision = get(baseline, "revision")
        if not is_int(revision):
            add_error("design_baseline.revision must be an integer")
        elif revision < 1:
            add_error("design_baseline.revision must be greater than zero")
        if baseline_id is not None and revision is not None:
            expected_baseline_ref = f"{baseline_id}@{revision}"
        intents = array_items(baseline, "intents", "design_baseline")
        nodes = array_items(baseline, "nodes", "design_baseline")
        if not intents:
            add_error("design_baseline.intents must contain at least one intent")
        if not nodes:
            add_error("design_baseline.nodes must contain at least one node")
        for index, intent in enumerate(intents):
            context = f"design_baseline.intents[{index}]"
            assert_known_properties(intent, ("id", "statement", "evidence"), context)
            add_unique_id(intent_ids, require_text(intent, "id", context), "intent")
        for index, node in enumerate(nodes):
            context = f"design_baseline.nodes[{index}]"
            assert_known_properties(node, ("id", "title", "status", "intent_ids", "parent_ids", "rationale"), context)
            add_unique_id(node_ids, require_text(node, "id", context), "node")

    known_ids = question_ids | node_ids

    for index, question in enumerate(questions):
        context = f"questions[{index}]"
        assert_known_properties(question, (
            "id", "title", "mode", "intent", "question", "evidence_needed", "relations", "confidence",
            "status", "resolution", "verification",
        ), context)
        require_text(question, "title", context)
        require_text(question, "intent", context)
        require_text(question, "question", context)
        mode = require_text(question, "mode", context)
        if mode is not None and mode not in ALLOWED_MODES:
            add_error(f"{context}.mode '{mode}' is invalid")
        confidence = require_text(question, "confidence", context)
        if confidence is not None and confidence not in ALLOWED_CONFIDENCE:
            add_error(f"{context}.confidence '{confidence}' is invalid")
        if mode == "verify":
            require_text(question, "evidence_needed", context)

        relations = get(question, "relations")
        if relations is None:
            add_error(f"{context}.relations is required")
        else:
            assert_known_properties(relations, RELATION_NAMES, f"{context}.relations")
            for relation_name in RELATION_NAMES:
                for target in array_items(relations, relation_name, f"{context}.relations", required=False):
                    if not isinstance(target, str) or target.strip() == "":
                        add_error(f"{context}.relations.{relation_name} contains an invalid target")
                    elif target not in known_ids:
                        add_error(f"{context}.relations.{relation_name} targets missing id '{target}'")

        status = None
        if is_v02_or_later or has(question, "status"):
            status = require_text(question, "status", context)
            if status is not None and status not in ALLOWED_QUESTION_STATUSES:
                add_error(f"{context}.status '{status}' is invalid")

        resolution = get(question, "resolution")
        if is_v02_or_later and resolution is None:
            add_error(f"{context}.resolution is required for v0.2")
        elif resolution is not None:
            res_context = f"{context}.resolution"
            assert_known_properties(resolution, ("decision", "evidence", "confirmed_at", "superseded_by"), res_context)
            decision = nullable_text(resolution, "decision", res_context, is_v02_or_later)
            nullable_text(resolution, "evidence", res_context, is_v02_or_later)
            nullable_timestamp(resolution, "confirmed_at", res_context, is_v02_or_later)
            superseded_by = nullable_text(resolution, "superseded_by", res_context, is_v02_or_later)
            if superseded_by is not None and superseded_by not in question_ids:
                add_error(f"{res_context}.superseded_by targets missing question '{superseded_by}'")
            if status == "superseded" and is_blank(superseded_by):
                add_error(f"{context}.status superseded requires resolution.superseded_by")
            if mode == "discuss" and status == "resolved" and is_blank(decision):
                add_warning(f"{context} is resolved discuss but resolution.decision is empty")

        verification = get(question, "verification")
        if is_v02_or_later and verification is None:
            add_error(f"{context}.verification is required for v0.2")
        elif verification is not None:
            ver_context = f"{context}.verification"
            assert_known_properties(verification, ("status", "plan", "evidence", "last_run_at"), ver_context)
            verification_status = require_text(verification, "status", ver_context)
            if verification_status is not None and verification_status not in ALLOWED_VERIFICATION_STATUSES:
                add_error(f"{ver_context}.status '{verification_status}' is invalid")
            plan = array_items(verification, "plan", ver_context)
            evidence = array_items(verification, "evidence", ver_context)
            assert_text_items(plan, f"{ver_context}.plan")
            assert_text_items(evidence, f"{ver_context}.evidence")
            nullable_timestamp(verification, "last_run_at", ver_context, is_v02_or_later)
            if verification_status == "planned" and not plan:
                add_warning(f"{context} verification is planned but plan is empty")
            if verification_status in ("running", "passed", "failed", "partial") and not evidence:
                add_warning(f"{context} verification status '{verification_status}' has no execution evidence")

    for index, intent in enumerate(intents):
        require_text(intent, "statement", f"design_baseline.intents[{index}]")
        require_text(intent, "evidence", f"design_baseline.intents[{index}]")

    for index, node in enumerate(nodes):
        context = f"design_baseline.nodes[{index}]"
        require_text(node, "title", context)
        require_text(node, "rationale", context)
        status = require_text(node, "status", context)
        if status is not None and status not in ALLOWED_NODE_STATUSES:
            add_error(f"{context}.status '{status}' is invalid")
        node_intent_ids = array_items(node, "intent_ids", context)
        if not node_intent_ids:
            add_error(f"{context}.intent_ids must contain at least one intent")
        for intent_id in node_intent_ids:
            if not isinstance(intent_id, str) or intent_id not in intent_ids:
                add_error(f"{context}.intent_ids targets missing intent '{display(intent_id)}'")
        for parent_id in array_items(node, "parent_ids", context, required=False):
            if not isinstance(parent_id, str) or parent_id not in node_ids:
                add_error(f"{context}.parent_ids targets missing node '{display(parent_id)}'")

    insights = array_items(document, "insights", "root", required=False)
    insight_ids = set()
    bubble_up_insights = []
    for index, insight in enumerate(insights):
        context = f"insights[{index}]"
        assert_known_properties(insight, (
            "id", "origin", "raw", "scope_relation", "mode", "relation", "confidence", "is_new_intent",
            "intent_id", "rationale",
        ), context)
        add_unique_id(insight_ids, require_text(insight, "id", context), "insight")
        origin = require_text(insight, "origin", context)
        if origin is not None and origin not in known_ids:
            add_error(f"{context}.origin targets missing id '{origin}'")
        require_text(insight, "raw", context)
        require_text(insight, "rationale", context)
        scope_relation = require_text(insight, "scope_relation", context)
        if scope_relation is not None and scope_relation not in SCOPE_RELATIONS:
            add_error(f"{context}.scope_relation '{scope_relation}' is invalid")
        if scope_relation == "bubble_up":
            bubble_up_insights.append((context, origin))
        mode = require_text(insight, "mode", context)
        if mode is not None and mode not in ALLOWED_MODES:
            add_error(f"{context}.mode '{mode}' is invalid")
        confidence = require_text(insight, "confidence", context)
        if confidence is not None and confidence not in ALLOWED_CONFIDENCE:
            add_error(f"{context}.confidence '{confidence}' is invalid")
        relation = require_text(insight, "relation", context)
        if relation is not None and relation not in RELATION_NAMES:
            add_error(f"{context}.relation '{relation}' is invalid")
        if scope_relation == "build_dependency" and relation != "blocks_build":
            add_error(f"{context} build_dependency must use relation blocks_build")
        is_new_intent = get(insight, "is_new_intent")
        if not isinstance(is_new_intent, bool):
            add_error(f"{context}.is_new_intent must be boolean")
        elif is_new_intent:
            insight_intent_id = require_text(insight, "intent_id", context)
            if insight_intent_id is not None and insight_intent_id not in intent_ids:
                add_error(f"{context}.intent_id targets missing intent '{insight_intent_id}'")

    possible_gaps = array_items(document, "possible_gaps", "root", required=is_v02_or_later)
    gap_ids = set()
    for index, gap in enumerate(possible_gaps):
        context = f"possible_gaps[{index}]"
        assert_known_properties(gap, (
            "id", "observation", "source_refs", "evidence_type", "confidence", "reason_not_open",
        ), context)
        add_unique_id(gap_ids, require_text(gap, "id", context), "possible_gap")
        require_text(gap, "observation", context)
        assert_text_items(array_items(gap, "source_refs", context), f"{context}.source_refs")
        evidence_type = require_text(gap, "evidence_type", context)
        if evidence_type is not None and evidence_type != "model_inference":
            add_error(f"{context}.evidence_type must be 'model_inference'")
        gap_confidence = require_text(gap, "confidence", context)
        if gap_confidence is not None and gap_confidence not in ("provisional", "unknown"):
            add_error(f"{context}.confidence '{gap_confidence}' is invalid")
        require_text(gap, "reason_not_open", context)

    source_lineage = array_items(document, "source_lineage", "root", required=False)
    for index, source in enumerate(source_lineage):
        context = f"source_lineage[{index}]"
        assert_known_properties(source, (
            "source_id", "source_type", "source_ref", "parent_source_ref", "run_mode", "tested_slice", "status",
            "active_region_ref", "brief_ref", "iteration_number",
        ), context)
        require_text(source, "source_id", context)
        require_text(source, "source_type", context)
        require_text(source, "source_ref", context)
        parent_source_ref = nullable_text(source, "parent_source_ref", context)
        run_mode = require_text(source, "run_mode", context)
        if run_mode is not None and run_mode not in ("full", "changed_slice"):
            add_error(f"{context}.run_mode '{run_mode}' is invalid")
        require_text(source, "tested_slice", context)
        source_status = require_text(source, "status", context)
        if source_status is not None and source_status not in ("draft", "final"):
            add_error(f"{context}.status '{source_status}' is invalid")
        if source_status == "draft":
            add_warning(f"{context} is draft and should not be treated as confirmed provenance")
        if run_mode == "changed_slice" and is_blank(parent_source_ref):
            add_error(f"{context} changed_slice requires parent_source_ref")
        if has(source, "active_region_ref"):
            source_region_ref = require_text(source, "active_region_ref", context)
            if source_region_ref is not None and source_region_ref not in known_ids:
                add_error(f"{context}.active_region_ref targets missing id '{source_region_ref}'")
        if has(source, "brief_ref"):
            nullable_text(source, "brief_ref", context)
        if has(source, "iteration_number"):
            source_iteration = get(source, "iteration_number")
            if not is_int(source_iteration) or source_iteration < 1:
                add_error(f"{context}.iteration_number must be a positive integer")

    selected_parent_ids = set()
    if mvp_seed is not None:
        assert_known_properties(mvp_seed, ("id", "baseline_ref", "selected_nodes", "excluded_nodes"), "mvp_seed")
        require_text(mvp_seed, "id", "mvp_seed")
        mvp_baseline_ref = require_text(mvp_seed, "baseline_ref", "mvp_seed")
        if expected_baseline_ref is not None and mvp_baseline_ref != expected_baseline_ref:
            add_error(f"mvp_seed.baseline_ref must equal '{expected_baseline_ref}'")
        selected_nodes = array_items(mvp_seed, "selected_nodes", "mvp_seed")
        if not selected_nodes:
            add_error("mvp_seed.selected_nodes must contain at least one slice")
        for index, selected in enumerate(selected_nodes):
            context = f"mvp_seed.selected_nodes[{index}]"
            assert_known_properties(selected, ("parent_id", "slice", "acceptance"), context)
            parent_id = require_text(selected, "parent_id", context)
            if parent_id is not None:
                selected_parent_ids.add(parent_id)
                if parent_id not in node_ids:
                    add_error(f"{context}.parent_id targets missing node '{parent_id}'")
            require_text(selected, "slice", context)
            require_text(selected, "acceptance", context)
        for excluded_id in array_items(mvp_seed, "excluded_nodes", "mvp_seed", required=False):
            if not isinstance(excluded_id, str) or excluded_id not in node_ids:
                add_error(f"mvp_seed.excluded_nodes targets missing node '{display(excluded_id)}'")

    delta_changes = []
    delta = get(document, "delta")
    if delta is not None:
        assert_known_properties(delta, ("id", "baseline_ref", "changes"), "delta")
        require_text(delta, "id", "delta")
        delta_baseline_ref = require_text(delta, "baseline_ref", "delta")
        if expected_baseline_ref is not None and delta_baseline_ref != expected_baseline_ref:
            add_error(f"delta.baseline_ref must equal '{expected_baseline_ref}'")
        delta_changes = array_items(delta, "changes", "delta")
        for index, change in enumerate(delta_changes):
            context = f"delta.changes[{index}]"
            assert_known_properties(change, ("type", "target_id", "before", "after", "evidence", "decision"), context)
            change_type = require_text(change, "type", context)
            if change_type is not None and change_type not in CHANGE_TYPES:
                add_error(f"{context}.type '{change_type}' is invalid")
            target_id = require_text(change, "target_id", context)
            if target_id is not None and target_id not in known_ids:
                add_error(f"{context}.target_id targets missing id '{target_id}'")
            for field in ("before", "after", "evidence", "decision"):
                require_text(change, field, context)

    for context, origin in bubble_up_insights:
        matching = [c for c in delta_changes
                    if get(c, "target_id") == origin and get(c, "type") in ("invalidated", "scope_change")]
        if not matching:
            add_warning(f"{context} is bubble_up but no invalidated/scope_change delta targets '{display(origin)}'")

    iteration = get(document, "iteration")
    if is_v03 and iteration is None:
        add_error("root.iteration is required for v0.3")
    elif iteration is not None:
        validate_iteration(iteration, questions, known_ids, source_lineage, delta_changes)

    acceptance_status = validate_acceptance(document, is_v03, iteration, questions, question_ids, source_lineage)

    closure = get(document, "closure")
    closure_status = None
    if is_v02_or_later and closure is None:
        add_error("root.closure is required for v0.2")
    elif closure is not None:
        assert_known_properties(closure, ("status", "rationale", "remaining_verifications", "next_skill"), "closure")
        closure_status = require_text(closure, "status", "closure")
        if closure_status is not None and closure_status not in ALLOWED_CLOSURE_STATUSES:
            add_error(f"closure.status '{closure_status}' is invalid")
        require_text(closure, "rationale", "closure")
        remaining_verifications = array_items(closure, "remaining_verifications", "closure")
        for question_id in remaining_verifications:
            if not isinstance(question_id, str) or question_id not in question_ids:
                add_error(f"closure.remaining_verifications targets missing question '{display(question_id)}'")
                continue
            if get(find_question(questions, question_id), "mode") != "verify":
                add_error(f"closure.remaining_verifications '{question_id}' is not a verify question")
        nullable_text(closure, "next_skill", "closure", is_v02_or_later)
        if closure_status == "fully_verified" and remaining_verifications:
            add_error("closure fully_verified requires remaining_verifications to be empty")
        if closure_status == "fully_verified":
            for question in questions:
                if get(question, "mode") != "verify":
                    continue
                verification = get(question, "verification")
                if verification is None or get(verification, "status") != "passed":
                    add_error(f"closure fully_verified requires verify question '{display(get(question, 'id'))}' to be passed")
        if is_v03 and acceptance_status == "validated" and closure_status != "fully_verified":
            add_error("validated acceptance requires closure fully_verified")
        if is_v03 and acceptance_status == "accepted_with_unverified_integration" and closure_status == "fully_verified":
            add_error("accepted_with_unverified_integration cannot use closure fully_verified")
        if is_v03 and closure_status == "fully_verified" and acceptance_status != "validated":
            add_error("v0.3 closure fully_verified requires validated acceptance")

    for question in questions:
        question_id = get(question, "id")
        question_status = get(question, "status")
        if question_status is None:
            question_status = "legacy_open"
        relations = get(question, "relations")
        if relations is None:
            continue
        relation_context = f"question '{display(question_id)}'.relations"
        decision_targets = array_items(relations, "blocks_decision", relation_context, required=False)
        build_targets = array_items(relations, "blocks_build", relation_context, required=False)
        if closure_status == "design_closed" and question_status == "open" and decision_targets:
            add_warning(f"closure is design_closed but open question '{display(question_id)}' still has blocks_decision targets")
        if question_status in ("open", "deferred", "legacy_open"):
            seen = []
            for target in decision_targets + build_targets:
                if target in seen:
                    continue
                seen.append(target)
                if isinstance(target, str) and target in selected_parent_ids:
                    add_warning(f"selected MVP node '{target}' still depends on unresolved question '{display(question_id)}'")

    return len(questions), len(insights), len(intents), len(nodes), (
        f"v{schema_version}" + ("-legacy" if schema_version == "0.1" else ""))


def relates_to_region(question, active_region_ref, context):
    relations = get(question, "relations")
    for relation_name in RELATION_NAMES:
        if active_region_ref in array_items(relations, relation_name, context, required=False):
            return True
    return False


def validate_iteration(iteration, questions, known_ids, source_lineage, delta_changes):
    assert_known_properties(iteration, (
        "active_region_ref", "state", "current_seed_ref", "last_full_seed_ref", "parent_seed_ref", "brief_ref",
        "iteration_number", "rerun_count", "recommended_run_mode", "selected_run_mode", "recommendation_rationale",
        "recommended_handoff", "selected_handoff",
    ), "iteration")
    active_region_ref = require_text(iteration, "active_region_ref", "iteration")
    if active_region_ref is not None and active_region_ref not in known_ids:
        add_error(f"iteration.active_region_ref targets missing id '{active_region_ref}'")
    state = require_text(iteration, "state", "iteration")
    if state is not None and state not in ALLOWED_ITERATION_STATES:
        add_error(f"iteration.state '{state}' is invalid")
    current_seed_ref = require_text(iteration, "current_seed_ref", "iteration")
    last_full_seed_ref = nullable_text(iteration, "last_full_seed_ref", "iteration")
    parent_seed_ref = nullable_text(iteration, "parent_seed_ref", "iteration")
    brief_ref = nullable_text(iteration, "brief_ref", "iteration")
    iteration_number = get(iteration, "iteration_number")
    if not is_int(iteration_number) or iteration_number < 1:
        add_error("iteration.iteration_number must be a positive integer")
    rerun_count = get(iteration, "rerun_count")
    if not is_int(rerun_count) or rerun_count < 0:
        add_error("iteration.rerun_count must be a non-negative integer")
    recommended_run_mode = nullable_text(iteration, "recommended_run_mode", "iteration")
    selected_run_mode = nullable_text(iteration, "selected_run_mode", "iteration")
    for mode_value in (recommended_run_mode, selected_run_mode):
        if mode_value is not None and mode_value not in ("full", "changed_slice"):
            add_error(f"iteration run mode '{mode_value}' is invalid")
    recommendation_rationale = nullable_text(iteration, "recommendation_rationale", "iteration")
    recommended_handoff = nullable_text(iteration, "recommended_handoff", "iteration")
    selected_handoff = nullable_text(iteration, "selected_handoff", "iteration")
    for handoff_value in (recommended_handoff, selected_handoff):
        if handoff_value is not None and handoff_value not in ("A", "B", "C"):
            add_error(f"iteration handoff '{handoff_value}' is invalid")

    current_source = [s for s in source_lineage if same_ref(get(s, "source_ref"), map_dir, current_seed_ref, map_dir)]
    if len(current_source) != 1:
        add_error("iteration.current_seed_ref must match exactly one source_lineage source_ref")
    elif get(current_source[0], "status") != "final":
        add_error("iteration.current_seed_ref must reference a Final Seed")
    if last_full_seed_ref is not None:
        last_full = [s for s in source_lineage if same_ref(get(s, "source_ref"), map_dir, last_full_seed_ref, map_dir)
                     and get(s, "run_mode") == "full" and get(s, "status") == "final"]
        if len(last_full) != 1:
            add_error("iteration.last_full_seed_ref must reference exactly one Final full Seed")

    if state == "ready_for_rerun":
        if not delta_changes:
            add_error("iteration ready_for_rerun requires at least one delta change")
        has_related_delta = False
        for change in delta_changes:
            target_id = get(change, "target_id")
            if target_id == active_region_ref:
                has_related_delta = True
                break
            matches = [q for q in questions if get(q, "id") == target_id]
            if len(matches) != 1:
                continue
            if relates_to_region(matches[0], active_region_ref,
                                 f"delta target question '{display(target_id)}'.relations"):
                has_related_delta = True
                break
        if not has_related_delta:
            add_error("iteration ready_for_rerun requires a delta related to the active region")
        has_related_evidence_goal = False
        for question in questions:
            if get(question, "mode") != "verify" or is_blank(get(question, "evidence_needed")) \
                    or not isinstance(get(question, "evidence_needed"), str):
                continue
            if relates_to_region(question, active_region_ref,
                                 f"question '{display(get(question, 'id'))}'.relations"):
                has_related_evidence_goal = True
                break
        if not has_related_evidence_goal:
            add_error("iteration ready_for_rerun requires a Verify evidence goal related to the active region")
        if recommended_run_mode is None:
            add_error("iteration ready_for_rerun requires recommended_run_mode")
        if recommendation_rationale is None:
            add_error("iteration ready_for_rerun requires recommendation_rationale")
        if parent_seed_ref is None:
            add_error("iteration ready_for_rerun requires parent_seed_ref")
        if any(v is not None for v in (selected_run_mode, brief_ref, recommended_handoff, selected_handoff)):
            add_error("iteration ready_for_rerun cannot already contain selected mode, Brief, or handoff")

    if selected_run_mode is not None and recommended_run_mode is None:
        add_error("iteration.selected_run_mode requires preserved recommended_run_mode")
    if state in POST_BRIEF_STATES:
        if selected_run_mode is None:
            add_error(f"iteration state '{state}' requires selected_run_mode")
        if brief_ref is None:
            add_error(f"iteration state '{state}' requires brief_ref")
        if recommended_handoff is None:
            add_error(f"iteration state '{state}' requires recommended_handoff")

    brief_artifact = None
    if state in POST_BRIEF_STATES and brief_ref is not None:
        brief_artifact = read_referenced_markdown_fields(brief_ref, BRIEF_FIELDS, "iteration.brief_ref")
        if brief_artifact is not None:
            brief_fields = brief_artifact["values"]
            if brief_fields["status"] != "final":
                add_error("iteration Brief must have status final")
            assert_markdown_field_equals(brief_fields, "active_region_ref", active_region_ref, "iteration Brief")
            assert_markdown_ref_equals(brief_artifact, "parent_seed_ref", parent_seed_ref, "iteration Brief")
            assert_markdown_field_equals(brief_fields, "run_mode", selected_run_mode, "iteration Brief")
            brief_iteration_number = parse_int(brief_fields["iteration_number"])
            if brief_iteration_number is None or brief_iteration_number != iteration_number:
                add_error(f"iteration Brief.iteration_number '{display(brief_fields['iteration_number'])}' "
                          f"does not match '{display(iteration_number)}'")

    if state == "brief_ready" and selected_handoff is not None:
        add_error("iteration brief_ready must wait for user handoff selection")
    if state in ("awaiting_seed", "evidence_received", "stalled", "accepted") and selected_handoff is None:
        add_error(f"iteration state '{state}' requires selected_handoff")

    if state in ("evidence_received", "stalled", "accepted") and len(current_source) == 1:
        returned = current_source[0]
        if get(returned, "active_region_ref") != active_region_ref:
            add_error("returned Seed active_region_ref does not match iteration.active_region_ref")
        if not same_ref(get(returned, "brief_ref"), map_dir, brief_ref, map_dir):
            add_error("returned Seed brief_ref does not match iteration.brief_ref")
        if get(returned, "iteration_number") != iteration_number:
            add_error("returned Seed iteration_number does not match iteration.iteration_number")
        if get(returned, "run_mode") != selected_run_mode:
            add_error("returned Seed run_mode does not match iteration.selected_run_mode")
        if not same_ref(get(returned, "parent_source_ref"), map_dir, parent_seed_ref, map_dir):
            add_error("returned Seed parent_source_ref does not match iteration.parent_seed_ref")
        seed_artifact = read_referenced_markdown_fields(get(returned, "source_ref"), SEED_FIELDS,
                                                        "returned Seed source_ref")
        if seed_artifact is not None and brief_artifact is not None:
            seed_fields = seed_artifact["values"]
            brief_fields = brief_artifact["values"]
            if seed_fields["status"] != "final":
                add_error("returned Seed Markdown must have status final")
            assert_markdown_ref_equals(seed_artifact, "parent_seed_ref", parent_seed_ref, "returned Seed")
            assert_markdown_field_equals(seed_fields, "run_mode", selected_run_mode, "returned Seed")
            assert_markdown_ref_equals(seed_artifact, "input_brief_ref", brief_ref, "returned Seed")
            assert_markdown_field_equals(seed_fields, "tested_slice", brief_fields["changed_slice"], "returned Seed")
            assert_markdown_field_equals(seed_fields, "starting_checkpoint", brief_fields["checkpoint"], "returned Seed")
            assert_markdown_field_equals(seed_fields, "restored_preconditions",
                                         brief_fields["restored_preconditions"], "returned Seed")
            assert_markdown_field_equals(seed_fields, "tested_slice", get(returned, "tested_slice"), "source_lineage")

    if is_int(rerun_count) and rerun_count >= 3:
        add_warning("rerun_count reached 3; choose redefine, add_evidence, Park, or continue explicitly")


def validate_acceptance(document, is_v03, iteration, questions, question_ids, source_lineage):
    acceptance = get(document, "acceptance")
    acceptance_status = None
    if is_v03 and acceptance is None:
        add_error("root.acceptance is required for v0.3")
    elif acceptance is not None:
        assert_known_properties(acceptance, ("status", "decision", "confirmed_at", "integration"), "acceptance")
        acceptance_status = require_text(acceptance, "status", "acceptance")
        if acceptance_status is not None and acceptance_status not in ALLOWED_ACCEPTANCE_STATUSES:
            add_error(f"acceptance.status '{acceptance_status}' is invalid")
        decision = nullable_text(acceptance, "decision", "acceptance")
        confirmed_at = nullable_timestamp(acceptance, "confirmed_at", "acceptance")
        integration = get(acceptance, "integration")
        if integration is None:
            add_error("acceptance.integration is required")
        else:
            validate_integration(integration, acceptance_status, decision, confirmed_at, iteration,
                                 questions, question_ids, source_lineage)

    if is_v03 and iteration is not None and get(iteration, "state") == "accepted" \
            and acceptance_status not in ("accepted_with_unverified_integration", "validated"):
        add_error("iteration.state accepted requires an explicit accepted or validated acceptance status")
    return acceptance_status


def validate_integration(integration, acceptance_status, decision, confirmed_at, iteration,
                         questions, question_ids, source_lineage):
    context = "acceptance.integration"
    assert_known_properties(integration, (
        "status", "verification_question_id", "full_seed_ref", "last_change_iteration",
    ), context)
    integration_status = require_text(integration, "status", context)
    if integration_status is not None and integration_status not in ALLOWED_INTEGRATION_STATUSES:
        add_error(f"{context}.status '{integration_status}' is invalid")
    question_id = nullable_text(integration, "verification_question_id", context)
    if question_id is not None:
        if question_id not in question_ids:
            add_error(f"{context}.verification_question_id targets missing question '{question_id}'")
        elif get(find_question(questions, question_id), "mode") != "verify":
            add_error(f"{context}.verification_question_id '{question_id}' is not a verify question")
    full_seed_ref = nullable_text(integration, "full_seed_ref", context)
    last_change_iteration = get(integration, "last_change_iteration")
    if not is_int(last_change_iteration) or last_change_iteration < 1:
        add_error(f"{context}.last_change_iteration must be a positive integer")

    if acceptance_status in ("not_requested", "pending") and (decision is not None or confirmed_at is not None):
        add_error(f"acceptance status '{acceptance_status}' cannot contain an acceptance decision")
    if acceptance_status in ("accepted_with_unverified_integration", "validated"):
        if decision is None or confirmed_at is None:
            add_error(f"acceptance status '{acceptance_status}' requires explicit decision and confirmed_at")
        if iteration is None or get(iteration, "state") != "accepted":
            add_error(f"acceptance status '{acceptance_status}' requires iteration.state accepted")
    if acceptance_status == "accepted_with_unverified_integration":
        if integration_status == "passed":
            add_error("accepted_with_unverified_integration cannot claim passed integration")
        if full_seed_ref is not None:
            add_error("accepted_with_unverified_integration must not claim a validating full_seed_ref")
    if acceptance_status == "validated":
        if integration_status != "passed":
            add_error("validated requires acceptance.integration.status passed")
        if full_seed_ref is None:
            add_error("validated requires acceptance.integration.full_seed_ref")
        else:
            full_sources = [s for s in source_lineage if same_ref(get(s, "source_ref"), map_dir, full_seed_ref, map_dir)
                            and get(s, "run_mode") == "full" and get(s, "status") == "final"]
            if len(full_sources) != 1:
                add_error("validated full_seed_ref must match exactly one Final full Seed")
            else:
                full_iteration = get(full_sources[0], "iteration_number")
                last_change = last_change_iteration if is_int(last_change_iteration) else 0
                if not is_int(full_iteration) or full_iteration <= last_change:
                    add_error("validated full Seed must occur after the last design change iteration")
            if iteration is not None and not same_ref(get(iteration, "last_full_seed_ref"), map_dir, full_seed_ref, map_dir):
                add_error("validated full_seed_ref must equal iteration.last_full_seed_ref")
        if question_id is None:
            add_error("validated requires acceptance.integration.verification_question_id")
        if question_id is not None and question_id in question_ids:
            verification = get(find_question(questions, question_id), "verification")
            evidence = array_items(verification, "evidence", f"question '{question_id}'.verification", required=False)
            if get(verification, "status") != "passed" or not evidence:
                add_error("validated requires the integration Verify question to be passed with evidence")


def main():
    use_utf8_output()
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

    global map_dir
    map_dir = os.path.dirname(os.path.abspath(path))
    question_count, insight_count, intent_count, node_count, schema = validate(document)

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"RESULT: invalid, errors={len(errors)}, warnings={len(warnings)}", file=sys.stderr)
        return 1

    print("PASS: question map is valid")
    print(f"RESULT: questions={question_count}, insights={insight_count}, intents={intent_count}, "
          f"nodes={node_count}, warnings={len(warnings)}, schema={schema}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
