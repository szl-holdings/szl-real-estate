#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""HF Space entry for szl-real-estate."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from szl_re.underwrite import PARCELS, run_parcel
from szl_space_brain import anatomy, substrate_status

ROOT = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    server_version = "szl-real-estate/0.2"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _send(self, status, raw, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in {"/healthz", "/readyz"}:
            brain = substrate_status()
            body = json.dumps({
                "ok": not brain["missing"],
                "occupancy": "UNAVAILABLE",
                "proven_trust": False,
                "second_brain": "LIVE" if not brain["missing"] else "DEGRADED",
                "locked_proven_count": brain["locked_proven_count"],
                "lambda": "Conjecture 1 OPEN",
            }).encode()
            self._send(200, body, "application/json")
            return
        if path == "/api/second-brain":
            self._send(200, json.dumps(anatomy("szl-real-estate"), indent=2).encode(), "application/json")
            return
        if path == "/api/formulas":
            self._send(200, json.dumps(substrate_status(), indent=2).encode(), "application/json")
            return
        if path == "/api/parcels":
            self._send(200, json.dumps({"ok": True, "parcels": list(PARCELS)}).encode(), "application/json")
            return
        if path in {"/", "/index.html"}:
            html = (ROOT / "index.html").read_text(encoding="utf-8")
            self._send(200, html.encode(), "text/html; charset=utf-8")
            return
        qs = parse_qs(urlparse(self.path).query)
        if path == "/api/underwrite":
            rec = run_parcel(qs.get("id", ["R-BK-11"])[0], qs.get("signal", [""])[0])
            self._send(200, json.dumps(rec, indent=2, default=str).encode(), "application/json")
            return
        self._send(404, json.dumps({"ok": False}).encode(), "application/json")

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(max(0, min(length, 200000))) if length else b"{}"
        try:
            data = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            data = {}
        if path != "/api/underwrite":
            self._send(404, json.dumps({"ok": False}).encode(), "application/json")
            return
        rec = run_parcel(str(data.get("id") or "R-BK-11"), str(data.get("signal") or ""))
        self._send(200, json.dumps(rec, indent=2, default=str).encode(), "application/json")


if __name__ == "__main__":
    port = 7860
    print(f"[szl-real-estate] 0.0.0.0:{port} · second-brain governed runtime", file=sys.stderr)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
