# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Public-records underwriting. Not an MLS. Occupancy UNAVAILABLE.

Zillow / CoStar / HouseCanary own listings. SZL owns assessor + FEMA letter
+ tract ACS RATE. Unit occupancy is never invented. Nassau has no PLUTO.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Mapping

KERNEL_COMMIT = "c7c0ba17"
ZERO = "0" * 64
proven_trust = False

PARCELS: tuple[dict[str, Any], ...] = (
    {
        "id": "R-BK-11",
        "county": "Kings",
        "tract": "36047001100",
        "fema": "X",
        "assessor": "C4",
        "occupancy": "UNAVAILABLE",
        "honesty": "MODELED",
    },
    {
        "id": "R-QN-19",
        "county": "Queens",
        "tract": "36081088300",
        "fema": "VE",
        "assessor": "C1",
        "occupancy": "UNAVAILABLE",
        "honesty": "MODELED",
    },
    {
        "id": "R-NS-04",
        "county": "Nassau",
        "tract": "36059302200",
        "fema": "AE",
        "assessor": "A2",
        "occupancy": "UNAVAILABLE",
        "honesty": "MODELED",
    },
)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def envelope(ev: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.dumps(ev, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "ok": True,
        "surface": "szl-real-estate",
        "receipt_sha256": sha256_hex(payload),
        "signing": "STRUCTURAL-ONLY — no key on this surface; tamper-EVIDENT hash, not a signature",
        "body": dict(ev),
    }


def _borough(geoid: str) -> str | None:
    county = geoid[2:5]
    return {"047": "3", "081": "4", "061": "1", "005": "2", "085": "5"}.get(county)


def _tract_aliases(geoid: str) -> list[str]:
    six = geoid[5:]
    n = int(six) if six.isdigit() else 0
    major = n // 100
    minor = n % 100
    dotted = f"{major}.{minor:02d}" if minor else str(major)
    return [str(major), dotted, six, six.lstrip("0") or "0"]


def _empty_pluto(geoid: str, parcel_id: str, note: str) -> dict[str, Any]:
    return {
        "tract": geoid,
        "parcelId": parcel_id,
        "address": None,
        "bbl": None,
        "assessTot": None,
        "unitsRes": None,
        "yearBuilt": None,
        "honesty": "UNAVAILABLE",
        "note": note,
    }


def fetch_pluto(geoid: str, parcel_id: str) -> dict[str, Any]:
    boro = _borough(geoid)
    if not boro:
        return _empty_pluto(
            geoid,
            parcel_id,
            "Not a NYC county. PLUTO does not cover Nassau. Assessor MEASURED feed UNAVAILABLE. Occupancy UNAVAILABLE.",
        )
    aliases = ",".join(f"'{a}'" for a in _tract_aliases(geoid))
    where = f"borocode='{boro}' AND ct2010 in ({aliases}) AND unitsres > 0 AND assesstot > 0"
    query = urllib.parse.urlencode(
        {
            "$select": "address,bbl,assesstot,unitsres,yearbuilt,ct2010,borocode",
            "$where": where,
            "$order": "assesstot DESC",
            "$limit": "1",
        }
    )
    url = f"https://data.cityofnewyork.us/resource/64uk-42ks.json?{query}"
    try:
        req = urllib.request.Request(url, headers={"accept": "application/json", "user-agent": "szl-real-estate/0.1"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            rows = json.loads(resp.read().decode("utf-8") or "[]")
    except Exception as exc:  # system boundary: public API — fail closed, never invent assessment
        return _empty_pluto(
            geoid,
            parcel_id,
            f"NYC PLUTO unreachable ({type(exc).__name__}). Assessment UNAVAILABLE. Occupancy UNAVAILABLE.",
        )
    row = rows[0] if isinstance(rows, list) and rows else None
    if not row:
        return _empty_pluto(geoid, parcel_id, "No PLUTO residential lot with assessment in this tract. Occupancy UNAVAILABLE.")
    assess = float(row.get("assesstot") or 0)
    units = float(row.get("unitsres") or 0)
    return {
        "tract": geoid,
        "parcelId": parcel_id,
        "address": row.get("address"),
        "bbl": str(int(float(row["bbl"]))) if row.get("bbl") else None,
        "assessTot": assess if assess == assess else None,
        "unitsRes": int(units) if units == units else None,
        "yearBuilt": int(float(row["yearbuilt"])) if row.get("yearbuilt") else None,
        "honesty": "MEASURED",
        "note": "NYC PLUTO assessed total and residential units are MEASURED public records. Unit occupancy stays UNAVAILABLE. Not an MLS.",
    }


def _willay(signal: str) -> bool:
    return bool(re.search(r"ignore (the )?policy|bypass (the )?gate|disable willay|override lambda|jailbreak", signal, re.I))


def run_parcel(parcel_id: str, signal: str) -> dict[str, Any]:
    if proven_trust is True:
        raise RuntimeError("refusing proven_trust true")
    meta = next((p for p in PARCELS if p["id"] == parcel_id), PARCELS[0])
    mls = bool(re.search(r"\bmls\b|lockbox|showing|list the house", signal, re.I))
    fire = _willay(signal)
    pluto = fetch_pluto(str(meta["tract"]), str(meta["id"]))
    if fire:
        decision, output, actuation = "BLOCKED", "WILLAY conscience veto — governance bypass refused", "NONE"
    elif mls:
        decision, output, actuation = "BLOCKED", "MLS/lockbox refused — no listing, no close", "NONE"
    else:
        decision, output, actuation = (
            "ADVISORY",
            "public PLUTO/ACS underwriting · unit occupancy UNAVAILABLE · not an MLS",
            "ROADMAP",
        )
    body = {
        "vertical": "real-estate",
        "id": meta["id"],
        "county": meta["county"],
        "tract": meta["tract"],
        "fema_letter": meta["fema"],
        "fema_honesty": "MODELED",
        "assessor": meta["assessor"],
        "signal": signal,
        "decision": decision,
        "output": output,
        "actuation": actuation,
        "occupancy": "UNAVAILABLE",
        "occupancy_j": None,
        "pluto": pluto,
        "acs": {
            "honesty": "UNAVAILABLE",
            "occupancyRate": None,
            "note": "Census ACS requires a bureau key from this runtime. Tract occupancy RATE UNAVAILABLE. Unit occupancy remains UNAVAILABLE.",
        },
        "energy": "UNAVAILABLE",
        "energy_j": None,
        "proven_trust": False,
        "kernel_commit": KERNEL_COMMIT,
        "leader_cited": "Zillow / CoStar / HouseCanary",
        "not_a_rehost": True,
        "affiliation": "none",
        "they_own": "listings, Zestimate, comps network",
        "we_own": "assessor + FEMA + tract ACS RATE, receipted, no fabricated occupancy",
        "payload_sha256": sha256_hex(f"{meta['id']}|{signal}"),
        "checked_at": now(),
    }
    return envelope(body)
