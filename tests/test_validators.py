"""Contract tests for the Question Map scripts.

Run from the repository root:

    python3 -m unittest discover -s tests
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "validated")
EXAMPLE = os.path.join(ROOT, "references", "examples", "fragile-learn")


def run(script, path, cwd=None):
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script), path],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )
    return result.returncode, result.stdout, result.stderr


class FixtureCase(unittest.TestCase):
    """Each test works on a private copy of the validated fixture."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "map")
        shutil.copytree(FIXTURE, self.dir)
        self.map_path = os.path.join(self.dir, "question-map.json")
        with open(self.map_path, encoding="utf-8") as handle:
            self.base = json.load(handle)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def validate(self, mutate=None, cwd=None):
        document = copy.deepcopy(self.base)
        if mutate is not None:
            mutate(document)
        with open(self.map_path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False)
        return run("validate-question-map.py", self.map_path, cwd=cwd or self.tmp)

    def assertInvalid(self, mutate, *expected_errors):
        code, _, stderr = self.validate(mutate)
        self.assertEqual(code, 1, stderr)
        for expected in expected_errors:
            self.assertIn(f"ERROR: {expected}", stderr)


class ValidMapTests(FixtureCase):
    def test_validated_fixture_passes(self):
        code, stdout, stderr = self.validate()
        self.assertEqual(code, 0, stderr)
        self.assertIn("PASS: question map is valid", stdout)
        self.assertIn("warnings=0, schema=v0.3", stdout)

    def test_example_passes_from_any_working_directory(self):
        code, stdout, stderr = run("validate-question-map.py", os.path.join(EXAMPLE, "question-map.json"),
                                   cwd=self.tmp)
        self.assertEqual(code, 0, stderr)
        self.assertIn("warnings=0", stdout)

    def test_example_brief_passes(self):
        code, _, stderr = run("validate-prototype-run-brief.py", os.path.join(EXAMPLE, "prototype-run-brief.md"),
                              cwd=self.tmp)
        self.assertEqual(code, 0, stderr)


class RelationAndLifecycleTests(FixtureCase):
    def test_relation_to_missing_id(self):
        def mutate(m):
            m["questions"][2]["relations"]["blocks_build"] = ["NX"]
        self.assertInvalid(mutate, "questions[2].relations.blocks_build targets missing id 'NX'")

    def test_superseded_requires_superseded_by(self):
        def mutate(m):
            m["questions"][0]["resolution"]["superseded_by"] = None
        self.assertInvalid(mutate, "questions[0].status superseded requires resolution.superseded_by")

    def test_verify_requires_evidence_needed(self):
        def mutate(m):
            m["questions"][2]["evidence_needed"] = None
        self.assertInvalid(mutate, "questions[2].evidence_needed must be non-empty text")

    def test_validated_full_seed_must_follow_last_change(self):
        def mutate(m):
            m["acceptance"]["integration"]["last_change_iteration"] = 2
        self.assertInvalid(mutate, "validated full Seed must occur after the last design change iteration")

    def test_unverified_acceptance_cannot_claim_integration(self):
        def mutate(m):
            m["acceptance"]["status"] = "accepted_with_unverified_integration"
        self.assertInvalid(
            mutate,
            "accepted_with_unverified_integration cannot claim passed integration",
            "accepted_with_unverified_integration cannot use closure fully_verified",
        )

    def test_third_rerun_only_warns(self):
        def mutate(m):
            m["iteration"]["rerun_count"] = 3
        code, stdout, stderr = self.validate(mutate)
        self.assertEqual(code, 0, stderr)
        self.assertIn("WARNING: rerun_count reached 3", stdout)

    def test_ready_for_rerun_cannot_hold_brief(self):
        def mutate(m):
            m["iteration"]["state"] = "ready_for_rerun"
        self.assertInvalid(mutate, "iteration ready_for_rerun cannot already contain selected mode, Brief, or handoff")


class PathTests(FixtureCase):
    def test_relative_refs_resolve_against_map_not_cwd(self):
        other = os.path.join(self.tmp, "elsewhere")
        os.mkdir(other)
        code, _, stderr = self.validate(cwd=other)
        self.assertEqual(code, 0, stderr)

    def test_absolute_refs_still_work(self):
        def mutate(m):
            for source in m["source_lineage"]:
                source["source_ref"] = os.path.join(self.dir, source["source_ref"])
            iteration = m["iteration"]
            for key in ("current_seed_ref", "last_full_seed_ref", "parent_seed_ref", "brief_ref"):
                iteration[key] = os.path.join(self.dir, iteration[key])
            m["acceptance"]["integration"]["full_seed_ref"] = iteration["last_full_seed_ref"]
        code, _, stderr = self.validate(mutate)
        self.assertEqual(code, 0, stderr)

    def test_missing_brief_file(self):
        os.remove(os.path.join(self.dir, "brief.md"))
        code, _, stderr = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("ERROR: iteration.brief_ref file does not exist: brief.md", stderr)

    def test_brief_must_match_iteration_parent(self):
        with open(os.path.join(self.dir, "brief.md"), encoding="utf-8") as handle:
            text = handle.read()
        with open(os.path.join(self.dir, "brief.md"), "w", encoding="utf-8") as handle:
            handle.write(text.replace("`parent_seed_ref`: seed-v01.md", "`parent_seed_ref`: seed-v02.md"))
        code, _, stderr = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("ERROR: iteration Brief.parent_seed_ref 'seed-v02.md' does not match 'seed-v01.md'", stderr)


