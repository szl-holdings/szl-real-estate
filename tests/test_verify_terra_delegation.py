"""Regression checks for Terra's publication evidence boundaries."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_terra_delegation", ROOT / "scripts/verify_terra_delegation.py"
)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class DelegationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.governance = self.root / "governance"
        self.publisher = self.root / "publisher"
        self.put(self.source, ".github/workflows/hf-space.yml", "name: verify\non: push\n")
        self.contract = {
            "schema": "szl.estate.alignment/v1",
            "authority": {"governed_fabric": verifier.PUBLISHER_REPO},
            "hub_alias_policy": {
                "duplicate_authority_spaces_forbidden": True,
                "canonical_public_space_slugs": ["terra"],
            },
            "public_bodies": [{
                "id": "terra", "backend_source": verifier.PRODUCT_REPO,
                "presentation_source": verifier.PRESENTATION_SOURCE,
                "publisher_workflow": verifier.PUBLISHER_REPO + ":" + verifier.PUBLISHER_WORKFLOW,
                "product_source_deployment_state": "LINKED_NOT_PUBLISHED",
                "hub_surface": verifier.HF_REPO, "domain": "real-estate",
            }],
        }
        self.put(self.governance, verifier.GOVERNANCE_CONTRACT, json.dumps(self.contract))
        self.put(self.publisher, verifier.PUBLISHER_WORKFLOW, "\n".join((
            "push:", "branches: [main]", "publish-vertical-flagships:",
            "scripts/hf_exact_main_ownership.py",
            "python scripts/hf_publish_vertical_flagships_v4.py",
            "hf-vertical-flagships-receipt.json",
            "HF_ORG_TOKEN: ${{ secrets.HF_ORG_TOKEN }}",
            "HF_WRITE_TOKEN: ${{ secrets.HF_WRITE_TOKEN }}",
            "HF_TOKEN: ${{ secrets.HF_TOKEN }}",
        )))
        self.put(self.publisher, verifier.PUBLISHER_ENTRYPOINT,
                 "from hf_publish_vertical_flagships_v4_impl import main")
        self.put(self.publisher, verifier.PUBLISHER_IMPLEMENTATION, "\n".join((
            'DEPLOYMENT_SOURCE_REPOSITORY = "szl-holdings/a11oy"',
            '"slug": "terra"', f'"source": "{verifier.PRODUCT_URL}"',
            "TERRA_FORGE_MARKER", "load_terra_forge_bundle()",
            '"schema":"szl.build-info/v1"',
            '"schema":"szl.vertical-shell-deployment/v1"', '"hf_repository": rid',
        )))

    @staticmethod
    def put(root, name, text):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_receipt_is_hash_bound_and_does_not_claim_runtime(self):
        with patch.object(verifier, "exact_sha", side_effect=["a" * 40, "b" * 40, "c" * 40]):
            receipt = verifier.verify(self.source, self.governance, self.publisher)
        claimed = receipt.pop("receipt_sha256")
        self.assertEqual(claimed, verifier.digest(json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")))
        self.assertEqual(receipt["product_source_sha"], "a" * 40)
        self.assertEqual(receipt["governance_sha"], "b" * 40)
        self.assertEqual(receipt["publisher_sha"], "c" * 40)
        self.assertIs(receipt["product_source_bytes_published_by_owner"], False)
        self.assertEqual(receipt["live_runtime_state"], "NOT_CHECKED")

    def test_other_yaml_workflow_is_inventoried(self):
        self.put(self.source, ".github/workflows/other.yaml", "name: read-only\n")
        inventory = verifier.scan_source_workflows(self.source)
        self.assertEqual(len(inventory), 2)
        self.assertIn(".github/workflows/other.yaml", inventory)

    def test_secret_in_second_workflow_fails_without_printing_value(self):
        self.put(self.source, ".github/workflows/other.yaml",
                 "env:\n  DEPLOY: ${{ secrets.ALIAS_TOKEN }}\n")
        with self.assertRaises(ValueError) as raised:
            verifier.scan_source_workflows(self.source)
        self.assertNotIn("ALIAS_TOKEN", str(raised.exception))

    def test_other_provider_writer_patterns_fail(self):
        for text in (
            "secrets: inherit",
            "uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@abcdef",
            "run: hf upload SZLHOLDINGS/terra .",
            "run: api.upload_folder(repo_id='SZLHOLDINGS/terra')",
            "env: {TOKEN: '${{ secrets[\"TOKEN_ALIAS\"] }}'}",
        ):
            with self.subTest(pattern=text.split(":")[0]):
                self.put(self.source, ".github/workflows/other.yml", text)
                with self.assertRaises(ValueError):
                    verifier.scan_source_workflows(self.source)

    def test_empty_workflow_inventory_fails(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            verifier.scan_source_workflows(self.root / "missing")

    def test_old_presentation_source_fails(self):
        self.contract["public_bodies"][0]["presentation_source"] = verifier.PRODUCT_REPO
        with self.assertRaisesRegex(ValueError, "presentation_source"):
            verifier.validate_governance(self.contract)

    def test_deployment_claim_or_target_drift_fails(self):
        for key, value in (
            ("product_source_deployment_state", "PUBLISHED"),
            ("hub_surface", "SZLHOLDINGS/terra-assurance"),
            ("publisher_workflow", "szl-holdings/szl-real-estate:.github/workflows/hf-space.yml"),
        ):
            contract = copy.deepcopy(self.contract)
            contract["public_bodies"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                verifier.validate_governance(contract)

    def test_duplicate_terra_body_fails(self):
        self.contract["public_bodies"] *= 2
        with self.assertRaisesRegex(ValueError, "one governed Terra"):
            verifier.validate_governance(self.contract)

    def test_substituted_secret_literals_fail_without_value_output(self):
        workflow = self.publisher / verifier.PUBLISHER_WORKFLOW
        workflow.write_text(workflow.read_text(encoding="utf-8").replace(
            "${{ secrets.HF_TOKEN }}", "TEST_SUBSTITUTED_VALUE"
        ), encoding="utf-8")
        with patch.object(verifier, "exact_sha", return_value="a" * 40):
            with self.assertRaises(ValueError) as raised:
                verifier.verify(self.source, self.governance, self.publisher)
        self.assertNotIn("TEST_SUBSTITUTED_VALUE", str(raised.exception))

    def test_workflow_has_no_inline_python_or_secret_expression(self):
        workflow = (ROOT / ".github/workflows/hf-space.yml").read_text(encoding="utf-8")
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("<<'PY'", workflow)
        self.assertNotIn("paths:", workflow)
        self.assertIn("source/scripts/verify_terra_delegation.py", workflow)

    def test_uncommitted_checkout_cannot_be_pinned(self):
        with patch.object(verifier.subprocess, "check_output", side_effect=["a" * 40, " M file"]):
            with self.assertRaisesRegex(ValueError, "uncommitted"):
                verifier.exact_sha(self.source)

    def test_source_pin_uses_current_surface_and_truth_boundary(self):
        text = (ROOT / "SOURCE_PIN.md").read_text(encoding="utf-8")
        self.assertIn("LINKED_NOT_PUBLISHED", text)
        self.assertIn("hf_publish_vertical_flagships_v4_impl.py", text)
        self.assertIn("https://huggingface.co/spaces/SZLHOLDINGS/terra)", text)
        self.assertNotIn("Space visibility | private", text)


if __name__ == "__main__":
    unittest.main()
