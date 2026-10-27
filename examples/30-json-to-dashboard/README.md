# 30. The file you get from an API is not the file the builder reads

A dashboard starts from a flat table. Most systems hand you something else: a JSON endpoint
with a wrapper object, nesting, and a field that is a list. The gap between the two is a
flattener of about fifteen lines, and this example is that gap, on purpose, so nobody
concludes the builder needs a rewrite to read JSON.

`ordrer.json` is the response as it arrives (27 records, 3 363 390 NOK). `flatten.py` turns
it into `salg.csv`, the five columns a dashboard needs. `ordrer.html` is built from that CSV.

## The two decisions the flattener makes out loud

- **`booked` becomes `Maaned`.** The builder's time column is what you group by; a full date
  is fine as a value, but months are what this reader compares. The cut is `[:7]`, in the open.
- **`lines` is taken as one element per order.** That holds for this data and is asserted,
  not assumed: an order with two lines stops the script with its id rather than silently
  dropping revenue. If your data has many lines per order, the flattener emits one row per
  line and the totals still add up, because a dashboard that sums a flat table does not care
  how the rows were produced.

## Prove it

```bash
cd examples/30-json-to-dashboard
python3 generate_data.py      # identical bytes every run
python3 flatten.py            # salg.csv, with the row count and the sum printed
python3 ../../tools/verify_dashboard.py ordrer.html
```

`tests/test_json_to_dashboard.py` re-derives both numbers from the JSON and reads them back
out of the built page, so a stale CSV or a hand-edited HTML fails the suite rather than
looking plausible. It also proves the one-line-per-order assertion bites: give a record two
lines and `flatten.py` must stop.

## Limits

- This is a flattener, not an integration. Nothing here re-extracts; a refresh means running
  the two scripts again (see `tun-data`).
- `page` and `pageSize` in the payload are ignored: this example reads one page. A paginated
  endpoint needs a loop around the record fetch, which is the API's problem, not the
  builder's.
- Synthetic data. No customer, order or amount here came from a real system.
