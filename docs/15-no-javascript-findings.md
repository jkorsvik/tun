# 15. The no-JavaScript question — findings, and one falsification

Partial answer to the question "can a standalone HTML file work without
JavaScript?" ("Javascript-løs standalone HTML"). It does not close the question. It
changes what the question is about.

`docs/11-responsiveness-and-browser-support.md` §1 and §3b leave one decision
open: should a BUNDLED dashboard **require** JavaScript and degrade visibly when
it fails (§3b's warning pattern), or should it **not need** JavaScript at all
(the no-JS demos, `examples/13-js-free-standalone-poc/` and
`examples/14-chart-emulation-nojs-poc/`)?

The honest answer from the evidence already in this repository: **the question is
wrongly framed, and one half of the demos' answer is already falsified.**

## 1. "No JavaScript" is not one property

Three separate things on a dashboard page either need a script or do not. They
have different verdicts, and mixing them is what makes the decision look
undecidable.

| Capability | Can it be script-free? | Evidence |
|---|---|---|
| **Reading the data** | Only in BUNDLED | PAIRED needs `<script src="data.js">` to read a sibling file at all — `docs/01` row 14, `docs/02` "Updating the data". Tier 2 and Tier 3 need a script environment by construction |
| **Switching views** | Partly — see §2 | `examples/13` proves `:checked` and `:target` work locally; `docs/01` row 24 falsifies `:target` in SharePoint's inline preview |
| **Drawing charts** | Yes, if the data is known at build time | `examples/14`, twelve chart types as static CSS/SVG |

So "can we drop JavaScript?" has no single answer. Charts: yes. Data: only in one
mode. Navigation: it depends on the mechanism, and that is the part that broke.

## 2. The falsification

`examples/13-js-free-standalone-poc/` switches pages with CSS `:target`
(`js-free-standalone-poc.html:188-200`, links at `:279`). Its README records the
visible `#page-charts` fragment in the URL as an accepted, documented cost.

`docs/01-tenant-constraints.md` row 24 tested exactly that mechanism in
SharePoint's inline file-preview, isolated to a bare-minimum page with three
links and three `:target` boxes:

> Clicking never changed which box was visible — fragment navigation itself did
> not occur. An otherwise-identical page using a JavaScript click handler
> switched correctly on the first click.

**Fragment navigation is blocked in that surface, while JavaScript itself runs
fine there (row 25 for the separate script-gating problem).** So:

- The script-free **page switching** in `examples/13` does not work in SharePoint
  inline preview. Not "degrades" — does not switch.
- The `:checked` half (menu, info panel, theme toggle) involves no navigation and
  is not touched by row 24. It has also not been tested in that surface, so it is
  **unproven there, not proven.**
- `examples/14`'s static charts involve neither script nor navigation. They are
  the one part of the no-JS demos that survives intact.

## 3. Why the demos could not have caught this

`examples/13` was verified by toggling JavaScript on and off in a local browser,
and it behaves identically both ways. That verification is correct and it is
irrelevant to row 24, because row 24 is not about JavaScript being on or off. It
is about a host surface refusing to perform a navigation.

The demos were verified in the one environment that cannot falsify them. A local
browser at `file://` honours fragment navigation; the surface that matters does
not. The claim "works with JavaScript off" was never the claim that needed
testing.

This is the same failure shape as row 23's retracted multi-line conclusion: a
result measured in the wrong place, believed because it was reproducible.

## 4. What the constraint surface actually rewards

Row 25 makes this sharper rather than softer. A literal `<script` substring
anywhere in the file — even inside a comment, never executed — appears to gate
whether **any** script on the page runs. A page that genuinely contains no script
tag is immune to that failure mode, provided it also never types those characters
as prose.

So there is a real argument for script-free construction, and it is not the
argument the demos made. It is not "JavaScript might be disabled". It is:

- **the tenant may refuse to run scripts for reasons unrelated to your code**
  (row 25, a text scan; row 22, the sharing path on mobile), and
- **a page with no script cannot be broken by any of that.**

But the same tenant blocks fragment navigation. So the script-free page must not
navigate either.

## 5. Consequence: what a script-free BUNDLED dashboard may use

Narrower than the demos assumed, still useful:

- **Allowed:** `<input type="checkbox">` / `<input type="radio">` plus `:checked`
  and sibling selectors for menus, panels, theme and — untested but structurally
  sound — page switching, because no navigation occurs. `<details>`/`<summary>`.
  Static CSS/SVG charts with build-time data. A non-scrolling flex shell with one
  scrolling container (row 26).
- **Not allowed:** `<a href="#...">` with `:target` for anything load-bearing.
  `position:sticky` and `position:fixed` for headers (row 26). The literal text
  `<script` as prose anywhere (row 25).

The obvious repair for `examples/13` is to move page switching from `:target` to
radio inputs plus `:checked`, which removes the navigation dependency and the
visible fragment at the same time. Not done in this document; it is a code change
and needs its own verification in the preview surface, not in a local browser.

## 6. What is still open

- Radio-plus-`:checked` page switching has **not** been tested in SharePoint
  inline preview. Until it is, script-free navigation is a hypothesis.
- Neither template from `tools/` ships any of this. The no-JS demos remain examples.
- The §3b warning pattern and script-free construction are **not** alternatives
  to choose between. §3b is the only option for PAIRED and Tier 2/3. Script-free
  is only available in BUNDLED. Any dashboard that needs live or paired data has
  already made the choice.

## 7. Documentation drift this exposes

`docs/11` §1 states that the no-JS demos' navigation was "verified to behave identically
with JavaScript on or off" and does not mention row 24. Both statements are true;
together they read as though the mechanism is settled. `docs/11` should carry a
pointer to row 24 where it describes `:target`, and `examples/13`'s README should
record that its page-switching mechanism is known to fail in one shipped surface.

Not edited here on purpose: this document is the finding. Changing the other two
files is a separate, reviewable change.

## 8. Let the reader see the fallback on purpose

Two techniques from an internal presentation on these findings, built with the rules in
this repository. Neither is measured in the tenant. Both are cheap and worth copying.

**A visible "simulate no scripts" switch.** The presentation is one long, scrollable
document with no script, and a full-screen deck with arrow-key navigation when scripts run.
It carries a button that removes the enhancement from the whole page, so the viewer sees
exactly what a recipient without running scripts would see. A clearly labelled way back
stays fixed on screen while the simulation is on. This does two jobs at once:

- it proves the degradation claim to a sceptical audience, live, instead of asserting it;
- it gives a human reviewer a one-click check of the no-script state, which the headless
  gates cannot judge for layout (`AGENTS.md` rule 3: look at the artefact).

The "way back" must itself work without depending on the state it undoes. A restore
control that only the enhanced page renders is the same logical dead end §3b point 4 of
`docs/11` describes for diagnostics.

**When scripts are dead, the notice is the page.** In a surface that will never run the
file's scripts (row 22's e-mail link on mobile, `docs/11` §3c's Quick Look), the reader
cannot fix anything from inside the page. So the notice should be the first and largest
thing on screen, not a strip above empty boxes, and it must name the route out in the
reader's terms: open the link through the Teams preview card, or choose "open in browser".
An explanation without a next step is still a dead end.

What still needs a script whatever the construction, so the notice has to cover it:

- reading a sister file (paired), because there is no script-free way to read one;
- any update without a new file;
- full-screen presentation mode with keyboard navigation.
