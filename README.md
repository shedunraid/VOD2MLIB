# VOD .strm Generator v1.3

Simple extension of v0.1 with configurable batch sizes.

## What's New in v1.1

- **Batch Size Options**: Choose 10, 50, 100, 200, 500, or All movies
- **Total Count Display**: Shows total VODs in database before processing
- **Progress Logging**: Logs every 50th movie to avoid spam

## Installation

1. Zip the `plugin.py` file.
2. In Dispatcharr → Plugins → Import
3. Enable the plugin

## Settings

- **Root Folder**: Where to create movie folders (e.g., `/data/movies`)
- **Dispatcharr URL**: Your actual IP (e.g., `http://192.168.99.11:9191`) - NOT localhost!
- **Batch Size**: How many movies to process (10, 50, 100, 200, 500, or All)

## Usage

### First Time
1. Set Batch Size to **10**
2. Click "Generate .strm Files"
3. Verify 10 movies created correctly
4. Test playback in media server

### Scale Up
1. Set Batch Size to **50**
2. Run again - processes next 50
3. Keep increasing as comfort grows

### Process All
1. Set Batch Size to **All**
2. Run once - processes entire catalog

## Output Example

```
============================================================
VOD .strm Generator v1.1.0
Action: generate
============================================================

Configuration:
  Root Folder: /data/movies
  Dispatcharr URL: http://192.168.99.11:9191
  Batch Size: 10

Scanning database...
Total VODs in database: 1234

Querying movies for this batch...
Processing 10 of 1234 movies
Found 10 movies to process

Root folder ready: /data/movies

Processing movies:
------------------------------------------------------------

[1/10] Avatar
  Year: 2009
  Folder: Avatar (2009)
  UUID: abc-123-def
  Stream ID: 1234567
  ✓ Created: /data/movies/Avatar (2009)/Avatar (2009).strm

... (details for other movies) ...

============================================================
SUMMARY:
  Total in DB:  1234
  Processed:    10
  Created:      10
  Skipped:      0
  Errors:       0
============================================================

Complete! Check your media server to verify playback.
```

## Folder Structure

```
/data/movies/
├── Avatar (2009)/
│   └── Avatar (2009).strm
├── Inception (2010)/
│   └── Inception (2010).strm
└── ...
```

## Differences from v0.1

| Feature | v0.1 | v1.1 |
|---------|------|------|
| Batch size | 5 only | 10, 50, 100, 200, 500, All |
| Total count | No | Yes |
| Progress | Every movie | Every 50th + first 10 |
| Action name | "Test Mode" | "Generate .strm Files" |

## Simple & Clean

Based on working v0.1 code with minimal additions:
- Same imports
- Same structure
- Same reliability
- Just adds batch size options

## Next Steps

Once this works perfectly:
- Add genre organization
- Add incremental processing (skip existing)
- Add progress notifications
- Add more features

But for now - keep it simple!


