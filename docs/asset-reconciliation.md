**Duplicate asset reconciliation**

**Why this exists**
This is based on a real cleanup job — reconciling several hundred duplicate
device records between LegacyCMDB (the legacy asset-management tool) and Intune. The two
systems drifted apart for boring, predictable reasons: a device got
re-imaged or re-enrolled and picked up a new LegacyCMDB asset ID while keeping
the same physical serial number, or someone typed the device name
differently between the two systems (`LAPTOP-JS4021` vs `laptop-js4021` vs
`Laptop_JS4021`). At a few hundred records this is technically doable by
eye in a spreadsheet, but it's slow and it misses anything that isn't
sitting next to its duplicate alphabetically once sorted.

The original version of this ran against a real LegacyCMDB export and a real
Intune device list. That data doesn't leave the work laptop it came from, so
what's in this repo is a rebuild of the same logic against synthetic data —
see the honesty note at the bottom before treating the sample output as a
real result.

**What's here**
- `scripts/asset_reconciliation.py` — the reconciliation script
- `scripts/sample_device_records.csv` — 41 synthetic device records with
  duplicates seeded in on purpose (see below)
- `scripts/sample_reconciliation_report.csv` — the report the script
  produces when run against that sample file, checked in so you can see the
  output without running anything

**How the matching works**
The script reads a single CSV containing rows from both sources (columns:
`asset_id`, `source`, `device_name`, `serial_number`, `last_check_in`) and
groups rows it thinks are the same physical device, in three passes, each
progressively less certain:

1. **Exact serial number match** (normalized — case and whitespace/dashes
   stripped before comparing). This is the strong signal: a serial number
   is supposed to be unique to one physical device, so two rows sharing one
   are almost certainly the same machine under two asset records, no matter
   what the device name says. Flagged **high confidence**.
2. **Exact normalized device name match**, for rows that didn't already
   match on serial. Names are lowercased and have whitespace/underscores/
   dashes collapsed out, so `IT-DT-0099` and `IT DT 0099` match. Weaker
   signal than a serial match — device names get reused and reassigned in
   ways serial numbers shouldn't — so this is **medium confidence**.
3. **Fuzzy name similarity**, using `difflib.SequenceMatcher` on the
   normalized names, for anything still unmatched. Catches things like a
   typo'd or truncated device name (`ENG-LT-5502` vs `ENG-LT-550`) that
   isn't an exact match after normalization but is clearly close. This is
   **low confidence** and the threshold (0.82) is a starting point, not a
   tuned value — I picked it by checking it caught the seeded near-matches
   in the sample data without also matching the genuinely unrelated names,
   nothing more rigorous than that.

For every group found, the script also suggests a canonical record to keep:
whichever row has the most recent `last_check_in`, with source as a
tiebreaker (Intune over LegacyCMDB, on the assumption that Intune's check-in
timestamp tends to be fresher than a manually-updated CMDB field). That's a
starting suggestion for whoever does the actual merge, not a rule to trust
blindly — see limitations below.

**The sample data**
`scripts/sample_device_records.csv` is entirely made up — fake serial
numbers, fake device names, no real hostnames or asset IDs from any real
environment. It has 41 rows: 8 seeded duplicate groups (4 exact-serial, 2
exact-name-variant, 2 fuzzy-name) covering pairs and one 3-record group, plus
24 rows that are genuinely unique devices with no duplicate — negative
examples, so the report isn't just "everything gets flagged."

Running the script against it:
```
Input records: 41
Duplicate groups found: 8
Records flagged as part of a duplicate group: 17
Records with no likely duplicate: 24
After reconciliation (one canonical record kept per group): 32 record(s) would remain

  high confidence groups: 4
  medium confidence groups: 2
  low confidence groups: 2
```
Every seeded duplicate got flagged, and none of the 24 unique negative
records got pulled into a group. I checked this by hand against what I
seeded, which is straightforward at 41 rows — it's not the same thing as
validating the logic against the messiness of a real few-hundred-row export,
which will have edge cases this sample doesn't (see below).

**Limitations — read this before merging anything**
- **False-positive merge risk is real, especially at "low" confidence.**
  Two genuinely different devices can have similar names by coincidence —
  think sequential asset tags (`ENG-LT-5502` and `ENG-LT-5503` are two
  different real laptops, not a typo) or a naming convention that happens
  to produce near-identical strings for unrelated machines. The fuzzy pass
  will flag these. It has no way to tell "typo" from "adjacent asset tag"
  on its own.
- **This is a triage aid, not an auto-merge tool.** It does not write
  anything back to LegacyCMDB or Intune, and it shouldn't be wired up to do so
  without a human confirming each group first, especially anything below
  high confidence. High-confidence (serial match) groups are about as safe
  as this kind of thing gets, but even there I'd want a person to glance at
  the pair before deleting a record.
- **The canonical-record suggestion is a heuristic, not a source of
  truth.** "Most recent check-in wins" breaks if, say, the stale record is
  actually the one with the correct department/owner metadata and the
  fresher one was mis-provisioned.
- **Serial number normalization is naive.** It strips whitespace and
  dashes and uppercases, which handles the formatting drift I actually saw,
  but wouldn't catch a serial recorded with extra characters, a checksum
  digit dropped, or manufacturer-prefix inconsistencies.
- **Not tested against a real export.** The sample data is small (41 rows)
  and clean by construction — I know exactly what duplicates are in it
  because I put them there. A real few-hundred-row export from two systems
  that have drifted for years will have messier cases: missing serials,
  swapped columns, devices that were legitimately reassigned to a new
  owner without changing the asset ID, retired devices still showing as
  active in one system. I'd expect the high-confidence pass to hold up
  fine against that; I'd trust the fuzzy pass a lot less without re-tuning
  the threshold against real data first.
