# 28. Prior art, and what Tún takes from it

**Reader:** record — a decision or a measurement, kept for why something is the way it is.

> **Status:** researched 2026-10-08. Four research agents searched the web in parallel,
> one per area below. Then a script fetched every page they cited and kept a claim only if
> its quote was on that page. Of 146 claims, **79 quotes were word for word, 35 were
> stitched** (each fragment of the quote is on the page, but the agent joined them), and
> **32 were dropped**. The harness paths in the first section were read directly from each
> tool's own documentation. Every quote on this page was checked against its page by a
> script on the same day. Ideas are taken, never code: several projects below have
> licences that do not combine with AGPL, and nothing here needs their code.

## The best, in one screen

1. **Tún is already a plugin for most AI tools.** Its skills are in the open Agent Skills
   format. `python3 setup.py --tool agents` or `--tool claude` installs them where other
   tools look. Tested: Gemini CLI and Claude Code load every skill. Codex reads the same
   folder as Gemini CLI, checked in its source.
2. **Strict tools need strict YAML.** Four of our twelve skills were invalid for them.
   Fixed, and a gate keeps it fixed.
3. **Next, if measured to work:** a `<meta>` CSP, so the browser enforces "loads nothing".
4. **Modern HTML does more with no script:** `<details name>`, `popover` and `:has()`.
   Each needs a test in the SharePoint preview first.
5. **The design holds.** Others build ahead of time and ship one file too. Nobody found here
   ships a dense cube inside the file. Everyone who scales needs a server.

The rest of this page is the evidence.

## One skill format, many harnesses

This is the most important finding. **The open Agent Skills format is the plugin
format.** A Tún skill is already a folder with a `SKILL.md`. The format's client
showcase lists 46 products under the heading "Agent products that support the Agent
Skills format." ([agentskills.io/clients](https://agentskills.io/clients)). Among them:
Claude Code, ChatGPT & Codex, Gemini CLI, Cursor, GitHub Copilot, VS Code, Goose,
OpenCode, Amp, Junie, Kiro, Snowflake Cortex Code and Databricks Genie Code.

