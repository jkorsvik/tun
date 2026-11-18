# Install and use Tún

**Just opening a dashboard?** Download the HTML file and open it in your browser. There is nothing to install. A SharePoint or OneDrive preview is not the browser view.

**Building a dashboard?** Choose your route:

| I use… | Start here |
|---|---|
| RAIWork | [Install from Marketplace](#raiwork-marketplace) |
| Claude Code or an assistant that reads Agent Skills | [Get the toolkit and copy the skills](#copy-tun-skills-to-your-assistant) |
| Python only | [Get the toolkit](#get-the-toolkit), then [make your first file](#make-your-first-file) |
| Copilot Chat, ChatGPT, Claude.ai or another web assistant | [Find your recipe](docs/ai-recipes/README.md). A web preview alone is not a Tún file. |

## RAIWork Marketplace

On Windows, macOS or Linux, open **Marketplace**, search for **Tún**, select the plugin, and choose **Install**. Open a new session and ask for `tun-help` or `tun-new`. Use an approved Python 3.12 environment to build. Browser verification also needs pre-provisioned Playwright and matching browser binaries. The plugin does not install these for you.

If your RAIWork CLI is already signed in, the equivalent install command for version 0.1.9 is:

```text
raicode manage marketplace install plugin/tun@0.1.9 --accept=skills
```

Use `raicode manage marketplace list` to check the installed version. If you previously copied Tún skills into `~/.raiwork/skills`, they can take precedence over the plugin. Ask the assistant to show the path of the `SKILL.md` it loaded. A Marketplace copy should be under `~/.raiwork/marketplace/plugins/tun/skills/`. Do not delete personal skills to fix this. Use [the RAIWork recipe](docs/ai-recipes/raiwork.md) to check the route.

## Get the toolkit

1. Open the Tún repository (use the GitHub link on [tun.community](https://tun.community)). Choose **Code → Download ZIP**. Extract the whole ZIP to a folder you can keep. Or follow the [Git clone steps](docs/04-onboarding.md) if you use Git.
2. Open a terminal **in the extracted or cloned folder**, the one that contains `setup.py`. On Windows, use PowerShell. On macOS or Linux, use your usual terminal.
3. Check Python: `py -3 --version` on Windows or `python3 --version` on macOS or Linux. Use Python 3.12 or later for this guide. If it is missing, use the [official Python downloads](https://www.python.org/downloads/) or your approved software catalog. On Linux you can also use your distribution's package manager. If Windows has `python` but not `py`, check `python --version` and use `python` in the commands below.

The toolkit runs from that folder. It does not need Node, a server, an account, or pip packages to build the example. Keep the folder: the builders and templates are in it.

## Copy Tún skills to your assistant

This is optional. Do not use the toolkit script to install the RAIWork Marketplace plugin.

| Assistant | Windows PowerShell | macOS or Linux |
|---|---|---|
| Claude Code | `py -3 setup.py --install --tool claude` | `python3 setup.py --install --tool claude` |
| Codex or another tool that reads `~/.agents/skills` | `py -3 setup.py --install --tool agents` | `python3 setup.py --install --tool agents` |

The script copies only Tún project skills to the folder your selected assistant reads. It does not download anything, need administrator access, set Git hooks, or replace existing paths. Add `--check` to see which files match without writing. Open the toolkit folder in your assistant and start a new session. Ask it to name the `tun-new` skill file before building. For tools with another discovery path, see [your recipe](docs/ai-recipes/README.md); do not assume that every IDE reads `~/.agents/skills`.

**Updating an earlier install?** Run the same command with `--check` first. If a skill differs, the script shows its path and leaves it alone, even if Tún originally installed it. If you own that copy, move it to a backup folder outside the assistant's skills folder, then run the install command again. Keep the backup if it has edits you want to reuse. Do not move a skill managed by another installer. You can still build without installing any skills.

## Make your first file

Run one command in the toolkit folder:

| Windows PowerShell | macOS or Linux |
|---|---|
| `py -3 tools/ai_recipe.py build` | `python3 tools/ai_recipe.py build` |

Open `work/ai-recipes/tun-recipe.html` in your browser. It shows **4 synthetic rows, total 10**. Set the Category filter to **Traffic**. The total should become **5**. Select **Reset** to return to **10**.

To check the generated file, replace `build` with `check`. To run the automated browser check, use [the verification steps](docs/ai-recipes/common-contract.md#verify-before-sharing). Keep auto-generated files out of Git unless you intend to publish them.

**Using an assistant?** Open [the AI recipes](docs/ai-recipes/README.md), pick your tool and copy its prompt. Want to use your own data? Follow [Start here](START-HERE.md). Everyone who can open your file can read all rows in it. Split the input before building files for different audiences.
