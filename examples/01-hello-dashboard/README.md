# 01. The default dashboard end to end

The one to read first. A CSV of sales, four filters, two charts, a sortable table, and the
provenance block that lets a reader trace every number back to the file it came from.

This is the shape a request turns into when nobody asks for anything special: pick a
dimension, a measure and a time column, and the builder decides the rest.

## Build it

```bash
python3 tools/build_dashboard.py \
  --data examples/01-hello-dashboard/salgsdata.csv \
  --title "Salg per region og produkt 2026" \
  --dimension Produkt --measure Belop --time Maaned \
  --filters Region,Produkt,Kanal \
  --source "Eksempeldata (syntetisk) — salgsdata.csv" \
  --requested-by "Prosjekteier" \
  --out examples/01-hello-dashboard/salg-dashboard.html
```

`--source` and `--requested-by` are part of the command, not garnish: without them the build
silently rewrites the block a reader audits.
