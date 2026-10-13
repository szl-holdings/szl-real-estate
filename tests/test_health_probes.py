# SPDX-License-Identifier: Apache-2.0
"""Liveness vs readiness probe semantics, served over a local 127.0.0.1 socket."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import szl_space_brain
from app import Handler

MISSING_MODULE = "szl_substrate.szl_brain"


def _status(missing):
    return {
        "label": "MEASURED",
        "substrate_sha": szl_space_brain.SUBSTRATE_SHA,
        "loaded": [],
        "missing": missing,
        "locked_proven_count": 8,
        "locked_proven_ids": list(szl_space_brain.LOCKED_EIGHT),
        "lambda": {"status": "OPEN", "label": "REPORTED", "name": "Conjecture 1"},
    }


DEGRADED = _status([{"module": MISSING_MODULE, "error": "ModuleNotFoundError"}])
RESTORED = _status([])


class HealthProbes(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as res:
                return res.status, res.headers, json.load(res)
        except urllib.error.HTTPError as err:
            with err:
                return err.code, err.headers, json.load(err)

    def test_healthz_stays_live_while_substrate_is_missing(self):
        with patch("app.substrate_status", return_value=DEGRADED):
            for path in ("/healthz", "/healthz/"):
                with self.subTest(path=path):
                    status, headers, body = self.get(path)
                    self.assertEqual(status, 200)
                    self.assertEqual(headers["Content-Type"], "application/json")
                    self.assertFalse(body["ok"])
                    self.assertEqual(body["second_brain"], "DEGRADED")
                    self.assertFalse(body["proven_trust"])
                    self.assertNotIn("ready", body)

    def test_readyz_is_503_with_explicit_reason_while_substrate_is_missing(self):
        with patch("app.substrate_status", return_value=DEGRADED):
            for path in ("/readyz", "/readyz/"):
                with self.subTest(path=path):
                    status, headers, body = self.get(path)
                    self.assertEqual(status, 503)
                    self.assertEqual(headers["Content-Type"], "application/json")
                    self.assertEqual(headers["Cache-Control"], "no-store")
                    self.assertFalse(body["ready"])
                    self.assertFalse(body["ok"])
                    self.assertEqual(body["second_brain"], "DEGRADED")
                    self.assertEqual(
                        body["missing"], [{"module": MISSING_MODULE, "error": "ModuleNotFoundError"}]
                    )

    def test_readyz_is_200_when_dependencies_are_restored(self):
        with patch("app.substrate_status", return_value=RESTORED):
            status, _, body = self.get("/readyz")
            self.assertEqual(status, 200)
            self.assertTrue(body["ready"])
            self.assertTrue(body["ok"])
            self.assertEqual(body["missing"], [])
            status, _, body = self.get("/healthz")
            self.assertEqual(status, 200)
            self.assertTrue(body["ok"])

    def test_real_import_failure_drives_readiness(self):
        # Exercise the real substrate_status import path rather than a stub.
        absent = "szl_substrate_absent_for_readyz_test"
        with patch.object(szl_space_brain, "MODULES", ("json", absent)):
            status, _, body = self.get("/readyz")
            self.assertEqual(status, 503)
            self.assertEqual([m["module"] for m in body["missing"]], [absent])
            self.assertEqual(self.get("/healthz")[0], 200)
        with patch.object(szl_space_brain, "MODULES", ("json",)):
            status, _, body = self.get("/readyz")
            self.assertEqual(status, 200)
            self.assertTrue(body["ready"])


if __name__ == "__main__":
    unittest.main()
