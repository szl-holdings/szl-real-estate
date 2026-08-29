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
- Hugging Face Space (private, ROADMAP): `SZLHOLDINGS/terra-assurance`
- This repo is a generated thin adapter. See [`SOURCE_PIN.md`](SOURCE_PIN.md).
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
- Hugging Face live push from this sandbox is ROADMAP until `HF_TOKEN` is in org secrets. This README does not claim the Space is RUNNING until Hub readback says so.

Not affiliated with Zillow, CoStar, or HouseCanary. Not a Zestimate.

Canonical GitHub: [szl-holdings/szl-real-estate](https://github.com/szl-holdings/szl-real-estate).
Operator kernel: [szl-holdings/szl-sovereign-os](https://github.com/szl-holdings/szl-sovereign-os).
