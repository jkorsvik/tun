#!/usr/bin/env python3
"""
verify_dashboard.py — prove a built dashboard actually works before anyone ships it.

This is the hard gate used by the skill `tun-verify`. A dashboard that
"should work" is worth nothing: the entire premise of a portable artefact is that it
opens on *someone else's* machine. So we open it in a real browser, from a real
`file://` URL — exactly how a recipient will — and assert on what rendered.

Per docs/08-generic-artifact-model.md, the checks below split into two layers:

  GENERIC  (imported from tools/verify_standalone_core.py — do not re-implement here,
            see docs/14-generic-layer-manifest.md for what "generic" means):
    1. self-contained — no external http(s) subresource references
    2. size within the Tier 1 budget
    3. no unsubstituted {{PLACEHOLDER}} left in the shipped file
    4. provenance block intact
    5. renders from file:// without a console error
    6. screenshot written for human review

  DASHBOARD-SPECIFIC (this file only):
    7. paired-mode sidecar present and valid, if applicable
    8. JS actually executed (charts/KPIs present in the DOM, not just markup)
    9. interactivity works (a filter change re-renders)

    python3 tools/verify_dashboard.py dashboards/salg.html [--engines chromium,firefox,webkit]

Exit 0 = safe to publish. Non-zero = do not publish.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from verify_standalone_core import (  # noqa: E402
    add_engines_arg,
    check_no_leftover_placeholders,
    check_no_stray_script_text,
    check_provenance,
    check_self_contained,
    check_size,
    label_failures,
    shot_path,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    add_engines_arg(ap)
    args = ap.parse_args()
    path = pathlib.Path(args.path).resolve()
    if not path.exists():
        print(f"✗ not found: {path}")
        return 2

    html = path.read_text(encoding="utf-8", errors="replace")
    failures: list[str] = []
    warnings: list[str] = []

    print(f"verifying {path.name}")
    print("─" * 60)

    # 1 — self-contained (generic)
    ok, msg = check_self_contained(html)
    print(f"  {'✓' if ok else '✗'} self-contained     {msg}")
    if not ok:
        failures.append(msg)

    # 2 — size (generic)
    level, msg, _ = check_size(path)
    icon = {"ok": "✓", "warn": "⚠", "fail": "✗"}[level]
    print(f"  {icon} size               {msg}")
    if level == "fail":
        failures.append(msg)
    elif level == "warn":
        warnings.append(msg)

    # 2b — paired mode: the data sibling must be there (dashboard-specific)
    if 'src="./data.js"' in html:
        sibling = path.with_name("data.js")
        if sibling.exists():
            d_kb = sibling.stat().st_size / 1024
            print(f"  ✓ paired data        data.js present ({d_kb:.0f} KB)")
            body = sibling.read_text(encoding="utf-8", errors="replace")
            if "DASHBOARD_DATA" not in body and "DASHBOARD_CSV" not in body:
                failures.append("data.js sets neither window.DASHBOARD_DATA nor "
                                "window.DASHBOARD_CSV")
                print("  ✗ paired data        data.js sets no recognised payload")
        else:
            failures.append("paired mode but data.js is missing next to the dashboard")
            print("  ✗ paired data        data.js NOT FOUND — the two files must travel together")
    else:
        print("  ✓ mode               bundled (data inlined)")

    # 3 — provenance (generic)
    ok, msg = check_provenance(html)
    print(f"  {'✓' if ok else '⚠'} provenance         {msg}")
    if not ok:
        warnings.append(msg)

    # 4 — unsubstituted placeholders (generic)
    ok, msg = check_no_leftover_placeholders(html)
    print(f"  {'✓' if ok else '✗'} placeholders       {msg}")
    if not ok:
        failures.append(msg)

    # 4b — stray script text (row 25). verify_standalone_core has always exported this
    # check and this tool never called it, so every dashboard built from a template whose
    # comments mention a tag shipped with the violation and was still told "safe to
    # publish". The check is cheap and textual; there is no reason for it to be optional.
    ok, msg = check_no_stray_script_text(html)
    print(f"  {'✓' if ok else '✗'} no-stray-script    {msg}")
    if not ok:
        failures.append(msg)

    # 5..7 — real browser render (generic console-clean + screenshot, dashboard DOM checks)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        failures.append("playwright not installed — the browser checks (render, console, "
                        "JS executed, charts, table, interactivity, screenshot) could not "
                        "run, so this file has NOT been verified. Install with: "
                        "uv sync --extra verify && uv run playwright install chromium")
        print("  ✗ render             BLOCKED — playwright not installed, browser checks "
              "could not run")
        return _report(failures, warnings)

    with sync_playwright() as pw:
        for engine in args.engines:
            print(f"  · {engine}")
            mark = len(failures)
            shot = shot_path(path, ".verify.png", engine)
            browser = getattr(pw, engine).launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors: list[str] = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))

            page.goto(path.as_uri())
            page.wait_for_timeout(1200)

            if errors:
                failures.append(f"{len(errors)} console error(s): {errors[0][:160]}")
                print(f"  ✗ console            {len(errors)} error(s): {errors[0][:80]}")
            else:
                print("  ✓ console            clean")

            kpis = page.locator(".kpi").count()
            bars = page.locator(".bar").count()
            rows = page.locator("#tbl tbody tr").count()
            dots = page.locator(".dot").count()

            if kpis == 0:
                failures.append("no KPI cards rendered — JS did not execute")
                print("  ✗ JS executed        0 KPI cards")
            else:
                print(f"  ✓ JS executed        {kpis} KPI cards")

            if bars == 0 and dots == 0:
                failures.append("no chart marks rendered — charts are empty")
                print("  ✗ charts             0 marks rendered")
            else:
                print(f"  ✓ charts             {bars} bars, {dots} line points")

            if rows == 0:
                failures.append("detail table rendered zero rows")
                print("  ✗ table              0 rows")
            else:
                print(f"  ✓ table              {rows} rows")

            # interactivity: drive a real filter and confirm the numbers moved.
            # Two dashboard shapes: <select> controls (rows template) and .chip toggles
            # (cube template). A gate that only knows one of them passes vacuously.
            selects = page.locator("#controls select")
            chips = page.locator(".chips .chip")
            if selects.count():
                before = page.locator("#tbl tbody tr").count()
                options = selects.first.locator("option")
                if options.count() > 1:
                    selects.first.select_option(index=1)
                    page.wait_for_timeout(500)
                    after = page.locator("#tbl tbody tr").count()
                    if after == before and before > 0:
                        warnings.append("filter change did not alter the row count "
                                        "(may be legitimate for uniform data)")
                        print(f"  ⚠ interactivity      filter changed nothing ({before} rows)")
                    else:
                        print(f"  ✓ interactivity      filter re-rendered ({before} → {after} rows)")
                    # Reset before the human-review screenshot. Without this the screenshot
                    # a person is told to look at before publishing shows the filtered state
                    # left over from this test, not the page the recipient actually opens —
                    # exactly the state a reviewer has no reason to discount and every reason
                    # to mistake for the real default.
                    reset = page.locator("#reset")
                    if reset.count():
                        reset.click()
                        page.wait_for_timeout(300)
                        restored = page.locator("#tbl tbody tr").count()
                        if restored != before:
                            failures.append(
                                f"reset did not restore the unfiltered row count "
                                f"({before} before filtering, {restored} after reset)"
                            )
                            print(f"  ✗ reset              did not restore row count ({before} → {restored})")
                        else:
                            print(f"  ✓ reset              restores the unfiltered view")
                else:
                    warnings.append("filter has only one option")
                    print("  ⚠ interactivity      filter has a single option")
            elif chips.count():
                # cube template: compare the headline KPI before and after one toggle
                kpi = page.locator(".kpi .v").first
                before = kpi.inner_text()
                chips.first.click()
                page.wait_for_timeout(300)
                after = kpi.inner_text()
                if after == before:
                    failures.append(f"chip filter changed nothing — KPI stayed at {before!r}")
                    print(f"  ✗ interactivity      chip filter changed nothing ({before})")
                else:
                    print(f"  ✓ interactivity      chip filter re-rendered ({before} → {after})")
                    reset = page.locator("#reset")
                    if reset.count():
                        reset.click()
                        page.wait_for_timeout(300)
                        if kpi.inner_text() != before:
                            failures.append("reset did not restore the unfiltered total")
                            print("  ✗ reset              did not restore the unfiltered total")
                        else:
                            print("  ✓ reset              restores the unfiltered total")
            else:
                warnings.append("no filter controls present")
                print("  ⚠ interactivity      no filters to test")

            page.screenshot(path=str(shot), full_page=True)
            print(f"  ✓ screenshot         {shot.name}")
            browser.close()
            label_failures(failures, mark, engine, args.engines)

    return _report(failures, warnings, shot_path(path, ".verify.png", args.engines[0]))


def _report(failures, warnings, shot=None) -> int:
    print("─" * 60)
    for w in warnings:
        print(f"  warn: {w}")
    if failures:
        print(f"\n✗ FAIL — {len(failures)} blocking issue(s). Do NOT publish.")
        for f in failures:
            print(f"    • {f}")
        return 1
    print("\n✓ PASS — safe to publish.")
    if shot:
        print(f"  Review the screenshot before sharing: {shot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
