# Leaders Study - szl-real-estate (Terra vertical, docs-only)

Lap: OUROBOROS spaces batch-2 census continue, target **szl-real-estate** (canonical product source for the Terra space; public-records underwriting). This document positions the repository against the four domain leaders scanned and web-verified 2026-11-24. Nothing here is approved, implemented, or claimed: every absorb item is an **unapproved study candidate** and every open item is an **open question**. This lap adds documentation only.

## What this repository is

- Public-records underwriting, not an MLS. Zillow / CoStar / HouseCanary own listings; this estate owns the public-records posture.
- NYC PLUTO is MEASURED only after one exact BBL and tract match, validated numeric records, and a retained source hash; tract samples never become parcel facts.
- Honest UNAVAILABLE states: Nassau has no PLUTO, unit occupancy is UNAVAILABLE, energy is UNAVAILABLE; unknown or missing IDs return an unresolved receipt and HTTP 404 without substituting an example.
- The three selectable parcels are MODELED fixtures without validated real BBLs.
- Formula authority is NONE: models, formulas and market signals never authorize. Not a Zestimate. Actuation (offer, listing, close) is ROADMAP. STRUCTURAL-ONLY receipts.

## Leaders studied (web-verified 2026-11-24)

1. **Zillow Zestimate (disclosure posture)** - publishes nationwide median error rates refreshed quarterly (roughly 2 percent on-market, roughly 7 percent off-market across 2026 refreshes), per-market accuracy tables, and explicit not-an-appraisal framing. Leader pattern: measured error transparency as a trust surface.
2. **HouseCanary (institutional AVM)** - median absolute prediction error 2.5 percent purchase / 6.8 percent prelist on its six-month benchmark ending 2026-08-18 (136M+ properties, census-block granularity), per-property confidence scores and prediction intervals, monthly internal plus quarterly independent third-party validation, and a public FHFA-standards compliance memo citing the interagency AVM quality-control final rule effective 2025-10-01.
3. **FHFA House Price Index (transparent methodology)** - fully transparent weighted repeat-sales methodology, 100M+ transactions back to 1975, geography down to census tract (63,122 tract-level repeat-sales indices in the 2021 working paper), with published revision behavior as new repeat pairs arrive.
4. **FEMA National Risk Index (risk-layer methodology)** - Expected Annual Loss = exposure x annualized frequency x historic loss ratio for 18 hazards at census-tract and county level, social-vulnerability and community-resilience layers, an explicit disclaimer that it is a baseline measurement and not absolute risk, public-domain data.

## Gap analysis

This repository refuses to be a valuation product: formula authority NONE, not-a-Zestimate, MLS fail-closed, MEASURED only with retained source hashes and honest UNAVAILABLE nulls. It currently lacks, versus the leaders: a written uncertainty and accuracy-disclosure policy (the leaders publish measured error posture); any per-parcel confidence or interval language (as clearly labeled derived, never MEASURED); a documented independent-validation-loop posture; and a written tract-layer methodology and revision policy for the ACS RATE and FEMA inputs. Conversely, none of the four leaders publish per-parcel source-hash receipts, so the estate moat stands.

## Absorb candidates (UNAPPROVED - study candidates only, nothing approved or implemented)

- **A1 Uncertainty and accuracy-disclosure policy study.** A written policy stating what is MEASURED, what is UNAVAILABLE, and that no accuracy or error-rate claim may be made without a measured benchmark. Study doc first; no schema change.
- **A2 Derived-confidence language study.** Whether a per-parcel confidence or interval label, HouseCanary-style but clearly labeled derived, could ever be produced without violating the never-re-label-as-MEASURED rule.
- **A3 Independent-validation-loop posture study.** What an independent validation loop could honestly validate today given the MODELED fixture parcels; what evidence a real validation lap would require first.
- **A4 Tract-layer methodology and revision policy study.** A written methodology and revision-policy doc for the tract ACS RATE and FEMA inputs, FHFA-transparency-style: which layers, which granularity, revision behavior.

## Open questions (OPEN - unresolved, not adopted)

- **A5 AVM rule alignment posture.** Does the interagency AVM quality-control final rule (effective 2025-10-01) create any alignment or disclosure posture for a product that explicitly refuses valuations? Unstudied; no compliance claim is made.
- **A6 Actuation evidence chain.** Any future actuation phase (offer, listing, close) would need its own measured evidence chain; what it must contain is undetermined. No actuation is proposed here.

## Non-goals

- No valuation, appraisal, accuracy, error-rate, or compliance claim anywhere in this study.
- No modification of the underwriting code, receipts, CI, workflows, or release gates in this lap.
- No MLS, listing, lockbox, or actuation work; formula authority stays NONE.
