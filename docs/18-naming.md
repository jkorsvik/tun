# 18. Naming — decided, with one part still open

**Decided:** the brand is **Tún**. The domain is **tun.community**. Both are
settled and this document records them rather than arguing them.

**Also decided:** the repository identifier is `tun`.

**Still open:** the package name on PyPI and npm, and the CLI name. The repository
name does not settle those, because `tun` is already taken on npm, and because
the collision described below is worse for a package than for a repository.

## The three words and their jobs

| Word | Job | Status |
|---|---|---|
| `Tún` | the noun; the enclosed place where the farm gathers, where resources are put and knowledge is shared | **Adopted as the brand.** Found by the person credited at the foot of this page |
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

`tun` is the name of the virtual network device on Unix systems. macOS, for
example, names its tunnel interfaces `utun0`, `utun1` and so on. For anyone technical,
`tun` reads as tunnel interface first.

Registry state when last checked:

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

## `å tune` works as a verb and fails as a name

As a Norwegian verb it is good: short, regular to conjugate (*tuner, tunet*), and
it names the act rather than the tool. A verb people reach for on their own is the
strongest thing a brand can have, and it is why both verbs are kept.

As a **name** it fails on every test that matters, and for reasons that have
nothing to do with Norwegian:

- Written down it is spelled exactly like the ordinary English word. An ordinary
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
of artefacts ships.

## Still to check, now that the name is chosen

1. **Trademark:** Patentstyret for Norway, EUIPO for the EU, in the relevant
   classes. A domain, a repository name and a free package name prove nothing
   about trademark.
2. **crates.io** and any other registry that matters, checked properly rather
   than through a request that returns 403.
3. **GitHub organisation name** availability, if the project moves off a personal account.
4. **Searchability mitigation:** decide to write `Tún` or `tunfeste` in prose and
   never bare `tun` as a search term, so the network-device collision stays
   harmless.
5. **Whether `å tune` survives contact with English readers.** Watch for "tuned
   the numbers" appearing in someone else's sentence, especially in an English or
   mixed-language document; that is the signal to fall back to `tunfeste`.

## Sequence

The brand and the domain are settled and need nothing from anyone else. Adoption
into packages and the CLI waits on the package-name decision above.

<!-- attribution:start -->
## Credit

The name *Tún* was found by the product owner.
<!-- attribution:end -->
