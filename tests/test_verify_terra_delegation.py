"""Regression checks for Terra's publication evidence boundaries."""
from __future__ import annotations

import copy
import importlib.util
import hashlib
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
            "python -I -B scripts/hf_publish_vertical_flagships_v4.py",
            "hf-vertical-flagships-receipt.json",
            "HF_ORG_TOKEN: ${{ secrets.HF_ORG_TOKEN }}",
            "HF_WRITE_TOKEN: ${{ secrets.HF_WRITE_TOKEN }}",
            "HF_TOKEN: ${{ secrets.HF_TOKEN }}",
        )))
        self.put(self.publisher, verifier.PUBLISHER_ENTRYPOINT,
                 "from hf_publish_vertical_flagships_v4_impl import main")
        for target, fixture in (
            (verifier.PUBLISHER_IMPLEMENTATION, "terra_overlay_v4.txt"),
            (verifier.PUBLISHER_BASE_IMPLEMENTATION, "terra_base_v4.txt"),
            (verifier.PUBLISHER_NATIVE_IMPLEMENTATION, "terra_native_v1.txt"),
        ):
            self.put(self.publisher, target, (ROOT / "tests/fixtures" / fixture).read_text())
        for path in verifier.NATIVE_ASSETS_SHA256:
            self.put(self.publisher, path, (ROOT / "tests/fixtures/native-assets" / path).read_text())
        self.make_forge_bundle()

    def make_forge_bundle(self):
        page = ('<html data-szl-vertical-forge="0.2.2"><a href="/panels">Panels</a>'
                '<a href="/build-receipt.json">Receipt</a><script>const EP="/api/live";</script></html>')
        page_hash = hashlib.sha256(page.encode()).hexdigest()
        event = {"artifact_sha256": page_hash, "kind": "generated-index",
                 "path": "terra/index.html", "prev_hash": "0" * 64}
        canonical = lambda value: hashlib.sha256(json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
        event["chain_hash"] = canonical(event)
        header = {"schema": "szl.vertical-forge.receipt/v4", "generator": "szl-vertical-forge/0.2.3",
                  "algorithm": "sha256-canonical-json-chain", "genesis": "0" * 64,
                  "config_sha256": "a" * 64, "vertical_count": 1}
        master = canonical({"header": header, "chain_tip": event["chain_hash"]})
        fleet = {**header, "events": [event], "chain_tip": event["chain_hash"], "master_hash": master}
        artifact = {"schema": "szl.vertical-forge.artifact/v1", "generator": header["generator"],
                    "chain_event": event, "fleet_master_hash": master,
                    "fleet_config_sha256": header["config_sha256"], "vertical": "terra",
                    "config_sha256": "c" * 64}
        lock = {"schema": "szl.vertical-shell.source-lock/v1", "generator": header["generator"],
                "source_repository": "szl-holdings/szl-vertical-forge",
                "source_revision": "67a3cf2d6281035af237a6f97486069a345d496b",
                "artifact_sha256": page_hash, "fleet_master_hash": master}
        self.put(self.publisher, verifier.TERRA_BUNDLE + "index.html", page)
        for name, value in (("fleet-receipt.json", fleet), ("build-receipt.json", artifact),
                            ("source-lock.json", lock)):
            self.put(self.publisher, verifier.TERRA_BUNDLE + name, json.dumps(value))

    def verify(self):
        with patch.object(verifier, "exact_sha", return_value="a" * 40):
            return verifier.verify(self.source, self.governance, self.publisher)

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
        self.assertIn(verifier.PUBLISHER_BASE_IMPLEMENTATION, receipt["publisher_files_sha256"])
        self.assertIn(verifier.PUBLISHER_NATIVE_IMPLEMENTATION, receipt["publisher_files_sha256"])
        self.assertEqual(receipt["forge_verification"]["state"], "STATIC_PASS")
        self.assertEqual(receipt["forge_verification"]["live_runtime_state"], "NOT_CHECKED")
        for name in ("index.html", "build-receipt.json", "fleet-receipt.json", "source-lock.json"):
            self.assertIn(verifier.TERRA_BUNDLE + name, receipt["publisher_files_sha256"])
        for path, digest in verifier.NATIVE_ASSETS_SHA256.items():
            self.assertEqual(receipt["publisher_files_sha256"][path], digest)

    def test_nonisolated_or_wrong_publisher_invocation_fails(self):
        workflow = self.publisher / verifier.PUBLISHER_WORKFLOW
        original = workflow.read_text(encoding="utf-8")
        expected = "python -I -B scripts/hf_publish_vertical_flagships_v4.py"
        for replacement in (
            "python scripts/hf_publish_vertical_flagships_v4.py",
            "python -I scripts/hf_publish_vertical_flagships_v4.py",
            "python -B scripts/hf_publish_vertical_flagships_v4.py",
            "python -I -B scripts/other_publisher.py",
        ):
            with self.subTest(invocation=replacement):
                workflow.write_text(original.replace(expected, replacement), encoding="utf-8")
                with patch.object(verifier, "exact_sha", return_value="a" * 40):
                    with self.assertRaisesRegex(ValueError, "canonical publisher workflow"):
                        verifier.verify(self.source, self.governance, self.publisher)

    def test_overlay_must_keep_proof_controls(self):
        overlay = self.publisher / verifier.PUBLISHER_IMPLEMENTATION
        overlay.write_text(
            overlay.read_text(encoding="utf-8").replace(
                'if fleet.get("master_hash") != _forge_sha256({"chain_tip": previous, "header": header}):',
                "if False:",
            ),
            encoding="utf-8",
        )
        with patch.object(verifier, "exact_sha", return_value="a" * 40):
            with self.assertRaisesRegex(ValueError, "canonical Terra overlay"):
                verifier.verify(self.source, self.governance, self.publisher)

    def test_base_implementation_controls_are_required(self):
        base = self.publisher / verifier.PUBLISHER_BASE_IMPLEMENTATION
        base.write_text(
            base.read_text(encoding="utf-8").replace(
                'DEPLOYMENT_SOURCE_REPOSITORY = "szl-holdings/a11oy"',
                'DEPLOYMENT_SOURCE_REPOSITORY = "other/repo"',
            ),
            encoding="utf-8",
        )
        with patch.object(verifier, "exact_sha", return_value="a" * 40):
            with self.assertRaisesRegex(ValueError, "canonical Terra base implementation"):
                verifier.verify(self.source, self.governance, self.publisher)

    def test_base_publisher_bypass_fails_even_with_required_markers(self):
        base = self.publisher / verifier.PUBLISHER_BASE_IMPLEMENTATION
        base.write_text(base.read_text() + "\nmain = lambda: 0\n")
        with self.assertRaisesRegex(ValueError, "canonical Terra base implementation"):
            self.verify()

    def test_overlay_comments_and_formatting_preserve_reviewed_ast(self):
        overlay = self.publisher / verifier.PUBLISHER_IMPLEMENTATION
        overlay.write_text("# Editorial comment\n\n" + overlay.read_text() + "\n")
        self.assertEqual(self.verify()["forge_verification"]["state"], "STATIC_PASS")

    def test_native_loader_must_be_restored_in_finally(self):
        overlay = self.publisher / verifier.PUBLISHER_IMPLEMENTATION
        text = overlay.read_text()
        for replacement in (
            "_BASE.load_terra_forge_bundle = load_terra_native_landing",
            "_BASE.load_terra_forge_bundle = None",
            "pass",
        ):
            with self.subTest(replacement=replacement):
                overlay.write_text(text.replace(
                    "_BASE.load_terra_forge_bundle = original_terra_loader", replacement,
                ))
                with self.assertRaisesRegex(ValueError, "canonical Terra overlay"):
                    self.verify()

    def test_native_derived_hash_binding_cannot_be_removed(self):
        native = self.publisher / verifier.PUBLISHER_NATIVE_IMPLEMENTATION
        native.write_text(native.read_text().replace(
            'hashlib.sha256(derived.encode()).hexdigest()', '"unverified"',
        ))
        with self.assertRaisesRegex(ValueError, "native renderer"):
            self.verify()

    def test_wrong_publisher_execution_fails(self):
        overlay = self.publisher / verifier.PUBLISHER_IMPLEMENTATION
        overlay.write_text(overlay.read_text().replace("return int(_BASE.main())", "return int(other.main())"))
        with self.assertRaisesRegex(ValueError, "canonical Terra overlay"):
            self.verify()

    def test_forge_landing_tampering_fails(self):
        page = self.publisher / verifier.TERRA_BUNDLE / "index.html"
        page.write_text(page.read_text() + "tampered")
        with self.assertRaisesRegex(ValueError, "artifact hash"):
            self.verify()

    def test_forge_receipt_tampering_fails(self):
        mutations = (
            ("fleet-receipt.json", lambda d: d["events"][0].update(prev_hash="e" * 64)),
            ("fleet-receipt.json", lambda d: d["events"][0].update(chain_hash="e" * 64)),
            ("fleet-receipt.json", lambda d: d.update(master_hash="e" * 64)),
            ("fleet-receipt.json", lambda d: d.update(config_sha256="e" * 64)),
            ("fleet-receipt.json", lambda d: d.update(vertical_count=2)),
            ("fleet-receipt.json", lambda d: d.update(generator="szl-vertical-forge/0.2.2")),
            ("source-lock.json", lambda d: d.update(source_repository="other/repo")),
            ("source-lock.json", lambda d: d.update(source_revision="main")),
            ("source-lock.json", lambda d: d.update(source_revision=int("1" * 40))),
            ("source-lock.json", lambda d: d.update(source_revision="1" * 40)),
            ("source-lock.json", lambda d: d.update(artifact_sha256="e" * 64)),
            ("build-receipt.json", lambda d: d.update(chain_event={})),
            ("build-receipt.json", lambda d: d.update(fleet_config_sha256="e" * 64)),
            ("build-receipt.json", lambda d: d.update(vertical="sentra")),
        )
        for name, mutate in mutations:
            with self.subTest(file=name, mutate=mutate):
                self.make_forge_bundle()
                path = self.publisher / verifier.TERRA_BUNDLE / name
                document = json.loads(path.read_text())
                mutate(document)
                path.write_text(json.dumps(document))
                with self.assertRaisesRegex(ValueError, "Terra forge"):
                    self.verify()

    def test_comment_only_proof_cannot_satisfy_overlay_contract(self):
        overlay = self.publisher / verifier.PUBLISHER_IMPLEMENTATION
        text = overlay.read_text()
        start = text.index("def load_terra_forge_bundle()")
        end = text.index("def load_terra_native_landing()")
        overlay.write_text(text[:start] + "\n".join("# " + line for line in text[start:end].splitlines())
                           + "\n" + text[end:])
        with self.assertRaisesRegex(ValueError, "canonical Terra overlay"):
            self.verify()

    def test_rebound_or_shadowed_proof_functions_fail(self):
        overlay = self.publisher / verifier.PUBLISHER_IMPLEMENTATION
        original = overlay.read_text()
        for shadow in (
            'def load_terra_native_landing():\n    return "unverified", {}',
            '_forge_sha256 = lambda _: "forged"',
            'from other import load_terra_forge_bundle',
            'del load_terra_native_landing',
            'TERRA_FORGE_RECEIPT_SCHEMA = "unverified"',
            '_BASE.load_terra_forge_bundle = lambda: ("unverified", {})',
            '_BASE.main = lambda: 0',
            '_BASE = other',
            'del _BASE',
            'from other import _BASE',
            '_native_module = other',
            'del _native_module',
            'from other import _native_module',
            '_native_module.present = lambda *args, **kwargs: "unreviewed"',
            '_native_module.derive_forge = lambda *args: ("unreviewed", {})',
            '_native_spec.loader = other',
            'setattr(_BASE, "main", lambda: 0)',
            'globals()["_BASE"] = other',

        ):
            with self.subTest(shadow=shadow):
                overlay.write_text(original + "\n" + shadow + "\n")
                with self.assertRaisesRegex(ValueError, "canonical Terra overlay"):
                    self.verify()

    def test_earlier_publisher_bypass_fails(self):
        overlay = self.publisher / verifier.PUBLISHER_IMPLEMENTATION
        overlay.write_text(overlay.read_text().replace(
            'def main() -> int:', 'def main() -> int:\n    return int(other.main())',
        ))
        with self.assertRaisesRegex(ValueError, "canonical Terra overlay"):
            self.verify()

    def test_native_renderer_dependency_changes_fail(self):
        native = self.publisher / verifier.PUBLISHER_NATIVE_IMPLEMENTATION
        original = native.read_text()
        for change in (
            original + '\npresent = lambda page, *args, **kwargs: "unverified"\n',
            original.replace('derived = present(page, "terra", forge=True)', 'derived = page'),
            original + '\nVERSION = "unreviewed"\n',
        ):
            with self.subTest(change=change[-80:]):
                native.write_text(change)
                with self.assertRaisesRegex(ValueError, "native renderer"):
                    self.verify()

    def test_native_renderer_asset_changes_fail(self):
        for path in verifier.NATIVE_ASSETS_SHA256:
            with self.subTest(path=path):
                asset = self.publisher / path
                original = asset.read_bytes()
                asset.write_bytes(original + b"changed")
                with self.assertRaisesRegex(ValueError, "native renderer assets"):
                    self.verify()
                asset.write_bytes(original)

    def test_self_consistent_receipt_with_invalid_configuration_digest_fails(self):
        for value in (None, False, 123, "g" * 64, "a" * 63, "a" * 65):
            with self.subTest(value=value):
                self.make_forge_bundle()
                root = self.publisher / verifier.TERRA_BUNDLE
                fleet = json.loads((root / "fleet-receipt.json").read_text())
                artifact = json.loads((root / "build-receipt.json").read_text())
                lock = json.loads((root / "source-lock.json").read_text())
                fleet["config_sha256"] = value
                header = {key: fleet[key] for key in verifier.FORGE_HEADER_FIELDS}
                master = hashlib.sha256(json.dumps(
                    {"chain_tip": fleet["chain_tip"], "header": header},
                    sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                ).encode()).hexdigest()
                fleet["master_hash"] = master
                artifact.update(fleet_config_sha256=value, fleet_master_hash=master)
                lock["fleet_master_hash"] = master
                for filename, document in (("fleet-receipt.json", fleet),
                                            ("build-receipt.json", artifact), ("source-lock.json", lock)):
                    (root / filename).write_text(json.dumps(document))
                with self.assertRaisesRegex(ValueError, "configuration digest"):
                    self.verify()

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

    def test_duplicate_publisher_environment_review_fails(self):
        workflow = self.publisher / verifier.PUBLISHER_WORKFLOW
        workflow.write_text(
            workflow.read_text(encoding="utf-8")
            + "\n    environment: production\n",
            encoding="utf-8",
        )
        with patch.object(verifier, "exact_sha", return_value="a" * 40):
            with self.assertRaisesRegex(ValueError, "duplicate environment review"):
                verifier.verify(self.source, self.governance, self.publisher)

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
