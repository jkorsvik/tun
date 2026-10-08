# The Portable Cube — how Tier 1 stopped caring about row count

**Status:** measured end to end. Every number below came from a run,
not an estimate. Reproduce with `examples/03-cube-dashboard/`.

---

## The problem this solves

Tier 1 ships a single self-contained `.html` file. Its ceiling was always the same:
**how many rows can you inline before the file becomes absurd?** The old budget in
[`02-architecture.md`](02-architecture.md) said stop at 500 000 rows / 50 MB and
escalate to Tier 3.

But Tier 3 turned out to be unreachable from a portable file
(see [the constraints doc](01-tenant-constraints.md#why-duckdb-wasm-cannot-run-from-a-file-page)):
DuckDB-WASM cannot boot from a `file://` page at all. So "escalate to Tier 3" meant
"escalate to a tier that needs an SPFx admin approval". For most work that is the
same as "no".

The way out was to stop shipping rows.

---

## The idea

A dashboard never shows 4 million rows. It shows **aggregates at the grain of its own
filters**. If the dashboard can filter on region, category, channel, age band and
month, then the *only* numbers it can ever display are sums over combinations of
those five things.

So ship exactly that: one cell per combination. A cube.

```
  4 000 000 rows                        115 200 cells
  ──────────────                        ─────────────
  region  kategori  kanal  …  belop     region × kategori × kanal × alder × måned
  Oslo    Sport     Nett   …  433.15      10   ×    12    ×   5   ×   6   ×  32
  Viken   Mat       Butikk …  128.90
  Oslo    Sport     Nett   …  902.00    each cell: sum(belop), sum(antall), count
  … 4 000 000 more                      → answers ANY filter combination exactly
```

The cube is **exact**, not sampled, for additive measures. Any slice, dice, drill or
roll-up the UI offers is a sum over a subset of cells, and gives the same answer as
scanning the raw rows.

Row count stops being the constraint. **Dimension cardinality** becomes the
constraint, and that is a design choice you control.

---

## Why it gets small: three compounding tricks

### 1. Positional encoding — no keys at all

The cube is stored **dense**, in canonical dimension order. A cell's position *is*
its coordinate, so nothing identifies it:

```
i = ((((r · 12 + k) · 5 + c) · 6 + a) · 32 + m)
```

Naive JSON with keys would have been **14.9 MB** for the same 115 200 cells. The
dense form carries zero key bytes.

Empty cells cost 4 bytes of zeros each, and zeros are what gzip is best at, so a
sparse dataset does not blow up — it just compresses harder. Density is reported at
build time.

### 2. Exact integer narrowing

Each measure is scaled to the smallest factor (1, 10, 100) that makes every cell an
exact integer inside `int32`, and that factor is recorded in the metadata. Money
becomes øre; the browser divides on read. Measured, on the same cube:

| encoding | raw | gzip | base64 |
|---|---|---|---|
| float64 | 1.84 MB | 0.81 MB | 1.08 MB |
| float32 | 1.38 MB | 0.61 MB | 0.82 MB |
| **int32, scaled** | **1.38 MB** | **0.51 MB** | **0.67 MB** |

Integers beat float32 on size *and* are exact. If no scale fits, the builder falls
back to float64 rather than silently losing precision.

### 3. Native gzip — no library

The payload is gzipped at build time and inflated in the browser by
**`DecompressionStream("gzip")`**, which is built into the platform. No bundler, no
inflate library, nothing added to the file.

The gzip header is fixed (mtime 0, OS byte 255), so the same data gives the same bytes on
any Python build. `tests/test_cube_reproducible.py` holds that.

This is the load-bearing detail, and it is verified to work from a `file://` page:

```
DecompressionStream finnes: true
komprimert: 14000 → 63 bytes
base64→gunzip fungerer: true
```

That matters because *every other way of getting bytes into a `file://` page is
blocked* — `fetch`, `new Worker`, and dynamic `import()` all fail against
origin `null`. An inline `<script>` block plus a native decompressor is the one
channel that survives.

---

## Measured result

4 000 000 rows of mock transaction data; 5 dimensions; 2 measures plus a row count.

| | |
|---|---|
| source rows | 4 000 000 |
| cube cells | 115 200 (100 % populated) |
| cube raw | 1.38 MB |
| gzipped | 0.60 MB |
| base64 inlined | 0.80 MB |
| **finished `.html`** | **0.81 MB** |
| build time | 21.7 s (stdlib Python, no dependencies) |

In the browser, opened from `file://`:

| | |
|---|---|
| base64 decode | 24 ms |
| gunzip | 16 ms |
| first full roll-up (all 115 200 cells) | 12.6 ms |
| **each filter click** | **0.00 – 1.30 ms** (median 0.10 ms) |

Correctness against DuckDB on the raw Parquet:

| measure | raw data | cube | delta |
|---|---|---|---|
| `sum(antall)` | 7 996 784 | 7 996 784 | exact |
| `count(*)` | 4 000 000 | 4 000 000 | exact |
| `sum(belop)` | 3 426 028 794.16 | 3 426 028 794.24 | 0.08 kr on 3.4 bn |

The 0.08 kr comes from the *source* Parquet storing `belop` as float32; the cube
itself is exact to the øre by construction.

**A 0.8 MB file, openable by anyone, that answers any question about 4 million rows
in under a millisecond, with no server, no licence and no approval.**

---

## What it cannot do

Be honest about this with stakeholders; the cube trades flexibility for portability.

- **No new dimensions after build.** You can only filter and group by what was
  compiled in. A question the cube was not built for needs a rebuild.
- **No row-level detail.** There is no "show me the underlying transactions" drill.
  The rows are gone. If a viewer needs to see individual records, this is the wrong
  tool.
- **Additive measures only.** `sum` and `count` compose over cells. `avg` is derived
  as `sum / count` in the browser, which is correct. **Distinct counts and medians do
  not compose** and the builder rejects them rather than producing a plausible lie.
- **Cardinality is the budget.** The cell count is the product of all dimension
  cardinalities, so it explodes fast. A daily grain over 3 years pushed the same
  cube from 115 200 to 3.5 million cells and hit the guard. Coarsen the grain or drop
  a dimension.
- **Still no row-level security.** Unchanged, and non-negotiable: if the answer
  depends on *who is looking*, this is a Power BI job. See
  [`00-vision.md`](00-vision.md).

---

## When to reach for it

| Situation | Tool |
|---|---|
| < 10 000 rows, viewer may want row detail | `tools/build_dashboard.py` (inline the rows) |
| Many rows, fixed set of filters, aggregates only | **`tools/build_cube_dashboard.py`** |
| Cube would exceed ~2 M cells | coarsen a dimension first; then reconsider |
| Needs live data, or row detail over a huge table | Tier 2 + Tier 3 (SPFx, admin approval) |
| Answer depends on the viewer's identity | Power BI. Always. |

---

## Usage

```bash
python3 tools/build_cube_dashboard.py \
    --data transaksjoner.csv \
    --dims region,kategori,kanal,aldersgruppe \
    --time dato --time-grain month \
    --measures "belop:sum:kr,antall:sum" \
    --title "Transaksjonsoversikt 2024–2026" \
    --requested-by "Analyseteamet" \
    --out dashboards/transaksjoner.html

python3 tools/verify_dashboard.py dashboards/transaksjoner.html
```

Stdlib only, like the rest of `tools/`. Input is `.csv`, `.tsv` or `.json`; convert
`.xlsx` or Parquet first with the `tun-data` skill.

The builder refuses to produce something misleading: it errors on a non-additive
measure, on an unknown column, and on a cube above `--max-cells` (default 2 000 000,
which bounds the browser's decoded footprint at ~24 MB). It warns when the cube is
not actually smaller than the source data, which means you should be inlining rows
instead.

---

## The wire format

`tools/build_cube_dashboard.py` and `templates/cube-dashboard.html` must agree byte
for byte. If you change one, change both.

```
<script id="cube" type="application/gzip;base64">   base64( gzip( payload ) )

payload = measure₀ ‖ measure₁ ‖ … ‖ count
          each exactly n_cells long, in canonical dimension order
          measure dtype "i" → int32 (divide by meta.scale on read)
                        "d" → float64
          count           → uint32
```

Dimension names, labels, shape, scales and dtypes travel in the `META` object beside
it. The browser reconstructs typed-array views directly over the inflated buffer with
no copy — except for a `float64` measure landing on a non-8-byte offset, which is
sliced instead, because `Float64Array` requires 8-byte alignment and a misaligned view
throws.

Strides are derived, never stored:

```js
STRIDE[last] = 1;  STRIDE[i] = STRIDE[i+1] * shape[i+1]
```
