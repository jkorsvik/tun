# AI recipes: make one Tún file with your assistant

**Start with [Install and use Tún](../../INSTALL.md).** On RAIWork, use Marketplace. On Windows, macOS or Linux, use the toolkit ZIP and Python. To open an existing dashboard, just download the HTML and open it in a browser.

All recipes use [the same synthetic CSV](fixtures/excuses.csv) and [the same acceptance checks](common-contract.md). The result is `tun-recipe.html`: four rows, total 10, Traffic total 5. A file preview, an app link, or a code block is not the result. If your assistant cannot run Tún, use the local command and ask the assistant to help with the data or the brief.

[Open or download the reference HTML](fixtures/tun-recipe.html) to try it without installing anything. On GitHub, use the file download control, then open the downloaded file in your browser.

## Choose your tool

These entries describe the route to try, not what every account can do. Edition, permissions and tool settings matter. **Native product runs are not recorded** unless a recipe gives a tool version, OS, date and result. The local toolkit and browser checks below are independent of the assistant.

| Tool | Where to start | Where to verify |
|---|---|---|
| [RAIWork](raiwork.md) | Marketplace plugin; repository fallback | Local browser |
| [Microsoft 365 Copilot Chat](microsoft-365-copilot.md) | Attach the CSV if enabled; build locally | Local toolkit and browser |
| [Copilot in Edge](edge-copilot.md) | Read the project with page context, if allowed | Local toolkit and browser |
| [GitHub Copilot in VS Code](github-copilot-vscode.md) | Open the toolkit; use Agent mode and terminal | Local browser |
| [GitHub Copilot coding agent](github-copilot-coding-agent.md) | Run the task in an authorised repository and review the diff | Runner checks, then local browser |
| [Claude Code](claude-code.md) | Copy the skills; open the toolkit | Local browser |
| [Claude.ai export](claude-artifacts.md) | Use the hosted workspace for drafting or for an unchanged file | Local toolkit and browser |
| [ChatGPT](chatgpt.md) | Attach the CSV; use file output if available | Local toolkit and browser |
| [Codex](codex.md) | Load the skills or use the checked-out repository | Terminal and browser if provisioned |
| [Gemini CLI](gemini-cli.md) | Open the toolkit and check skill discovery | Local browser |
| [Gemini web / Google AI Studio](gemini-web.md) | Attach the fixture where supported; export if available | Local toolkit and browser |
| [Cursor](cursor.md) | Open the toolkit; allow the build command | Local browser |
| [Windsurf](windsurf.md) | Open the toolkit; use Cascade and terminal | Local browser |
| [Cline / Roo Code](cline-roo.md) | Open the toolkit; approve the listed commands | Local browser |
| [JetBrains AI Assistant / Junie](jetbrains.md) | Open the toolkit project and select an agent with terminal access | Local browser |
| [Visual Studio](visual-studio.md) | Use supported Copilot features or the terminal; IntelliCode alone is not a builder | Local browser |

## No AI or no access?

From the toolkit root, run `python3 tools/ai_recipe.py build` (Windows: `py -3 tools/ai_recipe.py build`). Open `work/ai-recipes/tun-recipe.html`. This is the same file the recipes aim to produce. Run `check` and then `browser` as described in [the common contract](common-contract.md).

Tún maintainers own these recipes. When a tool changes, update its source links and record what actually ran. Do not update a test date based on documentation alone.