The format asks for little. From the [specification](https://agentskills.io/specification):

| Field | Rule (quoted) |
|---|---|
| `name` | "Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen." It must also match the folder name. |
| `description` | "Max 1024 characters. Non-empty. Describes what the skill does and when to use it." |
| `compatibility` | "Max 500 characters. Indicates environment requirements (intended product, system packages, network access, etc.)." |
| `metadata` | "Arbitrary key-value mapping for additional metadata (a map from string keys to string values)." |

The harnesses look for skill folders in a few places. Each row is quoted from that tool's
own page:

| Folder in the home directory | Read by |
|---|---|
| `~/.agents/skills/` | [Codex](https://github.com/openai/codex/blob/rust-v0.148.0/codex-rs/ext/skills/src/host_roots.rs) (source, lines 102 to 106: `home_dir.join(AGENTS_DIR_NAME).join(SKILLS_DIR_NAME)`), [Gemini CLI](https://geminicli.com/docs/cli/skills/) ("Located in ~/.gemini/skills/ or the ~/.agents/skills/ alias"), [GitHub Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) ("~/.copilot/skills or ~/.agents/skills"), [VS Code](https://code.visualstudio.com/docs/copilot/customization/agent-skills), [OpenCode](https://github.com/sst/opencode/blob/dev/packages/web/src/content/docs/skills.mdx) |
| `~/.claude/skills/` | [Claude Code](https://code.claude.com/docs/en/skills) ("~/.claude/skills/<skill-name>/SKILL.md"), VS Code ("~/.copilot/skills/ , ~/.claude/skills/ , ~/.agents/skills/"), OpenCode |

Codex's docs page refused a plain request, so its folder was read from its source code at
the installed version (0.148.0) instead. Cursor is in the showcase, but its page
renders with script, so its folder is **not verified** here.

**Tested, not just read.** On 2026-10-08, `setup.py --tool agents` into a throwaway home,
then `gemini skills list` (Gemini CLI 0.34.0): all twelve skills discovered and enabled.
The same folders as a project's `.claude/skills/`, then `claude -p` asked for its `tun-`
skills: all nine named. Codex was not run: its gateway key had expired, which does not
affect installing.

**What we found in our own skills.** The reference validator
([skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref)) parses the
frontmatter as strict YAML. **Four of our twelve skills failed it.** Three had an
unquoted `: ` inside the description, which strict YAML reads as a second mapping. One had
a flow list (`[a, b]`) in `metadata`. RAIWork's loader is lenient, so we never saw it. A
strict harness drops such a skill without a word. Our own first check missed it too,
because it was a lenient regex. The reference validator found it.

This change fixes all four (one double-quoted line each, and strings in `metadata`). All
twelve now pass `skills-ref validate`. A stdlib gate in the pre-commit hook,
[`tests/test_skill_frontmatter.py`](../tests/test_skill_frontmatter.py), now catches the
same class of fault. It refuses block scafagfelle (`>-`) too, because RAIWork shows them
literally. Its `--mutation-check` deletes each of its 19 rules in turn, and the self-test
notices all 19. On the first run, 7 of the 19 could be deleted unnoticed.

What this means for "installable in every good tool":

- **No new package format is needed.** The canonical form stays `skills/<name>/SKILL.md`.
  Installing into a harness means copying the folder into one of the two homes above.
  `setup.py --tool agents` and `--tool claude` now do that, with the same copy, marker and
  never-touch-your-own-skill rules as the RAIWork install. VS Code and OpenCode read both
  folders, so install only one for them, or they list each skill twice. Codex reads
  `~/.agents/skills/`, so `--tool agents` covers it.
- **An MCP server is not the distribution channel for skills.** One research agent
  proposed wrapping the skills as an MCP server, and others proposed a `package.json` or a
  VS Code extension. The harnesses read skill folders directly, so those layers add work
  and give nothing. MCP stays the right tool for a *tool* (a build or verify command a
  harness can call), if one is ever needed.
- **`compatibility` is the honest place to say what a skill needs:** Python 3, `uv`, and
  Playwright for verification.

## Portable data artefacts

Most of this area confirms Tún's design rather than changing it.

| Project | What it confirms or teaches | Quote |
|---|---|---|
| [Quarto](https://quarto.org/docs/output-formats/html-basics.html) (GPL-2.0) | Self-contained HTML through `data:` URIs is an established pattern | "The resulting file should be self contained, in the sense that it needs no external files and no net access to be displayed properly by a browser." |
| [Plotly](https://plotly.com/python/interactive-html-export/) (MIT) | One-file interactive export, shared by e-mail, is ordinary | "By default, the resulting HTML file is a fully self-contained HTML file which can be uploaded to a web server or shared via email or other file-sharing mechanisms." |
| [Observable Framework](https://github.com/observablehq/framework) (ISC) | Precomputing at build time is the same move as Tún's builders and cube | "Framework features data loaders that precompute static snapshots of data at build time for dashboards that load instantly." |
| [Evidence](https://evidence.dev/) (MIT) | Readers of reports also want the numbers as a workbook | "Every report can be exported to PDF or multi-tabbed XLSX workbooks." |
| [Datasette Lite](https://github.com/simonw/datasette-lite) (Apache-2.0) | A database in the browser needs an HTTP origin, which a downloaded file does not have (`docs/02` tier 3) | "You can use this tool to open any SQLite database file that is hosted online and served with a `access-control-allow-origin: *` CORS header." |
| [marimo](https://docs.marimo.io/guides/wasm/), [Mosaic](https://github.com/uwdata/mosaic), Perspective | WebAssembly engines are for a hosted page, not for a file opened from disk | Mosaic: "An extensible architecture for linking data visualizations, tables, input widgets, and other data-driven components, leveraging a backing database for scalable processing" |
| [SingleFile](https://github.com/gildas-lormeau/SingleFile) (AGPL-3.0) | Saving any page as one file, readable without script, is a mature tool. Useful to turn a hosted page into a portable snapshot | "SingleFile helps you to save a complete web page into a single HTML file." |

**Take:** a "download the numbers" button that writes CSV beside the dashboard, built from
the data already in the file. None of the projects found here ships a fixed, dense cube
inside one file. Those that scale ship rows and a query engine, which needs a hosted page.

## No framework, CSS first

| Source | What it offers Tún | Quote |
|---|---|---|
| [HTML First](https://html-first.com/) | The same stance as Tún, with a name others know | "HTML First is a style of writing web software that favours using the native capabilities and languages of the browser and reducing layers of abstraction" |
| [`<details name>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/details) | Native exclusive panels with no script, for lens texts and FAQ-like lists | "This attribute enables multiple <details> elements to be connected, with only one open at a time. This allows developers to easily create UI features such as accordions without scripting" |
| [`:has()`](https://developer.mozilla.org/en-US/docs/Web/CSS/:has) | Lets state live next to what it changes, instead of hidden inputs placed first | "It's been available across browsers since December 2023" |
| [`popover`](https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/popover) | Info bubbles with no script, through `popovertarget` | "Since April 2024, this feature works across the latest devices and browser versions" |
| [`<dialog>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog) | A native dialog when JS is used anyway | "It's been available across browsers since March 2022" |
| [Scroll-driven animations](https://developer.mozilla.org/en-US/docs/Web/CSS/scroll-timeline) | Not yet | "This feature is not Baseline because it does not work in some of the most widely-used browsers" |
| [Utopia](https://utopia.fyi/) | Fluid type and space with `clamp()`, fewer breakpoints | "Instead of tightening our grip by loading up on breakpoints, we can let go, embracing the ebb and flow with a more fluid and systematic approach" |
| [Explorable Explanations](https://worrydream.com/ExplorableExplanations/) | The living idea picture is one. The next step is text and picture linked, so a word lights its part | "Explorable Explanations is my umbrella project for ideas that enable and encourage truly active reading." |
| [Distill's hiatus](https://distill.pub/2021/distill-hiatus/) | A volunteer publication burns out on process, not on content. tun.community should stay a page, not become a journal | "Running Distill as a journal creates a great deal of structural friction, making it hard for us to focus on the aspects of scientific publishing we're most excited about." |

**Take, after measuring:** `<details name>`, `popover` and `:has()` each need one
constraints row (`docs/01`) before a template uses them. The open question is the
SharePoint inline preview, a sandboxed frame (row 28) that already breaks `:target`
(row 24). The radio pattern stays the default until then.

Not taken: classless CSS kits (Pico, Water.css, MVP.css) and Open Props, because Tún has its
own token contract (`docs/22`). htmx, because it is built around HTTP requests and a file
opened from disk has no server.

## Sharing, provenance and verification

| Source | What it offers Tún | Quote |
|---|---|---|
| [Reproducible Builds](https://reproducible-builds.org/docs/source-date-epoch/) | The convention for a fixed build date. On `main` only the process-diagram builder honours it; the rest should | "SOURCE_DATE_EPOCH is a standardised environment variable that distributions can set centrally and have build tools consume this in order to produce reproducible output." |
| [axe-core](https://github.com/dequelabs/axe-core) (MPL-2.0) | An accessibility engine to run inside the existing Playwright verifiers, as a dev-time tool only | "Axe is an accessibility testing engine for websites and other HTML-based user interfaces." |
| [Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP) | A `<meta>` policy would make "loads nothing from anywhere" a rule the browser enforces. A policy that allows no script would also have blocked the decoder script an edge network once injected into tun.community | "Content Security Policy (CSP) is a feature that helps to prevent or minimize the risk of certain types of security threats." |
| [PIT](https://pitest.org/) | The name and the method for what Tún already does to its gates | "Faults (or mutations) are automatically seeded into your code, then your tests are run. If your tests fail then the mutation is killed, if your tests pass then the mutation lived." |
| [W3C PROV](https://www.w3.org/TR/prov-overview/) | Vocabulary for the provenance block (entity, activity, agent), without changing its format | "Provenance is information about entities, activities, and people involved in producing a piece of data or thing, which can be used to form assessments about its quality, reliability or trustworthiness" |
| [Mark of the Web](https://en.wikipedia.org/wiki/Mark_of_the_Web) | Windows tags every downloaded file. Row 28 tells preview readers to download the file and open it from disk, so this needs a measurement on a Windows PC | "The Mark of the Web (MoTW) is a metadata identifier used by Microsoft Windows to mark files downloaded from the Internet as potentially unsafe." |

Not taken: provenance as JSON-LD in a `<script type="application/ld+json">` element. It
would put a script element in pages that promise none, and the comment block already
carries the facts. C2PA content credentials, because they are built for images and video.

**A gap, not a contradiction:** the agent found no Microsoft documentation of how
SharePoint, OneDrive or Outlook handle `.html` files. It reports that the pages it tried
returned 404. The
measured rows in `docs/01` remain the only evidence, which is why they exist.

## The harvest, ranked by value for effort

| # | Take | Effort | State |
|---|---|---|---|
| 1 | Strict, spec-valid skill frontmatter, with a gate and a mutation check | S | **done in this change** |
| 2 | `setup.py --tool agents/claude` installs into the shared folders, and the README says which tool reads which | S | **done in this change** |
| 3 | A `compatibility` line in each `SKILL.md` | S | next |
| 4 | Every builder honours `SOURCE_DATE_EPOCH`, with a build-twice-and-compare test | S | next |
| 5 | Measure `<meta>` CSP from `file://` and in the SharePoint preview, then add it to the templates | S then M | measure first |
| 6 | Measure `<details name>`, `popover` and `:has()` in the SharePoint preview (one row each) | S each | measure first |
| 7 | axe-core in the Playwright verifiers | M | later |
| 8 | A CSV download built from the data already in the file | M | later |
| 9 | Text and picture linked in the living idea picture | M | later |
| 10 | Mark of the Web: open a downloaded artefact on a Windows PC | S | open question |

## Method and its limits

- Four research agents, one per area, each told to quote word for word and warned that
  every quote would be checked. The gate script fetched 82 pages and normalised whitespace,
  entities and typography before it compared. "Stitched" means each fragment of 20 or more
  characters is on the page; the agent joined real sentences. Dropped quotes were
  paraphrases or sentences not on the page. Projects left with no surviving claim are
  not on this page: stlite, Bokeh, TiddlyWiki, Kepler.gl, Frictionless Data Package,
  Stryker, pa11y and html-validate.
- The agents' own summaries were not used as evidence. One said the Agent Skills spec was
  "finalized ~Aug 2026", and no page says so. Another recommended Apache-2.0 for Tún, which
  `docs/17` already decided otherwise.
- A page can change after it was read. The dates in the quotes are the pages' own.