class SchemaVersionTests(FixtureCase):
    def test_missing_version_warns_and_infers(self):
        code, stdout, stderr = self.validate(lambda m: m.pop("schema_version"))
        self.assertEqual(code, 0, stderr)
        self.assertIn("WARNING: root.schema_version is not declared; inferred '0.3'", stdout)

    def test_unknown_version(self):
        self.assertInvalid(lambda m: m.update(schema_version="0.9"), "root.schema_version '0.9' is invalid")

    def test_version_older_than_fields(self):
        self.assertInvalid(lambda m: m.update(schema_version="0.2"),
                           "root.schema_version '0.2' is older than the fields present, which require '0.3'")

    def test_declared_version_enforces_required_sections(self):
        def mutate(m):
            m.pop("iteration")
            m.pop("acceptance")
        # Without the declaration this would silently downgrade to v0.2 and pass.
        self.assertInvalid(mutate, "root.iteration is required for v0.3", "root.acceptance is required for v0.3")

    def test_legacy_map_without_version(self):
        def mutate(m):
            for key in ("schema_version", "source_lineage", "possible_gaps", "iteration", "acceptance",
                        "closure", "insights"):
                m.pop(key)
            for question in m["questions"]:
                for key in ("status", "resolution", "verification"):
                    question.pop(key)
        code, stdout, stderr = self.validate(mutate)
        self.assertEqual(code, 0, stderr)
        self.assertIn("schema=v0.1-legacy", stdout)


class BriefTests(FixtureCase):
    def write_brief(self, replacements):
        path = os.path.join(self.dir, "brief.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for old, new in replacements:
            text = text.replace(old, new)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_valid_brief(self):
        code, stdout, stderr = run("validate-prototype-run-brief.py", os.path.join(self.dir, "brief.md"),
                                   cwd=self.tmp)
        self.assertEqual(code, 0, stderr)
        self.assertIn("run_mode=full, iteration=2, appetite=1", stdout)

    def test_changed_slice_requires_concrete_fields(self):
        path = self.write_brief([
            ("`run_mode`: full", "`run_mode`: changed_slice"),
            ("`checkpoint`: start", "`checkpoint`: none"),
            ("`appetite`: 1", "`appetite`: 0"),
        ])
        code, _, stderr = run("validate-prototype-run-brief.py", path, cwd=self.tmp)
        self.assertEqual(code, 1)
        self.assertIn("ERROR: changed_slice requires concrete checkpoint", stderr)
        self.assertIn("ERROR: appetite must be a positive integer", stderr)

    def test_missing_parent_seed(self):
        path = self.write_brief([("seed-v01.md", "seed-missing.md")])
        code, _, stderr = run("validate-prototype-run-brief.py", path, cwd=self.tmp)
        self.assertEqual(code, 1)
        self.assertIn("ERROR: parent_seed_ref file does not exist: seed-missing.md", stderr)


class ReportAndInputTests(FixtureCase):
    def test_report_is_read_only_summary(self):
        before = os.path.getmtime(self.map_path)
        code, stdout, stderr = run("report-question-map.py", self.map_path, cwd=self.tmp)
        self.assertEqual(code, 0, stderr)
        self.assertIn("- Schema version: 0.3", stdout)
        self.assertIn("- Acceptance: validated", stdout)
        self.assertIn("discuss=2, verify=1", stdout)
        self.assertEqual(before, os.path.getmtime(self.map_path))

    def test_missing_file(self):
        for script in ("validate-question-map.py", "validate-prototype-run-brief.py", "report-question-map.py"):
            code, _, stderr = run(script, os.path.join(self.tmp, "nope"))
            self.assertEqual(code, 1, script)
            self.assertIn("ERROR: file not found", stderr)

    def test_invalid_json(self):
        with open(self.map_path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        code, _, stderr = run("validate-question-map.py", self.map_path)
        self.assertEqual(code, 1)
        self.assertIn("ERROR: invalid JSON", stderr)


if __name__ == "__main__":
    unittest.main()
