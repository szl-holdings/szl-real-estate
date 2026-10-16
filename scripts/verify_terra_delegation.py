"""Verify Terra's source/governance/presentation relation without provider writes.

This is a static, commit-addressed contract check. A separate live deployment
receipt is needed to establish which presentation bytes a provider is serving.
Keep GitHub expression literals in this file, never in a workflow run block.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

PRODUCT_REPO = "szl-holdings/szl-real-estate"
PRODUCT_URL = "https://github.com/" + PRODUCT_REPO
PUBLISHER_REPO = "szl-holdings/a11oy"
HF_REPO = "SZLHOLDINGS/terra"
GOVERNANCE_CONTRACT = "estate/alignment.v1.json"
PUBLISHER_WORKFLOW = ".github/workflows/hf-sync.yml"
PUBLISHER_ENTRYPOINT = "scripts/hf_publish_vertical_flagships_v4.py"
PUBLISHER_IMPLEMENTATION = "scripts/hf_publish_vertical_flagships_v4_impl.py"
PUBLISHER_BASE_IMPLEMENTATION = "scripts/_hf_publish_vertical_flagships_v4_impl_base.py"
PUBLISHER_NATIVE_IMPLEMENTATION = "scripts/hf_vertical_native_presentation.py"
TERRA_BUNDLE = "deployments/vertical-forge/terra/"
FORGE_GENERATOR = "szl-vertical-forge/0.2.3"
FORGE_HEADER_FIELDS = (
    "schema", "generator", "algorithm", "genesis", "config_sha256", "vertical_count",
)
# Reviewed contract migrations: a11oy#2787 (forge v4) and #2819 (native landing).
# Pin the proof functions and their execution/contract adapters.
# A semantic change to either requires review; comments/formatting do not.
PROOF_FUNCTIONS = {
    "load_terra_forge_bundle": "6cdda7f523df496f8c14e684450901f0f51c99bd9e52eaa9e6c9003d9789e167",
    "derive_forge": "45be7be008b39b8c9dd082ea533d2a26b27be009472fec2c72f67ff682b12921",
    "_sync_contract": "2d8a7c9ed43ca9537e4f879319fdd9441bdce16cdc6a784642c5d8a901bf5c1f",
    "_forge_sha256": "5747a18ae61aca1070ec7661108dff28c58eb667d467ddecc56f9a237b897580",
    "load_terra_native_landing": "371f6081a918af42e02b5d834ba812299649f90f183b3bd508b295f7cc9b1af9",
    "main": "5697ab3e294fed427343195c267b68e76a8e47e797e9198aa2f74263cbe49112",
}
PRESENTATION_SOURCE = PUBLISHER_REPO + ":" + PUBLISHER_IMPLEMENTATION


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_sha(checkout: Path) -> str:
    value = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "--verify", "HEAD"], text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("checkout identity is not an exact commit SHA")
    # A commit cannot identify modified or untracked files used for the proof.
    if subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=all"],
        text=True,
    ).strip():
        raise ValueError("delegation checkout has uncommitted files")
    return value


def scan_source_workflows(source: Path) -> dict[str, str]:
    directory = source / ".github/workflows"
    workflows = sorted(
        p for p in directory.rglob("*") if p.suffix.lower() in {".yml", ".yaml"}
    )
    if not workflows:
        raise ValueError("source workflow inventory is empty")
    patterns = {
        "secret reference": re.compile(r"\bsecrets\s*(?:\.|\[)", re.I),
        "inherited secrets": re.compile(r"\bsecrets\s*:\s*inherit\b", re.I),
        "reusable provider writer": re.compile(r"reusable-hf-deploy\.ya?ml", re.I),
        "provider upload command": re.compile(
            r"\b(?:hf|huggingface-cli)\s+(?:upload|upload-large-folder|repo\s+(?:create|delete))\b",
            re.I,
        ),
        "provider write API": re.compile(
            r"\b(?:upload_file|upload_folder|create_commit|create_repo|delete_repo)\s*\(",
            re.I,
        ),
    }
    inventory = {}
    for workflow in workflows:
        if workflow.is_symlink() or not workflow.is_file():
            raise ValueError("source workflow must be a regular file")
        data = workflow.read_bytes()
        text = data.decode("utf-8")
        present = [name for name, pattern in patterns.items() if pattern.search(text)]
        if present:
            # Never include matching text, because it could contain credentials.
            raise ValueError(
                f"source workflow {workflow.relative_to(source).as_posix()} "
                f"violates presentation delegation: {', '.join(present)}"
            )
        inventory[workflow.relative_to(source).as_posix()] = digest(data)
    return inventory


def validate_governance(governance: dict) -> None:
    if governance.get("schema") != "szl.estate.alignment/v1":
        raise ValueError("unexpected estate governance schema")
    bodies = [
        body for body in governance.get("public_bodies", [])
        if isinstance(body, dict) and body.get("id") == "terra"
    ]
    if len(bodies) != 1:
        raise ValueError("expected one governed Terra body")
    expected = {
        "backend_source": PRODUCT_REPO,
        "presentation_source": PRESENTATION_SOURCE,
        "publisher_workflow": PUBLISHER_REPO + ":" + PUBLISHER_WORKFLOW,
        "product_source_deployment_state": "LINKED_NOT_PUBLISHED",
        "hub_surface": HF_REPO,
        "domain": "real-estate",
    }
    mismatched = [key for key, value in expected.items() if bodies[0].get(key) != value]
    if mismatched:
        raise ValueError("Terra estate contract drifted: " + ", ".join(mismatched))
    if governance.get("authority", {}).get("governed_fabric") != PUBLISHER_REPO:
        raise ValueError("A11oy is not the governed publication fabric")
    aliases = governance.get("hub_alias_policy", {})
    if aliases.get("duplicate_authority_spaces_forbidden") is not True:
        raise ValueError("duplicate Hub authority is not forbidden")
    if "terra" not in aliases.get("canonical_public_space_slugs", []):
        raise ValueError("Terra is absent from canonical Hub slugs")


def require_fragments(text: str, fragments: tuple[str, ...], label: str) -> None:
    if any(fragment not in text for fragment in fragments):
        # Fragment values are not printed, even for expected secret expressions.
        raise ValueError(label + " is missing required delegation controls")


def verify_overlay_contract(overlay: str, native: str) -> None:
    """Inspect reviewed proof code without importing or executing a publisher."""
    tree = ast.parse(overlay)
    for name in PROOF_FUNCTIONS:
        module = ast.parse(native if name == "derive_forge" else overlay)
        functions = [node for node in module.body
                     if isinstance(node, ast.FunctionDef) and node.name == name]
        bindings = [node for node in ast.walk(module) if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name
            or isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del))
            or isinstance(node, ast.alias) and (node.asname or node.name.split(".")[0]) == name
        )]
        if len(functions) != 1 or len(bindings) != 1:
            raise ValueError("canonical Terra overlay has ambiguous proof functions")
        function = functions[0]
        if (function.body and isinstance(function.body[0], ast.Expr)
                and isinstance(function.body[0].value, ast.Constant)
                and isinstance(function.body[0].value.value, str)):
            function.body.pop(0)
        if digest(ast.unparse(function).encode("utf-8")) != PROOF_FUNCTIONS[name]:
            raise ValueError("canonical Terra overlay proof controls changed")
    statements = {ast.unparse(node) for node in tree.body}
    required = (
        'TERRA_FORGE_GENERATOR = "szl-vertical-forge/0.2.3"',
        'TERRA_FORGE_RECEIPT_SCHEMA = "szl.vertical-forge.receipt/v4"',
        'TERRA_FORGE_RECEIPT_ALGORITHM = "sha256-canonical-json-chain"',
        "TERRA_FORGE_RECEIPT_HEADER_FIELDS = " + repr(FORGE_HEADER_FIELDS),
        "_BASE.load_terra_forge_bundle = load_terra_forge_bundle",
        "def _forge_sha256(value: Any) -> str:\n    return hashlib.sha256(canonical_json(value)).hexdigest()",
        "def load_terra_native_landing() -> tuple[str, dict[str, Any]]:\n    return _native_module.derive_forge(*load_terra_forge_bundle())",
    )
    if any(ast.unparse(ast.parse(item).body[0]) not in statements for item in required):
        raise ValueError("canonical Terra overlay is missing required delegation controls")
    for name in ("TERRA_FORGE_GENERATOR", "TERRA_FORGE_RECEIPT_SCHEMA",
                 "TERRA_FORGE_RECEIPT_ALGORITHM", "TERRA_FORGE_RECEIPT_HEADER_FIELDS"):
        if sum(isinstance(node, ast.Name) and node.id == name
               and isinstance(node.ctx, (ast.Store, ast.Del)) for node in ast.walk(tree)) != 1:
            raise ValueError("canonical Terra overlay has ambiguous proof constants")
    top_level_loader_writes = [node for statement in tree.body
                              if not isinstance(statement, ast.FunctionDef)
                              for node in ast.walk(statement)
                              if isinstance(node, ast.Attribute)
                              and isinstance(node.ctx, (ast.Store, ast.Del))
                              and ast.unparse(node) == "_BASE.load_terra_forge_bundle"]
    if len(top_level_loader_writes) != 1 or any(
        isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del))
        and ast.unparse(node) == "_BASE.main" for node in ast.walk(tree)
    ):
        raise ValueError("canonical Terra overlay rebinds the canonical publisher")


def verify_forge_bundle(files: dict[str, bytes]) -> dict:
    """Independently bind the checked-in landing, v4 chain, header and source lock."""
    def object_at(name):
        value = json.loads(files[TERRA_BUNDLE + name])
        if not isinstance(value, dict):
            raise ValueError("Terra forge receipt must be a JSON object")
        return value

    def canonical_hash(value):
        return digest(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False).encode("utf-8"))

    page = files[TERRA_BUNDLE + "index.html"]
    fleet, artifact, lock = (object_at(name) for name in
                             ("fleet-receipt.json", "build-receipt.json", "source-lock.json"))
    expected_schemas = ("szl.vertical-forge.receipt/v4", "szl.vertical-forge.artifact/v1",
                        "szl.vertical-shell.source-lock/v1")
    for document, schema in zip((fleet, artifact, lock), expected_schemas):
        if document.get("schema") != schema or document.get("generator") != FORGE_GENERATOR:
            raise ValueError("Terra forge schema or generator mismatch")
    if (lock.get("source_repository") != "szl-holdings/szl-vertical-forge"
            or not isinstance(lock.get("source_revision"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", lock["source_revision"])
            or lock["source_revision"] == "0" * 40):
        raise ValueError("Terra forge source identity mismatch")
    if fleet.get("genesis") != "0" * 64 or fleet.get("algorithm") != "sha256-canonical-json-chain":
        raise ValueError("Terra forge chain header mismatch")
    events = fleet.get("events")
    if (not isinstance(events, list) or not events
            or type(fleet.get("vertical_count")) is not int
            or len(events) != fleet["vertical_count"]):
        raise ValueError("Terra forge event count mismatch")
    previous, terra_events = fleet["genesis"], []
    for event in events:
        if not isinstance(event, dict) or event.get("prev_hash") != previous:
            raise ValueError("Terra forge chain link mismatch")
        calculated = canonical_hash({k: v for k, v in event.items() if k != "chain_hash"})
        if event.get("chain_hash") != calculated:
            raise ValueError("Terra forge event hash mismatch")
        previous = calculated
        if event.get("path") == "terra/index.html":
            terra_events.append(event)
    master = canonical_hash({"chain_tip": previous,
                             "header": {k: fleet.get(k) for k in FORGE_HEADER_FIELDS}})
    if fleet.get("chain_tip") != previous or fleet.get("master_hash") != master:
        raise ValueError("Terra forge master hash mismatch")
    if len(terra_events) != 1 or artifact.get("chain_event") != terra_events[0]:
        raise ValueError("Terra forge artifact is not uniquely bound into the chain")
    page_hash = digest(page)
    if (terra_events[0].get("artifact_sha256") != page_hash
            or lock.get("artifact_sha256") != page_hash
            or lock.get("fleet_master_hash") != master
            or artifact.get("fleet_master_hash") != master
            or artifact.get("fleet_config_sha256") != fleet.get("config_sha256")
            or artifact.get("vertical") != "terra"):
        raise ValueError("Terra forge artifact hash or source-lock mismatch")
    if any(fragment not in page for fragment in (
        b'data-szl-vertical-forge="0.2.2"', b'href="/panels"',
        b'href="/build-receipt.json"', b'const EP="/api/live"',
    )):
        raise ValueError("Terra forge landing lacks required runtime wiring")
    return {"state": "STATIC_PASS", "generator": FORGE_GENERATOR,
            "source_repository": lock["source_repository"],
            "source_revision": lock["source_revision"], "artifact_sha256": page_hash,
            "fleet_master_hash": master, "live_runtime_state": "NOT_CHECKED"}


def verify(source: Path, governance: Path, publisher: Path) -> dict:
    source_sha, governance_sha, publisher_sha = map(
        exact_sha, (source, governance, publisher)
    )
    workflows = scan_source_workflows(source)
    governance_data = (governance / GOVERNANCE_CONTRACT).read_bytes()
    validate_governance(json.loads(governance_data))
    publisher_files = {
        path: (publisher / path).read_bytes()
        for path in (
            PUBLISHER_WORKFLOW,
            PUBLISHER_ENTRYPOINT,
            PUBLISHER_IMPLEMENTATION,
            PUBLISHER_BASE_IMPLEMENTATION,
            PUBLISHER_NATIVE_IMPLEMENTATION,
            *(TERRA_BUNDLE + name for name in (
                "index.html", "build-receipt.json", "fleet-receipt.json", "source-lock.json",
            )),
        )
    }
    workflow_text = publisher_files[PUBLISHER_WORKFLOW].decode("utf-8")
    require_fragments(workflow_text, (
        "push:", "branches: [main]", "publish-vertical-flagships:",
        "scripts/hf_exact_main_ownership.py",
        "python -I -B scripts/hf_publish_vertical_flagships_v4.py",
        "hf-vertical-flagships-receipt.json",
        "HF_ORG_TOKEN: ${{ secrets.HF_ORG_TOKEN }}",
        "HF_WRITE_TOKEN: ${{ secrets.HF_WRITE_TOKEN }}",
        "HF_TOKEN: ${{ secrets.HF_TOKEN }}",
    ), "canonical publisher workflow")
    # Preserve the pre-refactor negative control as well as the required
    # positive controls. A second production-environment review can stall the
    # canonical publisher even when all of its required steps are present.
    if "environment: production" in workflow_text:
        raise ValueError("canonical publisher has a duplicate environment review")
    require_fragments(publisher_files[PUBLISHER_ENTRYPOINT].decode("utf-8"), (
        "hf_publish_vertical_flagships_v4_impl",
    ), "publisher entrypoint")

    # The current A11oy publisher is a narrow policy overlay over an immutable
    # renderer base. Prove that the public entry implementation still binds the
    # exact base and preserves Terra identity. The reviewed 0.2.3 migration
    # verifies forge v4 receipts in the overlay; publication still uses the base.
    require_fragments(publisher_files[PUBLISHER_IMPLEMENTATION].decode("utf-8"), (
        '"_hf_publish_vertical_flagships_v4_impl_base.py"',
        'if getattr(_BASE, "TERRA_FORGE_MARKER", None) !=',
        'if getattr(_BASE, "TERRA_FORGE_GENERATOR", None) != "szl-vertical-forge/0.2.2"',
        '_sentra if row.get("slug") == "sentra" else row for row in _rows',
        "return int(_BASE.main())",
    ), "canonical Terra overlay")
    verify_overlay_contract(
        publisher_files[PUBLISHER_IMPLEMENTATION].decode("utf-8"),
        publisher_files[PUBLISHER_NATIVE_IMPLEMENTATION].decode("utf-8"),
    )
    forge_verification = verify_forge_bundle(publisher_files)

    # The deployment and Terra source controls now live in the immutable base.
    # Bind that file into the receipt instead of pretending they are present in
    # the overlay itself.
    require_fragments(publisher_files[PUBLISHER_BASE_IMPLEMENTATION].decode("utf-8"), (
        'DEPLOYMENT_SOURCE_REPOSITORY = "szl-holdings/a11oy"',
        '"slug": "terra"', f'"source": "{PRODUCT_URL}"', "TERRA_FORGE_MARKER",
        "def load_terra_forge_bundle()", '"schema":"szl.build-info/v1"',
        '"schema":"szl.vertical-shell-deployment/v1"', '"hf_repository": rid',
    ), "canonical Terra base implementation")

    receipt = {
        "schema": "szl.hf.canonical-surface-delegation.v4",
        "state": "DELEGATED_PRESENTATION",
        "product_source_repository": PRODUCT_REPO,
        "product_source_sha": source_sha,
        "product_source_url": PRODUCT_URL,
        "governance_repository": "szl-holdings/.github",
        "governance_sha": governance_sha,
        "governance_contract": GOVERNANCE_CONTRACT,
        "governance_contract_sha256": digest(governance_data),
        "publisher_repository": PUBLISHER_REPO,
        "publisher_sha": publisher_sha,
        "presentation_source": PRESENTATION_SOURCE,
        "publisher_files_sha256": {
            path: digest(data) for path, data in publisher_files.items()
        },
        "forge_verification": forge_verification,
        "source_workflow_scan": {
            "state": "STATIC_PASS",
            "scope": "all source .github/workflows YAML files",
            "files_sha256": workflows,
            "secret_references_present": False,
            "limit": "Static patterns do not prove arbitrary called code cannot write.",
        },
        "hf_repository": HF_REPO,
        "product_source_bytes_published_by_owner": False,
        "duplicate_authority_space_forbidden": True,
        "exact_publisher_main_guard_required": True,
        "live_deployment_receipt_required": True,
        "live_runtime_state": "NOT_CHECKED",
    }
    receipt["receipt_sha256"] = digest(json.dumps(
        receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8"))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "governance", "publisher", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.source, args.governance, args.publisher)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
