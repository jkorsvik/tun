# 21 — Tiers: core, community, third party

**Reader:** contributor — you are changing the toolkit, and need the constraint or the convention behind it.

Status: architecture note, drawn on paper and transcribed here. The tier names are decided;
the plugin contract is not. Nothing is published, and no licence is adopted.

## The sketch

![Hand-drawn architecture sketch: the TÚN core as a sun emitting HTML and CSS onto a waterline
of hosting substrates, with tun.community to one side, a feedback loop returning to the core,
and the incumbent document formats off to the other side.](assets/tun-architecture-sketch.jpeg)

What it says, read left to right:

- **`tun.community`** sits beside the core, with a two-headed arrow. The community both
  consumes and contributes; it is not a downstream audience.
- **The core is a sun labelled "skills" and ".MD"**. That is the whole of it: prompts and
  markdown, not an application. It emits rather than serves.
- **`tilbakemelding`** comes back into the core from a recipient. Feedback is a first-class
  path in the drawing, not an afterthought.
- **`HTML + CSS`** is the single thing the core emits.
- **The box of incumbents** holds Power BI, PPTX, Excel, Word. They sit outside the core,
  reached by an arrow, because the point is to leave them rather than integrate with them.
- **The waterline** carries GCP, SharePoint, Cloudflare, Vercel, Firebase, OneDrive, AWS and
  Azure, with recipients standing on it. The rays of the sun fall across all of them equally:
  the artefact does not know or care which substrate it landed on.
- **`OSS core`** is written across the top.

Two properties of the core follow directly, and they are the ones worth defending:

1. **Substrate-agnostic.** If the artefact behaved differently on SharePoint than on Vercel,
   the rays would not reach the whole waterline.
2. **Brand-agnostic.** Nothing in the drawing names an organisation.

## The three tiers

Modelled on Home Assistant, which solved this problem already: a core that ships, a community
index that anyone can publish into, and custom components that never leave the machine they
were written on.

| Tier | What belongs there | Who maintains it | Ships with core |
|---|---|---|---|
| **core** | the artefact model, the build tooling, the gates and verifiers, the templates, the measured platform physics | this repository | yes |
| **community** | themes, chart packs, locale packs, substrate adapters, anything generally useful | whoever wrote it, indexed by `tun.community` | no, installed |
| **third party** | organisation-specific brand, tenant quirks, internal endpoints | the organisation, privately | no, never published |

## Why this matters more than a tidy-up

There is a Eksempel AS-shaped problem in this repository: trademark artwork in two examples, brand
colours taken from an SSO-gated brandbook, and the employer named in more than half the tracked
files. The obvious response is to scrub it before publishing.

The tier model gives a better answer. That material is not contamination to be removed; it is
**a third-party plugin that was never separated out.** Extracting it is ordinary architecture
work, it can start immediately, it needs no publication decision, and it produces the first
real plugin, which is the thing that proves the contract exists at all.

The difference is in how the boundary is held afterwards. A scrub is a single event and decays
from the next commit onwards. A boundary is enforced continuously: core must not name an
organisation, and a gate can assert that on every commit, the same way the row gates and the
real-data gate already work.

## Evidence from practice: four tools, one shape

Before this document existed, several self-contained HTML tools were built for unrelated
jobs, each on its own, without a shared plan:

| Tool | Job |
|---|---|
| a follow-up engine | activities and contacts in a relationship; one concrete setup was the first proof, the engine takes more |
| a process-diagram engine | visualises any flow or process; replaced two variants that had drifted apart over time |
| a case room | one gathering point per case for a fixed core group: front page, documents, event log, nothing sent around |
| a method and model overview | one shared data set drives two views built for different purposes |

Each one landed, independently, on the same form: **one generic engine, one configurable
first case.** Without that, the same basic tricks (theme, navigation, how to prove a file is
safe to send) get reinvented per tool, a little differently each time, and the tools become
harder to maintain together. The two process-diagram variants that drifted apart are that
failure, observed rather than predicted.

The lesson is not "build everything alike". It is: research the tenant physics and the
painful tricks **once**, in core, and let every new tool inherit the answer instead of
rediscovering it. That is the core tier above, arrived at from the bottom up.

## What a plugin has to be able to do

Derived from the Eksempel AS case, which is the only real one we have. Each item is a requirement the
contract must satisfy, not a design:

- **supply brand tokens**, replacing the palette and typography a template reads at build time
- **supply assets**, including a logo, without core holding any copy of them
- **override or extend templates**, so a branded topbar is a plugin concern rather than an
  example in core
- **extend verification**, so an organisation can assert its own rules, for example that its
  logo is never placed on a disallowed background
- **declare tenant facts**, since the measured constraints in `docs/01` are partly about
  Microsoft 365 generally and partly about how one tenant is configured

Open: whether a plugin may add skills, how versioning and compatibility are expressed, and
whether substrate adapters are plugins or core. The existing `plugin/manifest.json` is a
raicode packaging manifest for this repository as a single unit, named after the organisation
and licensed `Internal`; it conflates core with the Eksempel AS plugin and will have to split.

## Decided: Tún's own skills ship as a plugin

Today the product skills are installed by symlinking them into the user's global skill
folder (`setup.py`). That is backwards:

- **They are visible where they cannot work.** The skills point at repo-local paths
  (`tools/`, `templates/`), but a global install shows them in every session, in every
  project.
- **They are missing where they can work.** A new colleague who clones the repo gets no
  skills until they run the installer.

Decision: all of Tún's skills ship as one standalone, cross-platform plugin, not through a
personal dotfiles repository. The plugin replaces the symlink installer. Until it exists,
`setup.py` stays, and the dev skills (`skills/dev/`) stay project-agnostic.

## Consequence for publication

`docs/20-publication-readiness.md` describes categories to clean before publishing. The tier
model reduces the largest of them: once the Eksempel AS plugin is extracted, most of what category 2
lists has moved out of core by construction rather than by editing.

The personal-data vector in `docs/20` is unaffected and stays what it is: a private-only
exposure in the internal repository's pull-request refs, which never travels because the public
repository will not inherit this history.
