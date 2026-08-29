# SPDX-License-Identifier: Apache-2.0
import unittest

from szl_re.underwrite import run_parcel


class RealEstate(unittest.TestCase):
    def test_blocks_mls(self):
        r = run_parcel("R-BK-11", "push this to MLS with lockbox")
        self.assertEqual(r["body"]["decision"], "BLOCKED")
        self.assertEqual(r["body"]["occupancy"], "UNAVAILABLE")

    def test_nassau_no_pluto(self):
        r = run_parcel("R-NS-04", "public records only")
        self.assertEqual(r["body"]["pluto"]["honesty"], "UNAVAILABLE")
        self.assertIn("Nassau", r["body"]["pluto"]["note"])

    def test_hash(self):
        r = run_parcel("R-BK-11", "underwrite")
        self.assertEqual(len(r["receipt_sha256"]), 64)
        self.assertTrue(r["signing"].startswith("STRUCTURAL-ONLY"))


if __name__ == "__main__":
    unittest.main()
