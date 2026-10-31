# NPC personas (left to right)

Each `.txt` file is plain persona prose, ready to pass straight into `create_npc --persona`. Files are numbered in rough left-to-right political order; the Bloc Québécois persona sits by economic-left stance but carries its own nationalist axis rather than fitting the left-right line exactly.

| # | File | Suggested party code | Suggested role |
|---|------|----------------------|-----------------|
| 1 | `1_green_eco_socialist.txt` | `GRN` | MP |
| 2 | `2_ndp_labour_organizer.txt` | `NDP` | MP |
| 3 | `3_liberal_pragmatist.txt` | `LIB` | MP |
| 4 | `4_bq_quebec_nationalist.txt` | `BQ` | MP |
| 5 | `5_independent_swing_voter.txt` | `IND` | MP |
| 6 | `6_conservative_fiscal_hawk.txt` | `CON` | MP |
| 7 | `7_ppc_populist_libertarian.txt` | `PPC` | MP |

## Usage

From `CMHoC_Polsim/`, with your venv active:

```bash
python manage.py create_npc \
  --username npc_green_mp \
  --party GRN \
  --role MP \
  --riding "Some Existing Riding Name" \
  --persona "$(cat npcs/personas/1_green_eco_socialist.txt)"
```

Repeat per persona with a distinct `--username`, matching `--party` code, and (optionally) an existing `--riding` name from your `Riding` table. Omit `--riding` to leave the NPC's riding unset.

Tune `--reply-chance` (default `0.4`) and `--cooldown-minutes` (default `20`) per NPC if you want some to post more or less often than others.
