# 21 — Tiers: core, community, third party

Status: architecture note, drawn on paper and transcribed here. The tier names are decided;
the plugin contract is a proposal. The licence is decided; see `docs/17-licensing.md`.

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

Picture a toolkit grown inside one organisation, with that organisation's brand and
specifics spread through it. The obvious response is to scrub it before publishing.

The tier model gives a better answer. That material is not contamination to be removed; it is
**a third-party plugin that was never separated out.** Extracting it is ordinary architecture
work, it can start immediately, it needs no publication decision, and it produces the first
real plugin, which is the thing that proves the contract exists at all.

The difference is in how the boundary is held afterwards. A scrub is a single event and decays
from the next commit onwards. A boundary is enforced continuously: core must not name an
organisation, and a gate can assert that on every commit, the same way the row gates and the
real-data gate already work.

## What a plugin has to be able to do

Derived from the Eksempel AS example plugin. Each item is a requirement the
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
raicode packaging manifest for this repository as a single unit; it conflates core with
the Eksempel plugin and will have to split.

## Consequence for publication

Real cases stay local and never enter git; only method, scripts, templates and tests on
synthetic data belong here. The tier model helps here too: once the Eksempel plugin is
extracted, most organisation-specific material has moved out of core by construction rather
than by editing.
