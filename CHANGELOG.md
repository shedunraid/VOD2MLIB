# Changelog

---

## [1.4.0]

### Dispatcharr v0.20 Compatibility

Added `plugin.json` — required by Dispatcharr v0.20's updated plugin standard. Without it the plugin is flagged as legacy and prompts a warning in the UI. The manifest declares the plugin name, version, author, description, help URL, all settings fields with their types and defaults, and all actions. Dispatcharr reads this file to render the configuration UI and action buttons without executing any plugin code.

---

### Cron Scheduling

Two independent background scheduler threads — one for generate, one for cleanup — each driven by its own cron expression.

- **Generate Schedule** (default `0 2 * * *`) fires `Generate All` automatically, e.g. nightly to pick up new content added to Dispatcharr
- **Cleanup Schedule** (default `0 3 * * 0`) fires `Cleanup All` automatically, e.g. weekly to remove content removed from Dispatcharr
- Cron expressions support `*`, `/`, `,`, and `-` operators across all five fields (`minute hour day month weekday`)
- Leaving a cron field **blank** disables that schedule — no separate enable toggle required
- Schedules **auto-apply on settings save** — the plugin compares the current cron expressions and root folder paths against what each scheduler was last started with; any change triggers a clean restart of the affected thread automatically
- On container restart, schedulers **auto-start on the first button click** if cron expressions are configured, with no manual intervention required
- If a scheduler thread dies unexpectedly it is silently restarted on the next action
- Both threads are stopped cleanly via `on_unload` when the plugin is disabled or Dispatcharr reloads it

---

### Actions

| Old (v1.3.0) | New (v1.4.0) |
|---|---|
| Scan for VODs | *(merged into Generate All)* |
| Generate Movie .strm Files | *(merged into Generate All)* |
| Generate Series .strm Files | *(merged into Generate All)* |
| Clean Up Movies | *(merged into Clean Up All)* |
| Clean Up Series | *(merged into Clean Up All)* |
| — | **Generate All** |
| — | **Clean Up All** |
| — | **Apply & Check Schedules** |

**Generate All** — scans and logs the available movie and series counts from Dispatcharr, then generates `.strm` files for whichever content types have a root folder configured.

**Clean Up All** — runs orphan-aware cleanup for whichever content types have a root folder configured (see Cleanup section below).

**Apply & Check Schedules** — force-reapplies current cron settings then immediately reports the running state, cron expression, and content configuration of both schedulers.

---

### Orphan-Aware Cleanup

The cleanup behaviour has been completely rewritten. Previously, `Clean Up Movies` and `Clean Up Series` deleted every folder under the configured root regardless of whether the content still existed in Dispatcharr.

The new `Clean Up All` queries Dispatcharr's database to build the full expected set of folder names using the same naming logic as generation (`Title (Year)` / `Title`). It then removes only folders on disk that have **no matching entry in Dispatcharr**. Any content still present in Dispatcharr is never touched.

The cleanup log reports how many entries are in Dispatcharr, how many orphaned folders were identified, and how many were successfully removed.

---

### Settings

**Root folders as enable/disable switches** — leaving `Root Folder for Movies` or `Root Folder for Series` blank disables all processing (generate and cleanup) for that content type. No separate enable toggle required.

- `Root Folder for Movies` default: `/VODS/Movies` → `/vod/movies`
- `Root Folder for Series` default: `/VODS/Series` → `/vod/series`
- `Dispatcharr URL` default: `http://192.168.99.11:9191` → `http://{ipaddress}:9191` to prompt users to enter their actual address

**Unified batch size** — separate `Batch Size (Movies)` and `Batch Size (Series)` fields (with inconsistent options) replaced by a single `Batch Size` field used for both content types. Default changed from `250` to `100`. Options standardised to: `1 (testing)`, `5`, `10`, `25`, `100`, `250`, `1000`, `All (slow!)`.

**Unified NFO toggle** — separate `Generate Movie NFO Files` and `Generate Series NFO Files` toggles replaced by a single `Generate NFO Files` field that controls `.nfo` generation for movies, series, and episodes.

---

## [1.3.0]

Real concurrent threading for series processing using `ThreadPoolExecutor` with 3 parallel workers. Series batch processing time reduced by 50–70%.
