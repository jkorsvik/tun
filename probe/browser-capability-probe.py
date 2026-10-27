#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
browser-capability-probe.py — re-verify what a `file://` page can and cannot reach,
for capabilities NOT covered by probe/tenant-probe.py.

tenant-probe.py answers Graph/SharePoint-side questions (does the tenant serve .html
as attachment, is Range supported, ...). This script answers a different question:
once a file is downloaded and opened locally, what does the BROWSER itself allow from
origin `null`? That is a browser-platform rule, not a Eksempel AS tenant policy, but it is just
as load-bearing for anything in docs/01-tenant-constraints.md — see rows 19-20 there.

Requires only Playwright + a locally installed Chromium — no Graph token, no tenant
access, reproducible on any machine.

    uv run playwright install chromium   # once
    python3 probe/browser-capability-probe.py

Exit 0 always — this script reports findings for a human to read and update the docs
with; unlike tenant-probe.py there is no fixed EXPECTED baseline yet, because at least
one of the two capabilities tested (File System Access API) cannot be driven to a
pass/fail verdict headlessly. Read the printed findings.
"""
from __future__ import annotations

import pathlib
import tempfile

FIXTURE_FEATURES = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<h1>probe</h1>
<script>
window.__results = {
  fsapi_present: (typeof window.showDirectoryPicker === "function"),
  worker_ctor_present: (typeof Worker === "function"),
  blob_present: (typeof Blob === "function"),
  decompressionstream_present: (typeof DecompressionStream === "function"),
};

window.__fsapiNoGesture = async function() {
  try {
    await window.showDirectoryPicker({ mode: "readwrite" });
    return { ok: true, note: "picker resolved with no user gesture (unexpected)" };
  } catch (e) {
    return { ok: false, name: e.name, message: String(e.message || e) };
  }
};

window.__workerBlob = function() {
  return new Promise((resolve) => {
    try {
      const src = "onmessage = function(e) { postMessage(e.data * 2); };";
      const blob = new Blob([src], { type: "application/javascript" });
      const url = URL.createObjectURL(blob);
      const w = new Worker(url);
      const timeout = setTimeout(() => resolve({ ok: false, name: "Timeout",
        message: "no response in 3s" }), 3000);
      w.onmessage = (ev) => { clearTimeout(timeout);
        resolve({ ok: true, echoed: ev.data }); w.terminate(); };
      w.onerror = (ev) => { clearTimeout(timeout);
        resolve({ ok: false, name: "WorkerError", message: ev.message || String(ev) }); };
      w.postMessage(21);
    } catch (e) {
      resolve({ ok: false, name: e.name, message: String(e.message || e) });
    }
  });
};

window.__workerExternal = function() {
  return new Promise((resolve) => {
    try {
      const w = new Worker("./does-not-exist-worker.js");
      const timeout = setTimeout(() => resolve({ ok: false, name: "Timeout",
        message: "no response in 1.5s" }), 1500);
      w.onmessage = () => { clearTimeout(timeout); resolve({ ok: true }); w.terminate(); };
      w.onerror = (ev) => { clearTimeout(timeout);
        resolve({ ok: false, name: "WorkerError", message: ev.message || String(ev) }); };
    } catch (e) {
      resolve({ ok: false, name: e.name, message: String(e.message || e) });
    }
  });
};
</script>
</body></html>"""

FIXTURE_GESTURE = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<button id="btn">pick</button>
<div id="out">pending</div>
<script>
document.getElementById('btn').addEventListener('click', async () => {
  try {
    const handle = await window.showDirectoryPicker({ mode: "readwrite" });
    document.getElementById('out').textContent = "OK:" + handle.name;
  } catch (e) {
    document.getElementById('out').textContent = "ERR:" + e.name + ":" + e.message;
  }
});
</script>
</body></html>"""


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("✗ playwright not installed — run: uv run playwright install chromium")
        return 2

    tmpdir = pathlib.Path(tempfile.mkdtemp())

    print("Browser-capability probe — file:// origin, rows 19-20 of the constraints doc")
    print("=" * 78)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        print(f"  chromium build: {browser.version}")

        # --- part 1: feature detection + no-gesture call ---
        f1 = tmpdir / "probe1.html"
        f1.write_text(FIXTURE_FEATURES, encoding="utf-8")
        page = browser.new_page()
        page.goto(f1.as_uri())
        print(f"  page origin: {page.evaluate('location.origin')!r}\n")

        feats = page.evaluate("window.__results")
        print("Feature detection")
        print("-" * 78)
        for k, v in feats.items():
            print(f"  {'✓' if v else '✗'} {k:<32} {v}")
        print()

        print("Row 19a — showDirectoryPicker() called with NO user gesture")
        print("-" * 78)
        print(f"  result: {page.evaluate('window.__fsapiNoGesture()')}")
        print()

        print("Row 20 — inline Worker constructed from a Blob URL (no external file)")
        print("-" * 78)
        print(f"  result: {page.evaluate('window.__workerBlob()')}")
        print()

        print("Row 20 control — Worker from an external relative path (expect fail)")
        print("-" * 78)
        print(f"  result: {page.evaluate('window.__workerExternal()')}")
        print()
        page.close()

        # --- part 2: showDirectoryPicker with a REAL click-triggered gesture ---
        f2 = tmpdir / "probe2.html"
        f2.write_text(FIXTURE_GESTURE, encoding="utf-8")
        page2 = browser.new_page()
        page2.goto(f2.as_uri())
        page2.click("#btn", timeout=5000)
        page2.wait_for_timeout(1500)
        result = page2.text_content("#out")
        print("Row 19b — showDirectoryPicker() with a REAL click-triggered gesture")
        print("-" * 78)
        print(f"  result: {result}")
        if "AbortError" in (result or ""):
            print("  → same AbortError as the no-gesture call: headless Chromium has no")
            print("    display to render the native OS picker on, so it auto-cancels")
            print("    regardless of activation. This path needs a HEADED browser and a")
            print("    human to verify past this point — it cannot be scripted further.")
        page2.close()

        browser.close()

    print("\n" + "=" * 78)
    print("No pass/fail verdict printed for row 19 — read docs/01-tenant-constraints.md")
    print("for why, and update it if any result above changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
