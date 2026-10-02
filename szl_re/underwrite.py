# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Public-records underwriting. Not an MLS. Occupancy UNAVAILABLE.

Zillow / CoStar / HouseCanary own listings. SZL owns assessor + FEMA letter
+ tract ACS RATE. Unit occupancy is never invented. Nassau has no PLUTO.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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


def fetch_pluto(geoid: str, parcel_id: str, *, bbl: str | None = None) -> dict[str, Any]:
    """Read one exact NYC BBL; a tract or a modeled fixture is not a parcel join."""
    if not isinstance(geoid, str) or not re.fullmatch(r"36\d{9}", geoid):
        return _empty_pluto(geoid, parcel_id, "Invalid NY tract identifier. Parcel evidence UNAVAILABLE.")
    boro = _borough(geoid)
    if not boro:
        return _empty_pluto(
            geoid,
            parcel_id,
            "Not a NYC county. PLUTO does not cover Nassau. Assessor MEASURED feed UNAVAILABLE. Occupancy UNAVAILABLE.",
        )
    if not isinstance(bbl, str) or not re.fullmatch(r"[1-5]\d{9}", bbl) or bbl[0] != boro:
        return _empty_pluto(
            geoid, parcel_id,
            "No validated exact NYC BBL for this parcel. MODELED examples do not identify a real tax lot. Assessment UNAVAILABLE.",
        )
    query = urllib.parse.urlencode(
        {
            "$select": "address,bbl,assesstot,unitsres,yearbuilt,ct2010,borocode",
            "$where": f"bbl='{bbl}'",
            "$limit": "2",
        }
    )
    url = f"https://data.cityofnewyork.us/resource/64uk-42ks.json?{query}"
    try:
        req = urllib.request.Request(url, headers={"accept": "application/json", "user-agent": "szl-real-estate/0.1"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read(1_048_577)
            if len(raw) > 1_048_576:
                raise ValueError("PLUTO response exceeds bound")
            rows = json.loads(raw.decode("utf-8") or "[]")
    except Exception as exc:  # system boundary: public API — fail closed, never invent assessment
        return _empty_pluto(
            geoid,
            parcel_id,
            f"NYC PLUTO unreachable ({type(exc).__name__}). Assessment UNAVAILABLE. Occupancy UNAVAILABLE.",
        )
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return _empty_pluto(geoid, parcel_id, "Exact BBL join missing, ambiguous, or malformed. Assessment UNAVAILABLE.")
    row = rows[0]
    matched_bbl = re.fullmatch(r"([1-5]\d{9})(?:\.0+)?", str(row.get("bbl", "")))
    try:
        matched_tract = Decimal(str(row.get("ct2010"))) == Decimal(geoid[5:]) / 100
        assess = float(row["assesstot"])
        units = float(row["unitsres"])
        year = float(row["yearbuilt"]) if row.get("yearbuilt") else None
        valid_numbers = math.isfinite(assess) and assess >= 0 and math.isfinite(units) and units >= 0 and units.is_integer()
        if year is not None:
            valid_numbers = valid_numbers and math.isfinite(year) and year >= 0 and year.is_integer()
    except (KeyError, TypeError, ValueError, InvalidOperation):
        matched_tract, valid_numbers = False, False
    if not matched_bbl or matched_bbl[1] != bbl or str(row.get("borocode")) != boro or not matched_tract or not valid_numbers:
        return _empty_pluto(geoid, parcel_id, "Returned parcel identity or assessment failed validation. Assessment UNAVAILABLE.")
    return {
        "tract": geoid,
        "parcelId": parcel_id,
        "address": row.get("address"),
        "bbl": bbl,
        "parcel_id_namespace": "NYC_BBL",
        "identity_state": "EXACT_BBL",
        "assessTot": assess,
        "unitsRes": int(units),
        "yearBuilt": int(year) if year is not None else None,
        "honesty": "MEASURED",
        "source_uri": url,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "observed_at": now(),
        "note": "NYC PLUTO assessed total and residential units are MEASURED public records. Unit occupancy stays UNAVAILABLE. Not an MLS.",
    }


def _willay(signal: str) -> bool:
    return bool(re.search(r"ignore (the )?policy|bypass (the )?gate|disable willay|override lambda|jailbreak", signal, re.I))


def run_parcel(parcel_id: str, signal: str) -> dict[str, Any]:
    if proven_trust is True:
        raise RuntimeError("refusing proven_trust true")
    meta = next((p for p in PARCELS if p["id"] == parcel_id), None)
    if meta is None:
        result = envelope({
            "vertical": "real-estate", "id": parcel_id,
            "identity_state": "UNKNOWN_PARCEL", "honesty": "UNAVAILABLE",
            "decision": "BLOCKED_PENDING", "actuation": "NONE",
            "output": "Unknown parcel identifier; no parcel was substituted. Parcel evidence UNAVAILABLE.",
            "occupancy": "UNAVAILABLE", "proven_trust": False,
            "checked_at": now(),
        })
        result["ok"] = False
        return result
    mls = bool(re.search(r"\bmls\b|lockbox|showing|list the house", signal, re.I))
    fire = _willay(signal)
    pluto = fetch_pluto(str(meta["tract"]), str(meta["id"]), bbl=meta.get("bbl"))
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
        "parcel_id_namespace": "SZL_MODELED_FIXTURE",
        "identity_state": "MODELED_FIXTURE",
        "honesty": "MODELED",
        "county": meta["county"],
        "tract": meta["tract"],
        "fema_letter": meta["fema"],
        "fema_honesty": "MODELED",
        "assessor": meta["assessor"],
        "assessor_honesty": "MODELED",
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
