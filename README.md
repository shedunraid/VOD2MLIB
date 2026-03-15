# VOD2MLIB — Dispatcharr Plugin

**Convert your Dispatcharr VOD library into a media server-ready folder structure of `.strm` files.**

Supports movies and series. Generates Kodi/Jellyfin/Plex-compatible `.nfo` metadata. Orphan-aware cleanup. Built-in cron scheduling with auto-apply.

---

## Features

- **Generate `.strm` files** for movies and/or series from your Dispatcharr VOD library
- **NFO metadata** — movie, tvshow, and episode `.nfo` files compatible with Jellyfin, Kodi, and Plex
- **Orphan-aware cleanup** — removes only folders that no longer exist in Dispatcharr, leaving everything else untouched
- **Cron scheduling** — independent schedules for generate and cleanup, auto-applied when settings are saved
- **Concurrent series processing** — episodes fetched in parallel using 3 worker threads
- **Language prefix stripping** — cleans `EN -`, `FR -`, etc. from titles automatically
- **Flexible batch sizes** — process a small test batch first, then scale up

---

## Installation

1. Download `VOD2MLIB.zip` from the repository
2. In Dispatcharr, open the **Plugins** page from the sidebar
3. Click **Import Plugin**
4. Drag and drop the ZIP file onto the upload area, or click to browse and select it
5. Once imported, find **VOD2MLIB** in the plugin list and toggle it **on** to enable it
6. Click on the plugin to open its settings and configure it before running

---

## Settings

### Root Folder for Movies
**Default:** `/vod/movies`

The path inside the container where movie folders will be created. Each movie gets its own subfolder named `Title (Year)` containing a `.strm` file and an optional `.nfo` file. This path must be a volume you have mounted into the Dispatcharr container so your media server can also access it.

Leave this field **blank** to disable all movie processing — movies will be skipped in both Generate All and Clean Up All.

---

### Root Folder for Series
**Default:** `/vod/series`

The path inside the container where series folders will be created. Each series gets a folder named `Title (Year)` containing a `tvshow.nfo` and subfolders for each season (`Season 01`, `Season 02`, etc.), each containing per-episode `.strm` and `.nfo` files. This path must be a volume you have mounted into the Dispatcharr container so your media server can also access it.

Leave this field **blank** to disable all series processing — series will be skipped in both Generate All and Clean Up All.

---

### Dispatcharr URL
**Default:** `http://{ipaddress}:9191`

The base URL of your Dispatcharr instance as seen from your **media server** (not from inside the container). This URL is written directly into every `.strm` file, so when Jellyfin, Plex, or Kodi plays a file it fetches the stream from this address.

Replace `{ipaddress}` with your actual LAN IP address, e.g. `http://192.168.1.100:9191`. Do **not** use `localhost` or `127.0.0.1` — those addresses resolve to the media server itself, not to Dispatcharr.

---

### Batch Size
**Default:** `100`

How many movies or series to process in a single run. The plugin skips any title that already has a folder on disk, so running multiple times is safe — it will only create what is missing.

| Option | Use case |
|---|---|
| `1 (testing)` | Verify a single title works end to end before committing to a full run |
| `5` / `10` / `25` | Small test batches to check output before scaling up |
| `100` / `250` / `1000` | Regular incremental runs |
| `All (slow!)` | Process the entire library in one go — can take a long time for large libraries or series with many episodes |

---

### Generate NFO Files
**Default:** On

When enabled, a `.nfo` metadata file is created alongside every `.strm` file. These files are read by Jellyfin, Kodi, and Plex to populate title, year, genre, plot, and ratings without needing an internet scrape.

- Movies produce a `Title (Year).nfo` using the `<movie>` format
- Series produce a `tvshow.nfo` in the series root folder using the `<tvshow>` format
- Episodes produce individual `.nfo` files using the `<episodedetails>` format

Disable this if you prefer your media server to scrape metadata itself, or if you want to reduce the number of files created.

---

### Generate Schedule (Cron)
**Default:** `0 2 * * *` *(2 AM every day)*

A cron expression that controls when **Generate All** runs automatically in the background. The schedule starts automatically when the plugin is first used and restarts itself if this field is changed.

Leave this field **blank** to disable automatic generation entirely.

---

### Cleanup Schedule (Cron)
**Default:** `0 3 * * 0` *(3 AM every Sunday)*

A cron expression that controls when **Clean Up All** runs automatically in the background. Cleanup only removes folders that no longer have a matching entry in Dispatcharr — content still in your library is never touched.

Leave this field **blank** to disable automatic cleanup entirely.

---

### Cron Format Reference

```
minute  hour  day  month  weekday
  0      2     *     *       *     → 2 AM every day
  0      3     *     *       0     → 3 AM every Sunday
  0      3     1     *       *     → 3 AM on the 1st of each month
  0      2     *     *      1-5    → 2 AM weekdays only
  0     */6    *     *       *     → every 6 hours
```

Weekday values: `0` = Sunday, `1` = Monday … `6` = Saturday.

Schedules are automatically applied whenever settings are saved. No button click required.

---

## Actions

| Action | Description |
|---|---|
| **Generate All** | Scans Dispatcharr for VODs then generates `.strm` files for all enabled content types |
| **Clean Up All** | Removes folders on disk that no longer have a matching entry in Dispatcharr |
| **Apply & Check Schedules** | Force-reapplies cron settings and prints current scheduler status |

---

## Output Structure

### Movies
```
/vod/movies/
├── Avatar (2009)/
│   ├── Avatar (2009).strm
│   └── Avatar (2009).nfo
├── Inception (2010)/
│   ├── Inception (2010).strm
│   └── Inception (2010).nfo
└── ...
```

### Series
```
/vod/series/
├── Breaking Bad (2008)/
│   ├── tvshow.nfo
│   ├── Season 01/
│   │   ├── Breaking Bad - S01E01 - Pilot.strm
│   │   ├── Breaking Bad - S01E01 - Pilot.nfo
│   │   └── ...
│   └── Season 02/
│       └── ...
└── ...
```

---

## Recommended First Run

1. Set **Batch Size** to `1 (testing)`
2. Click **Generate All**
3. Verify the folder and `.strm` file were created correctly
4. Test playback in your media server
5. Increase batch size and run again — already-existing files are skipped automatically

---

## Scheduling

Both schedules run independently as background threads:

- **Generate** (default `0 2 * * *`) — runs nightly to pick up new content added to Dispatcharr
- **Cleanup** (default `0 3 * * 0`) — runs weekly on Sunday to remove content that was removed from Dispatcharr

Schedules start automatically on the first action after a container restart, and restart automatically if cron expressions or root folder paths are changed.

---

## License

MIT License — Copyright (c) 2025-2026 shedunraid
