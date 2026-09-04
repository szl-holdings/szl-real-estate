---
title: SZL Real Estate
emoji: 🧠
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Public-records underwriting. Not an MLS.
---

# szl-real-estate


## Packet 8 source pin

Terra Assurance product logic lives in canonical [`szl-holdings/a11oy/verticals/terra`](https://github.com/szl-holdings/a11oy/tree/main/verticals/terra).

- Kernel: [`verticals/_kernel/a11oy_kernel.py`](https://github.com/szl-holdings/a11oy/blob/main/verticals/_kernel/a11oy_kernel.py)
- Canonical Hugging Face surface: [SZLHOLDINGS/terra](https://huggingface.co/spaces/SZLHOLDINGS/terra)
- This repo is the canonical product source. The protected A11oy publisher owns
  the presentation runtime and links it back here; source bytes and deployed
  runtime bytes are deliberately reported as separate identities.
- Formula authority: **NONE**. Models, formulas and market signals never authorize.
- Canonical land PR: [szl-holdings/a11oy#1438](https://github.com/szl-holdings/a11oy/pull/1438)
- Canonical land SHA: [`2b67b63624a3f4bf35787cfa5260d7960f1a76d5`](https://github.com/szl-holdings/a11oy/commit/2b67b63624a3f4bf35787cfa5260d7960f1a76d5)


The fifth vertical. Zillow / CoStar / HouseCanary own listings. SZL owns public assessor + FEMA letter + tract ACS RATE.

- NYC PLUTO is MEASURED when the open data API answers.
- Nassau has no PLUTO — honesty stays UNAVAILABLE, never invented.
- Unit occupancy is UNAVAILABLE.
- MLS / lockbox / "list the house" fail closed.
- Actuation (offer, listing, close) is ROADMAP.
- Energy UNAVAILABLE. Λ = Conjecture 1. STRUCTURAL-ONLY receipts.
- The local `hf-space` workflow performs no provider write. It verifies the
  organization estate contract, the current protected A11oy publisher, and the
  single canonical `SZLHOLDINGS/terra` target, then emits a hash-addressed
  delegation receipt. Runtime state still requires a separate live deployment
  receipt and provider readback.

Not affiliated with Zillow, CoStar, or HouseCanary. Not a Zestimate.

Canonical GitHub: [szl-holdings/szl-real-estate](https://github.com/szl-holdings/szl-real-estate).
Operator kernel: [szl-holdings/szl-sovereign-os](https://github.com/szl-holdings/szl-sovereign-os).
