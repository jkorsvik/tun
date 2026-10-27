# 18. Naming — decided, with one part still open

**Reader:** record — a decision or a measurement, kept for why something is the way it is.

**Decided:** the brand is **Tún**. The domain is **tun.community**. Both are
settled and this document records them rather than arguing them.

**Also decided:** the repository identifier is `tun`
(the internal forge, under the maintainer's namespace). The repository was renamed from
`tun` on 2026-09-17; the old name now works only as a
GitHub redirect.

**Still open:** the package name on PyPI and npm, and the CLI name. The repository
name does not settle those, because `tun` is already taken on npm, and because
the collision described below is worse for a package than for a repository.

## The three words and their jobs

| Word | Job | Status |
|---|---|---|
| `Tún` | the noun; the enclosed place where the farm gathers, where resources are put and knowledge is shared | **Adopted as the brand.** Found by the colleague credited at the foot of this page |
| `å tunfeste` | Norwegian verb; to gather, structure and anchor information so it becomes understandable, findable and trustworthy | Kept. The most distinctive of the three, and the leading candidate for the package identifier |
| `å tune` | Norwegian verb, **a new coinage from `tún`** — to bring something into the tún. Not the English word `tune` and not `tuning` | Kept as a verb. **Not** a product name or an identifier; see below |

So the name is one noun and two Norwegian verbs: *å tunfeste* and *å tune*, both
derived from `Tún`. The short one is the everyday word — *jeg tuner dataene* — and
`tunfeste` is the formal one for when the act needs spelling out.

`å tune` is **not** borrowed from English. It is built from the noun the same way
any Norwegian verb is, and it is pronounced as Norwegian: two syllables,
`tu-ne`, not the one-syllable English `tune`.

## The diacritic separates brand from identifier

`Tún` works as a display name. It cannot be the identifier.

- Package names, CLI commands, SPDX identifiers, environment variables and branch
  names are all effectively ASCII in practice.
- A domain with `ú` becomes an IDN with a punycode form, which people mistype and
  which some corporate mail filters treat as suspicious.
- `tun.community` already drops the accent, so brand and identifier already
  differ. That is not a defect; it is the normal arrangement, now made explicit.

## Why the identifier is not simply `tun`

`tun` is the name of the virtual network device on Unix systems. On this laptop
there are nine interfaces named `utun0` through `utun8`. For anyone technical,
`tun` reads as tunnel interface first.

Verified registry state, 2026-09-19:

| Name | npm | PyPI | crates.io |
|---|---|---|---|
| `tun` | taken | free | unknown |
| `tune` | taken | taken | unknown |
| `tunfest` | free | free | unknown |
| `tunfeste` | free | free | unknown |

crates.io returned 403 to a plain request, so those entries are **unknown, not
free.** Check through the site before relying on the table.

So `tun` as a bare package name is unavailable on npm, ambiguous everywhere, and
hard to search for. As a **repository** name that is acceptable: a repository is
found through a link or an organisation, not through a global namespace, and it is
free to rename again. As a **package** name it is not, because a package name is a
permanent public claim in a namespace everybody shares.

Candidates for the package and CLI, in order: `tunfeste`, then a compound such as
`tun-dashboards` or `tun-toolkit` that keeps the brand visible while staying
searchable. Not decided.

### The redirect is load-bearing, and it is fragile

Every artefact built before the rename carries `Repo: tun`
in its provenance block. That string resolves today only because GitHub redirects
the old name. **The redirect breaks the moment a repository with the old name is
created again under the same account.** So: never recreate
`tun`. It is not a free name; it is the thing that keeps
old provenance resolvable.

## `å tune` works as a verb and fails as a name

As a Norwegian verb it is good: short, regular to conjugate (*tuner, tunet*), and
it names the act rather than the tool. A verb people reach for on their own is the
strongest thing a brand can have, and it is why both verbs are kept.

As a **name** it fails on every test that matters, and for reasons that have
nothing to do with Norwegian:

- Written down it is sTunkallend exactly like the ordinary English word. An ordinary
  word is hard to protect as a trademark and easy to contest.
- It collides broadly in commerce and software: music services, hotel chains,
  audio tooling, and `tune` as a verb in machine learning.
- `tune` is taken on both npm and PyPI (table above).

A verb never has to pass those tests, because a verb is not registered, defended or
typed into a package manager. So the rule is narrow rather than a rejection: **use
`å tune` in Norwegian prose, never as the product name, the package, the CLI or
the repository.**

### The hazard is the English reader, not the Norwegian one

A Norwegian reader sees a verb built from `tún` and gets it immediately. An
English reader sees *tune*, which first means *adjust*. For a tool whose whole
claim is faithful provenance — the artefact shows what the source said, and the
footer proves where it came from — "they tuned the numbers" is exactly the wrong
reading, and in an audit conversation it is worse than clumsy.

Two consequences:

- The verb stays Norwegian. Do not translate it; there is no English *to tune* in
  this vocabulary. In English write *gather into the tún*, or keep the Norwegian
  word and gloss it once.
- Written material that mixes languages is where the misreading happens. In those
  places prefer `tunfeste`, which no English reader will misread.

If the short verb turns out to be misread anyway by people who matter, drop it and
keep `tunfeste` alone. The noun and the domain do not depend on it.

## What the domain decision commits us to

Every generated artefact embeds provenance and, once the name is adopted, will
carry the brand and very likely the URL. **Artefacts already sent can never be
updated.** So choosing `tun.community` is a commitment that the address answers
permanently, not a choice that can be revisited cheaply later.

That is an argument for getting the artefact footer right once, before any volume
of artefacts ships. See "Adopting the name" below.

## Trademark

The policy is [`TRADEMARK.md`](../TRADEMARK.md). Tún and the mark are unregistered marks
(™, never ®), and the code licence gives no right to them. A fork that changes the code takes
another name. Nominative use such as "works with Tún" is allowed. The mark follows the project,
which belongs to its authors (`17-licensing.md`, "Status"). The mark itself is in
`plugins/tun/assets/`.

None of these trademark checks has been done. The registry table above is about package
names, not trademarks:

- **Norway:** search the Patentstyret register for `Tún`, `Tun` and `tunfeste`, in the
  classes that fit. Likely 9 for software and 42 for software services. Confirm with whoever
  runs the search.
- **EU:** search EUIPO for EU trade marks, and the national registers of the member states
  (TMview covers both).
- **International:** search WIPO for registrations under the Madrid system that designate
  Norway or the EU.
- **Domains:** who holds the obvious neighbours of `tun.community`, for example `tun.no`,
  `tun.com` and the IDN `tún.no`.
- **Handles:** the GitHub organisation name (item 3 below), the npm and PyPI names for the
  chosen package, and any social handle the project would use.

## Still to check, now that the name is chosen

1. **Trademark:** the registry, domain and handle checks listed under
   "Trademark" above. A domain, a repository name and a free package name prove
   nothing about trademark.
2. **crates.io** and any other registry that matters, checked properly rather
   than through a request that returns 403.
3. **GitHub organisation name** availability.
4. **Conflict with the employer's brand.** This was question 6 in the letter to
   legal. Settled with the ownership answer (2026-10-11).
5. **Searchability mitigation:** decide to write `Tún` or `tunfeste` in prose and
   never bare `tun` as a search term, so the network-device collision stays
   harmless.
6. **Whether `å tune` survives contact with English readers.** Watch for "tuned
   the numbers" appearing in someone else's sentence, especially in an English or
   mixed-language document; that is the signal to fall back to `tunfeste`.

## Sequence

The brand and the domain are settled and need nothing from anyone else. Adoption
into code, packages and artefacts waited for the ownership answer and the licence.
Both are in place (`17-licensing.md`).

<!-- attribution:start -->
## The old name

Until 2026-09-28 the repository was called `tun`. Old notes, session
logs and clones may still use that name. The forge redirects the old URL, so a push to it
succeeds without a warning. Always resolve the repository by its current name.

## Credit

The name *Tún* was found by en kollega.
<!-- attribution:end -->

## Adopting the name

Formerly `19-name-adoption-plan.md`, folded in here so the name and what it costs to
carry are one document (`ROADMAP.md` B3). The domain, the diacritic and the adoption order
are the same decision seen from three sides.

The brand is Tún and the domain is tun.community (`18-naming.md`). **There is no
rename.** This document is what replaces the rename plan: how the settled name
gets into the code, the artefacts and the registries, in an order where a mistake
stays cheap.

It is built on one rule: **the three things that carry a name cost different
amounts to change, so treat them as three jobs.**

| Thing | Example | Cost to change later |
|---|---|---|
| Display name | the word in a README or on a page | low; one edit |
| Identifier | package, CLI, repository, container | medium; mechanical, touches builds and deploys |
| Public address | `tun.community`, `hei@tun.community` | high; it lives in other people's links, inboxes and downloaded files |

Since the brand and the domain are now fixed, the expensive third column is
already decided. What is left is mostly the middle one.

### Where the name already lives

**The repository is already renamed.** It is `tun` as of 2026-09-17; the old name
resolves only through a GitHub redirect. Step 5 of the sequence below therefore
happened first, which changes what is left to do and creates the two problems in
the next two sections.

**The old name is still in 65 places across 42 tracked files.** Not a rename
backlog in the ordinary sense: most of them are correct history. The ones that
matter are few.

| Where | Count | What it is |
|---|---|---|
| `examples/*/` built artefacts and their build scripts | 38 | provenance lines in committed example output; regenerate, do not hand-edit |
| `docs/04`, `docs/05`, `docs/08`, `docs/14` | 9 | prose; correct when written, now stale |
| `templates/single-file-dashboard.html:20`, `templates/cube-dashboard.html:11` | 2 | **the provenance line every future artefact inherits** |
| `templates/_generic-provenance-block.html:27` | 1 | the shared source of the same block |
| `pyproject.toml:2` | 1 | the package name; a separate decision, see `18-naming.md` |
| `setup.py:74` | 1 | **the install marker; do not touch, see below** |
| `tests/test_skill_links.py`, `README.md` | 2 | one assertion, one prose line |

**In the private testmiljø repository `eksempelgård-penthouse`,** which serves
tun.community: 17 files and about 60 references.

| File in `eksempelgård-penthouse` | References |
|---|---|
| `testserver/stacks/tun-site/README.md` | 12 |
| `testserver/stacks/tun-site/docker-compose.yml` | 9 |
| `testserver/stacks/tun-site/tools/test-poll-deploy.py` | 8 |
| `docs/adr/0028-tun-community-public-hostname.md` | 6 |
| `testserver/stacks/tun-site/web/index.html` | 5 |
| `testserver/stacks/tun-site/poll-deploy.sh` | 5 |
| `cmd/server/main.go`, `tools/verify-preview.py` | 3 each |
| `README.md` (repo root) | 3 |
| remaining files | 1 to 2 each |

Those are all consistent with the decision, so they stay as they are. The
inventory is kept because it is the map of every place the name appears, which is
what you want when checking consistency rather than when renaming.

**In no repository at all,** and therefore easy to forget when something breaks:

- The Cloudflare Zero Trust ingress rule, `tun.community -> http://tun-site:8080`.
- The Cloudflare zone, its DNS records, the DMARC record, and Email Routing with
  the `hei` rule.
- The cron entry on the testserver and its log path
  `/home/jonski/logs/tun-site-deploy.log`.
- Docker image and container names, including the rollback tags.
- The Traefik router labels for LAN preview, `tun-site.${ZIMA_DOMAIN}`.
- The Go module path `github.com/example/tun-site`.

### The part that is irreversible

Every generated artefact carries a provenance block. Today it says:

```
Repo        : tun
```

in `templates/single-file-dashboard.html:20` and
`templates/cube-dashboard.html:11`, with the shared source in
`templates/_generic-provenance-block.html`.

Once the brand lands there, **every artefact sent out carries it permanently.**
Artefacts cannot be recalled or updated. So the footer is the one place to get
right on the first attempt, and it is a reason to adopt the name there *after* the
licence text is settled rather than before: the same block is the natural place
for a one-line licence notice, and changing it twice means two generations of
artefacts disagree.

One trap in that file: `tools/verify_standalone_core.py`'s `check_provenance()`
looks for the literal strings `PROVENANCE`, `Source data` and `Built`. Keep those
three labels when adding the brand, or the verifier fails on every artefact.

### The rename already made that line wrong

Because the repository is now `tun`, `Repo: tun` is not
merely old branding — it is **factually incorrect in every artefact built from
today onwards**, and it points at a name that survives only on a redirect.

That collides with the ordering argument above. Waiting for the licence means
shipping artefacts with a wrong provenance line; fixing it now means the brand
lands in the footer before the licence notice, so two generations of artefacts
differ.

**Correctness wins.** The licence is blocked on an answer with no date, and a
provenance line exists to be true. Change the line to `Repo: tun` now, add the
licence notice when there is one, and accept two generations. A wrong line is a
worse legacy than an incomplete one.

### Do not rename the install marker

`setup.py:74` defines `MARKER = ".installed-by-tun"`. It is
written into every skill directory this project copies into `~/.raiwork/skills/`,
and at `setup.py:97` its presence is the *only* thing that distinguishes "our own
earlier copy, safe to refresh" from "a skill the user already had, leave alone".

Rename that string and every previously installed copy stops being recognised.
`python3 setup.py` will then report *"you already have a skill with this name —
left alone"* and quietly stop refreshing those skills. No error, no failure, just
skills that silently never update again.

If the marker must carry the new name, accept **both** strings as ours and keep the
old one forever, or write the new marker into any directory that has the old one
before the check runs. The safe option is to leave it alone: it is invisible to
users and nothing about it is branding.

Status: done the first way. `setup.py` writes `.installed-by-tun` and keeps the old
string in `LEGACY_MARKERS`, so old installs are still ours. A run replaces the old
marker, and a renamed-away copy that carries only the old one is still cleaned up.
`tests/test_skill_links.py` steps 11 to 13 pin this.

### Sequence

Each step is useful on its own and revertible on its own.

**Step 1 — licence first.** `17-licensing.md`. Applied: AGPL v3 plus the Artefact
Exception. The ownership answer is in
(2026-10-11), so the remaining steps are no longer blocked. It comes first because the artefact footer should gain the brand
and the licence notice in one edit, not two.

**Step 2 — decide the identifier.** `tunfeste`, or a compound that keeps the brand
visible. Register nothing yet; just decide, and write it down in `18-naming.md`.
This is free today and stops being free the moment it reaches a registry.

**Step 3 — adopt in prose.** README, `docs/00-vision.md` and the other docs start
saying Tún. No identifier changes, no artefact changes. Cheap, reversible, and it
is the fastest way to find out whether the word survives being read aloud by
people who have not seen it written.

**Step 4 — correct the artefact footer.** `Repo: tun` in
`templates/_generic-provenance-block.html` and both templates, then regenerate the
committed examples. Do this before the licence rather than with it, because the
current line is wrong rather than merely unbranded. Verify with
`tools/verify_dashboard.py` and `verify_standalone_core.py` before any artefact
built with it is sent anywhere.

**Step 5 — repository identifier: done.** Renamed to `tun` on 2026-09-17, ahead of
this sequence. The package name and CLI are still open and still wait for step 2
and for the trademark checks in `18-naming.md`.

**Step 6 — registries and trademark.** Reserve the identifier where it matters.
This is also the point where the name becomes publicly visible in a way that
cannot be taken back.

### What makes this go wrong

- **Adopting the name in the artefact footer before the licence is settled.** Two
  generations of artefacts then carry different notices, permanently.
- **Registering the identifier before the employer brand question is answered.** That
  is the one open check that can still force a different name, and a reserved
  package name is a public, dated claim.
- **Assuming the brand settles the identifier.** `tun` is taken on npm and means
  tunnel device to every engineer. The brand is unaffected; the identifier is not.
- **Treating tun.community as revisable.** Downloaded artefacts embed it. It has
  to answer permanently.
- **Recreating `tun` under the same account.** That breaks
  the redirect keeping older artefacts' provenance resolvable.
- **Renaming the install marker** in `setup.py`. It fails silently and
  permanently; see above.

### One piece of hygiene, downgraded on purpose

An earlier draft of this plan argued that the hardcoded canonical host in
`eksempelgård-penthouse` (`cmd/server/main.go:112`, defaulted again in
`tools/verify-live.sh`) should be made configurable, because it would turn a
future rename from a code change into a setting.

With the domain decided, that argument is gone. Making it configuration is still
mildly tidier, and it is now small hygiene rather than an unlock. It should not be
scheduled ahead of anything in the sequence above.
