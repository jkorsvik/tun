# The reference dashboard

Use the same small file to try Tún in any assistant. [Download the synthetic CSV](fixtures/excuses.csv), or use the copy in the toolkit. There are **4 rows**, the total is **10**, and **Traffic** accounts for **5** across two rows. The numbers are made up. Do not use work data for the trial.

## Build the file

[Get the toolkit](../../INSTALL.md#get-the-toolkit) and open a terminal in its folder. These commands work without an AI account. They run the same builder that the assistant recipes ask for.

| Step | Windows PowerShell | macOS or Linux |
|---|---|---|
| Build | `py -3 tools/ai_recipe.py build` | `python3 tools/ai_recipe.py build` |
| Check the file | `py -3 tools/ai_recipe.py check` | `python3 tools/ai_recipe.py check` |

Open **`work/ai-recipes/tun-recipe.html`**. Building again replaces that example. The file contains its data, styles and code, not a link to an app. Reuse the original HTML if an assistant can return only text or a hosted preview. Do not paste a generated app into the file and call it Tún.

`check` compares the HTML with a fresh build from this toolkit and the shared fixture. It checks the exact content, not just the filename. The provenance block records the source and row count. Both dates are fixed to the synthetic reference time so a fresh build can reproduce the sample. They do not report when you ran the command. A recipe comment records the contract number, fixture digest, and builder-output digest. Keep the toolkit revision with your test record (Git commit or source ZIP reference). To check a download, add its quoted path after `check`, for example `python3 tools/ai_recipe.py check "$HOME/Downloads/tun-recipe.html"`. On PowerShell use `py -3 tools/ai_recipe.py check "$HOME/Downloads/tun-recipe.html"`.

## Verify before sharing

**Built** means the file exists. **Static PASS** means it matches this toolkit's reference build. Neither means the dashboard ran in a browser.

Use an approved Python environment with Playwright and its Chromium browser. If permitted, you can provision these separately with [uv](https://docs.astral.sh/uv/), from the toolkit folder:

```text
uv sync --extra verify
uv run playwright install chromium
```

On Linux, Playwright can also need system libraries. Use your approved package route or ask the environment owner. Do not change device policy to get the browser to run.

Run `uv run --extra verify python tools/ai_recipe.py browser` on Windows, macOS or Linux. With an already provisioned interpreter, use `py -3 tools/ai_recipe.py browser` or `python3 tools/ai_recipe.py browser` as appropriate. To check a downloaded copy, add its path after `browser`.

**Browser PASS** means Chromium opened the exact reference as a local file with the network blocked. It rendered the heading, table and chart. It showed 10, changed to 5 for Traffic, and returned to 10 on Reset. The gate also checks page errors and requests. If the browser is not available, record **browser not verified**. A preview inside an assistant is not this check.

Open the screenshot next to the HTML. Confirm the title and source, check one row against the CSV, and look for cut-off labels. Open the downloaded file in the recipient's browser if it differs from yours.

## Hand off the file

Share the original `.html` file in a folder with the correct audience, or attach it if your policy allows. For OneDrive or SharePoint, tell recipients to download the HTML and open it in a browser. A preview can limit scripts. No server or hosted app is required.

Keep Tún's [Origin Notice](../../COPYING.ARTEFACT-EXCEPTION) in the generated HTML. Do not strip the provenance comment or relabel another generator's work as Tún. Do not add secrets or restricted rows to a prompt, repository, or output. A filter does not protect rows. Split the data before building files for different audiences, and verify folder permissions separately.

## Record what ran

For a platform test, record the tool and edition, version (or observed date for a hosted tool), OS, toolkit revision, and whether the file was built, downloaded, checked and opened. Attach the actual command result or say why it could not run. Vendor documentation is evidence of a supported feature, not a test of this recipe. The Tún maintainers own this contract.

### Refresh the download after a builder change

Run `python3 tools/ai_recipe.py build` (`py -3` on Windows), then replace
`fixtures/tun-recipe.html` in this directory with `work/ai-recipes/tun-recipe.html` from
the toolkit root. Commit the refreshed sample with the builder change. Run the static
check against the committed sample and the browser check against a copy under `work/`.
