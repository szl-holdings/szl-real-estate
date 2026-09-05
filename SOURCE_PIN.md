# Terra source and presentation ownership

| Field | Authority |
| --- | --- |
| Product source | `szl-holdings/szl-real-estate` |
| Assurance core | `szl-holdings/a11oy:verticals/terra` |
| Kernel | `szl-holdings/a11oy:verticals/_kernel/a11oy_kernel.py` |
| Presentation implementation | `szl-holdings/a11oy:scripts/hf_publish_vertical_flagships_v4_impl.py` |
| Canonical provider writer | `szl-holdings/a11oy:.github/workflows/hf-sync.yml` |
| Canonical public Space | [SZLHOLDINGS/terra](https://huggingface.co/spaces/SZLHOLDINGS/terra) |
| Estate contract | `szl-holdings/.github:estate/alignment.v1.json` |
| Product deployment relation | `LINKED_NOT_PUBLISHED` |
| Formula authority | NONE |
| Lambda | Conjecture 1 / ADVISORY_CONJECTURAL |

The A11oy publisher builds Terra's presentation and links it to this product
source. That link does not establish that the product source's Python or HTML
bytes are deployed. This repository has no provider publishing workflow.

The delegation workflow records the exact source, governance, and publisher
commits in `hf-canonical-terra-delegation.json`. This file describes ownership;
it does not replace those per-run commit pins. A live `/build-receipt.json` and
Hugging Face provider readback establish the served presentation revision.

The former `terra-assurance` target and Packet 8 commit are historical context,
not the current canonical target or runtime receipt. Visibility and runtime
status must be read from the provider rather than inferred from this document.

This adapter does not provide an MLS, certified valuation, offer, listing, or
close engine. Consequential actions require separate authority and evidence.
