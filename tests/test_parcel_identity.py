"""Identity regressions with fabricated records; no live-data qualification."""
import hashlib
import io
import json
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app import Handler
from szl_re.underwrite import PARCELS, fetch_pluto, run_parcel


class ParcelIdentity(unittest.TestCase):
    def test_unknown_and_missing_ids_do_not_substitute_or_fetch(self):
        with patch("szl_re.underwrite.fetch_pluto") as fetch:
            for parcel_id in ("UNKNOWN-PARCEL", "", None):
                with self.subTest(parcel_id=parcel_id):
                    result = run_parcel(parcel_id, "research")
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["body"]["id"], parcel_id)
                    self.assertEqual(result["body"]["identity_state"], "UNKNOWN_PARCEL")
                    self.assertEqual(result["body"]["decision"], "BLOCKED_PENDING")
                    self.assertNotIn("county", result["body"])
            fetch.assert_not_called()

    def test_fixtures_do_not_invent_bbl_or_live_assessment(self):
        with patch("urllib.request.urlopen") as remote:
            for parcel in PARCELS:
                result = run_parcel(parcel["id"], "research")["body"]
                self.assertEqual(result["identity_state"], "MODELED_FIXTURE")
                self.assertEqual(result["fema_honesty"], "MODELED")
                self.assertEqual(result["pluto"]["honesty"], "UNAVAILABLE")
                self.assertIsNone(result["pluto"]["assessTot"])
            remote.assert_not_called()

    def record(self, **changes):
        return dict(address="EXAMPLE ONLY", bbl="3000010001.000", ct2010="11.00",
                    borocode="3", assesstot="1200", unitsres="2", yearbuilt="1900", **changes)

    def fetch(self, rows):
        raw = json.dumps(rows).encode()
        with patch("urllib.request.urlopen", return_value=io.BytesIO(raw)) as remote:
            result = fetch_pluto("36047001100", "test", bbl="3000010001")
        return result, remote, raw

    def test_exact_bbl_query_and_source_digest(self):
        result, remote, raw = self.fetch([self.record()])
        query = urllib.parse.parse_qs(urllib.parse.urlparse(remote.call_args.args[0].full_url).query)
        self.assertEqual(query["$where"], ["bbl='3000010001'"])
        self.assertEqual(query["$limit"], ["2"])
        self.assertNotIn("$order", query)
        self.assertEqual(result["honesty"], "MEASURED")
        self.assertEqual(result["identity_state"], "EXACT_BBL")
        self.assertEqual(result["source_sha256"], hashlib.sha256(raw).hexdigest())

    def test_missing_ambiguous_mismatched_and_nonfinite_records_are_unavailable(self):
        variants = [[], [self.record(), self.record()], {}, [None]]
        for key, value in (("bbl", "3000010002"), ("ct2010", "12"),
                           ("borocode", "4"), ("assesstot", "NaN"),
                           ("unitsres", "-1"), ("unitsres", "1.5"), ("yearbuilt", "inf")):
            row = self.record()
            row[key] = value
            variants.append([row])
        for rows in variants:
            with self.subTest(rows=rows):
                self.assertEqual(self.fetch(rows)[0]["honesty"], "UNAVAILABLE")

    def test_invalid_identity_does_not_query_provider(self):
        with patch("urllib.request.urlopen") as remote:
            for tract, bbl in (("36047001100", None), ("36047001100", "4000010001"),
                               ("bad", "3000010001"), (None, "3000010001")):
                self.assertEqual(fetch_pluto(tract, "test", bbl=bbl)["honesty"], "UNAVAILABLE")
            remote.assert_not_called()

    def test_http_get_and_post_reject_unknown_or_missing_identity(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}/api/underwrite"
        try:
            for query in ("", "?id=", "?id=UNKNOWN-PARCEL"):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(base + query)
                self.assertEqual(error.exception.code, 404)
                self.assertEqual(json.load(error.exception)["body"]["identity_state"], "UNKNOWN_PARCEL")
            for body in ({}, {"id": "UNKNOWN-PARCEL"}):
                request = urllib.request.Request(base, data=json.dumps(body).encode(),
                                                 headers={"Content-Type": "application/json"})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
