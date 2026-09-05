"""Verify Terra's source/governance/presentation relation without provider writes.

This is a static, commit-addressed contract check. A separate live deployment
receipt is needed to establish which presentation bytes a provider is serving.
Keep GitHub expression literals in this file, never in a workflow run block.
"""
from __future__ import annotations

import argparse
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


def verify(source: Path, governance: Path, publisher: Path) -> dict:
    source_sha, governance_sha, publisher_sha = map(
        exact_sha, (source, governance, publisher)
    )
    workflows = scan_source_workflows(source)
    governance_data = (governance / GOVERNANCE_CONTRACT).read_bytes()
    validate_governance(json.loads(governance_data))
    publisher_files = {
        path: (publisher / path).read_bytes()
        for path in (PUBLISHER_WORKFLOW, PUBLISHER_ENTRYPOINT, PUBLISHER_IMPLEMENTATION)
    }
    workflow_text = publisher_files[PUBLISHER_WORKFLOW].decode("utf-8")
    require_fragments(workflow_text, (
        "push:", "branches: [main]", "publish-vertical-flagships:",
        "scripts/hf_exact_main_ownership.py",
        "python scripts/hf_publish_vertical_flagships_v4.py",
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
    require_fragments(publisher_files[PUBLISHER_IMPLEMENTATION].decode("utf-8"), (
        'DEPLOYMENT_SOURCE_REPOSITORY = "szl-holdings/a11oy"',
        '"slug": "terra"', f'"source": "{PRODUCT_URL}"', "TERRA_FORGE_MARKER",
        "load_terra_forge_bundle()", '"schema":"szl.build-info/v1"',
        '"schema":"szl.vertical-shell-deployment/v1"', '"hf_repository": rid',
    ), "canonical Terra implementation")
    receipt = {
        "schema": "szl.hf.canonical-surface-delegation.v3",
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
