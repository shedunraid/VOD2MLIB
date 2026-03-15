"""
VOD .strm Generator Plugin for Dispatcharr
v1.4.0

MIT License
Copyright (c) 2025-2026 shedunraid
https://github.com/shedunraid/VODVSCODE
"""
import os
import re
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


class Plugin:
    """Generate .strm files for VOD movies from Dispatcharr."""

    name = "VOD2MLIB"
    version = "1.4.0"

    _generate_scheduler_thread = None
    _generate_scheduler_stop = None
    _cleanup_scheduler_thread = None
    _cleanup_scheduler_stop = None
    _generate_scheduler_cron = None   # cron the running generate scheduler was started with
    _cleanup_scheduler_cron = None    # cron the running cleanup scheduler was started with
    _last_root_folder = None          # tracks root folder at last scheduler start
    _last_series_root_folder = None   # tracks series root folder at last scheduler start

    description = (
        "Convert Dispatcharr VODs to media library format (.strm files) for movies and series. "
        "Map a host folder to /VODS in your Dispatcharr container, configure your movie and series "
        "root folders, then generate .strm files in batches. Optional NFO generation is supported "
        "for both movies and series. Series processing uses real concurrent threading for faster "
        "episode generation. Independent cron schedules for generate and cleanup."
    )

    fields = [
        # --- Paths & URL ---
        {
            "id": "root_folder",
            "label": "Root Folder for Movies",
            "type": "string",
            "default": "/vod/movies",
            "help_text": "Path where movie folders will be created. Leave blank to disable movie processing."
        },
        {
            "id": "series_root_folder",
            "label": "Root Folder for Series",
            "type": "string",
            "default": "/vod/series",
            "help_text": "Path where series folders will be created. Leave blank to disable series processing."
        },
        {
            "id": "dispatcharr_url",
            "label": "Dispatcharr URL (IMPORTANT!)",
            "type": "string",
            "default": "http://{ipaddress}:9191",
            "help_text": "Must be your actual IP address or reachable hostname, not localhost. This URL is written into .strm files and must be accessible from your media server."
        },
        # --- Batch size & NFO ---
        {
            "id": "batch_size",
            "label": "Batch Size",
            "type": "select",
            "default": "100",
            "options": [
                {"value": "1", "label": "1 (testing)"},
                {"value": "5", "label": "5"},
                {"value": "10", "label": "10"},
                {"value": "25", "label": "25"},
                {"value": "100", "label": "100"},
                {"value": "250", "label": "250"},
                {"value": "1000", "label": "1000"},
                {"value": "all", "label": "All (slow!)"}
            ],
            "help_text": "Number of movies or series to process per run"
        },
        {
            "id": "generate_nfo",
            "label": "Generate NFO Files",
            "type": "checkbox",
            "default": True,
            "help_text": "Create .nfo metadata files for movies, series, and episodes"
        },
        # --- Schedules ---
        {
            "id": "generate_schedule_cron",
            "label": "Generate Schedule (Cron)",
            "type": "string",
            "default": "0 2 * * *",
            "help_text": "Cron format: minute hour day month weekday. E.g. '0 2 * * *' = 2 AM daily, '0 2 * * 1-5' = 2 AM weekdays. Leave blank to disable. Schedules auto-apply when saved."
        },
        {
            "id": "cleanup_schedule_cron",
            "label": "Cleanup Schedule (Cron)",
            "type": "string",
            "default": "0 3 * * 0",
            "help_text": "Cron format: minute hour day month weekday. E.g. '0 3 * * 0' = 3 AM every Sunday, '0 3 1 * *' = 3 AM on the 1st of each month. Leave blank to disable. Schedules auto-apply when saved."
        }
    ]

    actions = [
        {
            "id": "generate_all",
            "label": "Generate All",
            "description": "Scan VODs then generate .strm files. Movies and/or series are processed based on which root folders are set."
        },
        {
            "id": "cleanup_all",
            "label": "Clean Up All",
            "description": "Remove orphaned .strm folders that no longer exist in Dispatcharr. Movies and/or series are processed based on which root folders are set."
        },
        {
            "id": "manage_schedules",
            "label": "Apply & Check Schedules",
            "description": "Apply current cron settings (non-blank enables, blank disables) then report scheduler status"
        }
    ]

    def on_unload(self, context):
        """Called when the plugin is disabled or reloaded — stop both scheduler threads."""
        self._stop_scheduler("generate")
        self._stop_scheduler("cleanup")
        Plugin._generate_scheduler_cron = None
        Plugin._cleanup_scheduler_cron = None
        Plugin._last_root_folder = None
        Plugin._last_series_root_folder = None

    def run(self, action: str, params: dict, context: dict):
        """Execute plugin action."""
        logger = context.get("logger")
        settings = context.get("settings", {})

        # Auto-manage schedulers: start/restart whenever cron or root folders change
        self._sync_schedulers(settings, logger)

        logger.info("=" * 60)
        logger.info("VOD .strm Generator v%s", self.version)
        logger.info("Action: %s", action)
        logger.info("=" * 60)

        if action == "generate_all":
            return self._generate_all(settings, logger)
        elif action == "cleanup_all":
            return self._cleanup_all(settings, logger)
        elif action == "manage_schedules":
            return self._manage_schedules(settings, logger)

        return {"status": "error", "message": f"Unknown action: {action}"}
    
    def _generate_all(self, settings: Dict[str, Any], logger):
        """Scan VODs then generate .strm files for all configured content types."""
        movies_enabled = bool(settings.get("root_folder", "").strip())
        series_enabled = bool(settings.get("series_root_folder", "").strip())

        if not movies_enabled and not series_enabled:
            logger.warning("Nothing to generate — both root folders are blank.")
            logger.warning("Set a Root Folder for Movies and/or Series to enable processing.")
            return {"status": "ok", "message": "Nothing to generate (both root folders are blank)"}

        # Scan counts first
        try:
            from apps.vod.models import M3UMovieRelation, M3USeriesRelation
            logger.info("")
            logger.info("Available VODs:")
            if movies_enabled:
                logger.info("  Movies:  %d", M3UMovieRelation.objects.count())
            if series_enabled:
                logger.info("  Series:  %d", M3USeriesRelation.objects.count())
            logger.info("")
        except Exception as e:
            logger.warning("Could not scan counts: %s", e)

        if movies_enabled:
            logger.info("--- Generating movies ---")
            self._generate_movies(settings, logger)

        if series_enabled:
            logger.info("--- Generating series ---")
            self._generate_series(settings, logger)

        return {"status": "ok", "message": "Generate All complete"}

    def _cleanup_all(self, settings: Dict[str, Any], logger):
        """Remove orphaned .strm folders for all configured content types."""
        movies_enabled = bool(settings.get("root_folder", "").strip())
        series_enabled = bool(settings.get("series_root_folder", "").strip())

        if not movies_enabled and not series_enabled:
            logger.warning("Nothing to clean up — both root folders are blank.")
            logger.warning("Set a Root Folder for Movies and/or Series to enable processing.")
            return {"status": "ok", "message": "Nothing to clean up (both root folders are blank)"}

        if movies_enabled:
            logger.info("--- Cleaning up orphaned movies ---")
            self._cleanup_movies(settings, logger)

        if series_enabled:
            logger.info("--- Cleaning up orphaned series ---")
            self._cleanup_series(settings, logger)

        return {"status": "ok", "message": "Cleanup All complete"}
    
    def _generate_movies(self, settings: Dict[str, Any], logger):
        """Generate movie .strm files according to batch size."""
        root_folder = settings.get("root_folder", "/vod/movies")
        dispatcharr_url = settings.get("dispatcharr_url", "http://{ipaddress}:9191").rstrip("/")
        batch_size = settings.get("batch_size") or "100"
        generate_nfo = settings.get("generate_nfo", True)
        
        # Validate URL is not localhost
        if "localhost" in dispatcharr_url.lower() or "127.0.0.1" in dispatcharr_url:
            logger.error("=" * 60)
            logger.error("CONFIGURATION ERROR!")
            logger.error("Dispatcharr URL is set to localhost/127.0.0.1")
            logger.error("This will NOT work in media servers!")
            logger.error("")
            logger.error("Current setting: %s", dispatcharr_url)
            logger.error("Change to: http://192.168.99.11:9191 (or your actual IP)")
            logger.error("=" * 60)
            return {
                "status": "error",
                "message": "Dispatcharr URL must be an actual IP address, not localhost! Update settings and try again."
            }
        
        logger.info("")
        logger.info("Configuration:")
        logger.info("  Root Folder: %s", root_folder)
        logger.info("  Dispatcharr URL: %s", dispatcharr_url)
        logger.info("  Batch Size: %s", batch_size)
        logger.info("  Generate NFO: %s", "Yes" if generate_nfo else "No")
        logger.info("")
        
        # Import Django models
        try:
            from apps.vod.models import Movie, M3UMovieRelation
            from apps.m3u.models import M3UAccount
        except ImportError as e:
            logger.error("Failed to import models: %s", e)
            return {"status": "error", "message": f"Import error: {e}"}
        
        # Get total count first
        logger.info("Scanning database...")
        try:
            total_count = M3UMovieRelation.objects.count()
            logger.info("Total VODs in database: %d", total_count)
            logger.info("")
        except Exception as e:
            logger.error("Failed to count VODs: %s", e)
            return {"status": "error", "message": f"Database error: {e}"}
        
        # Get movies based on batch size
        logger.info("Querying movies for this batch...")
        try:
            # Get movies with their M3U relations
            query = M3UMovieRelation.objects.select_related('movie', 'm3u_account', 'category')
            filtered_count = query.count()
            
            if batch_size == "all":
                movie_relations = list(query)
                logger.info("Processing ALL %d movies", filtered_count)
                target_batch = filtered_count
            else:
                target_batch = int(batch_size)
                # Fetch 3x batch size to account for skips
                fetch_size = min(target_batch * 3, filtered_count)
                movie_relations = list(query[:fetch_size])
                logger.info("Fetching %d movies to process batch of %d", fetch_size, target_batch)
            
            if not movie_relations:
                logger.warning("No movies found in database!")
                return {
                    "status": "ok",
                    "message": "No movies found to process",
                    "processed": 0
                }
            
            logger.info("Found %d movies to process", len(movie_relations))
            logger.info("")
            
        except Exception as e:
            logger.error("Database query failed: %s", e)
            return {"status": "error", "message": f"Database error: {e}"}
        
        # Ensure root folder exists
        try:
            os.makedirs(root_folder, exist_ok=True)
            logger.info("Root folder ready: %s", root_folder)
            logger.info("")
        except Exception as e:
            logger.error("Failed to create root folder: %s", e)
            return {"status": "error", "message": f"Folder creation error: {e}"}
        
        # Process movies until we've created the target batch
        created_strm = 0
        created_nfo = 0
        skipped = 0
        errors = 0
        processed = 0
        
        logger.info("Processing movies:")
        logger.info("-" * 60)
        
        for idx, relation in enumerate(movie_relations, 1):
            processed += 1
            movie = relation.movie
            stream_id = relation.stream_id
            
            # Build movie name with year (clean language prefix)
            raw_name = movie.name or f"Unknown Movie {movie.id}"
            movie_name = self._clean_title(raw_name)
            year = movie.year
            
            if year:
                folder_name = f"{self._sanitize_filename(movie_name)} ({year})"
                strm_filename = f"{self._sanitize_filename(movie_name)} ({year}).strm"
            else:
                folder_name = self._sanitize_filename(movie_name)
                strm_filename = f"{self._sanitize_filename(movie_name)}.strm"
            
            # Create movie folder and paths
            movie_folder = os.path.join(root_folder, folder_name)
            strm_path = os.path.join(movie_folder, strm_filename)
            
            # Check if already processed
            if os.path.exists(strm_path):
                skipped += 1
                if idx % 50 == 1 or idx <= 10:
                    logger.info("")
                    logger.info("[%d/%d] %s - Already exists, skipping", idx, len(movie_relations), movie_name)
                continue
            
            # Stop if we've created enough for this batch (unless processing all)
            if batch_size != "all" and created_strm >= target_batch:
                logger.info("")
                logger.info("Batch complete! Created %d movies.", target_batch)
                break
            
            # Build proxy URL
            proxy_url = f"{dispatcharr_url}/proxy/vod/movie/{movie.uuid}?stream_id={stream_id}"
            
            # Log every 50th movie to avoid spam
            if idx % 50 == 1 or idx <= 10:
                logger.info("")
                logger.info("[%d/%d] %s", idx, len(movie_relations), movie_name)
                logger.info("  Year: %s", year if year else "Unknown")
                logger.info("  Folder: %s", folder_name)
                logger.info("  UUID: %s", movie.uuid)
                logger.info("  Stream ID: %s", stream_id)
            
            try:
                # Create folder
                os.makedirs(movie_folder, exist_ok=True)
                
                # Write .strm file
                with open(strm_path, 'w', encoding='utf-8') as f:
                    f.write(proxy_url)
                created_strm += 1
                
                # Write .nfo file if enabled
                if generate_nfo:
                    nfo_filename = strm_filename.replace('.strm', '.nfo')
                    nfo_path = os.path.join(movie_folder, nfo_filename)
                    
                    category_name = relation.category.name if relation.category else ""
                    nfo_content = self._generate_nfo(movie, category_name)
                    
                    with open(nfo_path, 'w', encoding='utf-8') as f:
                        f.write(nfo_content)
                    created_nfo += 1
                
                if idx % 50 == 1 or idx <= 10:
                    logger.info("  ✓ Created: .strm%s", " + .nfo" if generate_nfo else "")
                
            except Exception as e:
                logger.error("  ✗ Error: %s", e)
                errors += 1
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("SUMMARY:")
        logger.info("  Total in DB:    %d", total_count)
        logger.info("  Examined:       %d", processed)
        logger.info("  .strm created:  %d", created_strm)
        if generate_nfo:
            logger.info("  .nfo created:   %d", created_nfo)
        logger.info("  Skipped:        %d", skipped)
        logger.info("  Errors:         %d", errors)
        logger.info("=" * 60)
        logger.info("")
        logger.info("Complete! Check your media server to verify playback.")
        
        summary_msg = f"Created {created_strm} .strm files"
        if generate_nfo:
            summary_msg += f" + {created_nfo} .nfo files"
        
        return {
            "status": "ok",
            "message": summary_msg,
            "total_in_db": total_count,
            "processed": processed,
            "created_strm": created_strm,
            "created_nfo": created_nfo if generate_nfo else 0,
            "skipped": skipped,
            "errors": errors
        }
    
    def _generate_series(self, settings: Dict[str, Any], logger):
        """Generate series .strm files with episodes using parallel processing."""
        series_root = settings.get("series_root_folder", "/vod/series")
        dispatcharr_url = settings.get("dispatcharr_url", "http://{ipaddress}:9191").rstrip("/")
        batch_size = settings.get("batch_size") or "100"
        generate_nfo = settings.get("generate_nfo", True)
        
        # Validate URL
        if "localhost" in dispatcharr_url.lower() or "127.0.0.1" in dispatcharr_url:
            return {"status": "error", "message": "Dispatcharr URL must be an actual IP address!"}
        
        logger.info("")
        logger.info("Configuration:")
        logger.info("  Series Root: %s", series_root)
        logger.info("  Dispatcharr URL: %s", dispatcharr_url)
        logger.info("  Batch Size: %s", batch_size)
        logger.info("  Generate NFO: %s", "Yes" if generate_nfo else "No")
        logger.info("  Threading: ENABLED (3 workers)")
        logger.info("")
        
        try:
            from apps.vod.models import M3USeriesRelation
        except ImportError as e:
            logger.error("Failed to import models: %s", e)
            return {"status": "error", "message": f"Import error: {e}"}
        
        # Get series
        try:
            query = M3USeriesRelation.objects.select_related('series', 'm3u_account', 'category')
            total_count = query.count()
            
            if batch_size == "all":
                series_relations = list(query)
                logger.info("Processing ALL %d series", total_count)
                target_batch = total_count
            else:
                target_batch = int(batch_size)
                # Fetch enough to account for skips
                fetch_size = min(target_batch * 3, total_count)
                series_relations = list(query[:fetch_size])
                logger.info("Fetching %d series to process batch of %d", fetch_size, target_batch)
            
            if not series_relations:
                return {"status": "ok", "message": "No series found"}
            
            logger.info("Found %d series to process", len(series_relations))
            logger.info("")
        except Exception as e:
            logger.error("Query failed: %s", e)
            return {"status": "error", "message": f"Database error: {e}"}
        
        # Ensure root exists
        try:
            os.makedirs(series_root, exist_ok=True)
        except Exception as e:
            return {"status": "error", "message": f"Folder creation error: {e}"}
        
        # Process series with ThreadPoolExecutor (3 workers for safety)
        created_strm = 0
        created_nfo = 0
        errors = 0
        series_created = 0
        skipped = 0
        
        logger.info("Processing series with 3 parallel workers:")
        logger.info("-" * 60)
        
        max_workers = 3
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks for series that need processing
            futures = {}
            submitted = 0
            
            for series_rel in series_relations:
                # Stop submitting if we already have enough created
                if batch_size != "all" and series_created >= target_batch:
                    break
                
                # Submit the processing task
                future = executor.submit(
                    self._process_single_series,
                    series_rel,
                    dispatcharr_url,
                    generate_nfo,
                    series_root,
                    logger
                )
                futures[future] = series_rel
                submitted += 1
            
            logger.info("Submitted %d series for parallel processing...", submitted)
            logger.info("")
            
            # Process results as they complete
            for idx, future in enumerate(as_completed(futures), 1):
                series_rel = futures[future]
                
                try:
                    result = future.result()
                    
                    if result.get("skipped"):
                        skipped += 1
                        logger.info("[%d/%d] %s", idx, submitted, result["message"])
                    elif result.get("created"):
                        series_created += 1
                        created_strm += result["episodes"]
                        created_nfo += result["nfo_files"]
                        logger.info("[%d/%d] %s", idx, submitted, result["message"])
                    else:
                        # No episodes or other issue
                        logger.info("[%d/%d] %s", idx, submitted, result["message"])
                    
                    if "error" in result:
                        errors += 1
                    
                    # Stop if we've created enough
                    if batch_size != "all" and series_created >= target_batch:
                        logger.info("")
                        logger.info("Batch target reached! Waiting for in-progress tasks...")
                        
                except Exception as e:
                    logger.error("[%d/%d] Error processing series: %s", idx, submitted, e)
                    errors += 1
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("SUMMARY:")
        logger.info("  Series created: %d", series_created)
        logger.info("  Series skipped: %d", skipped)
        logger.info("  Episodes created: %d", created_strm)
        if generate_nfo:
            logger.info("  NFO files created: %d", created_nfo)
        logger.info("  Errors: %d", errors)
        logger.info("=" * 60)
        
        summary_msg = f"Created {series_created} series with {created_strm} episodes"
        if generate_nfo:
            summary_msg += f" + {created_nfo} NFO files"
        
        return {
            "status": "ok",
            "message": summary_msg,
            "series_processed": series_created,
            "episodes_created": created_strm,
            "nfo_created": created_nfo if generate_nfo else 0,
            "errors": errors
        }
    
    def _process_single_series(self, series_rel, dispatcharr_url, generate_nfo, series_root, logger):
        """Process a single series - fetches episodes and creates files (thread-safe)."""
        from apps.vod.models import M3UEpisodeRelation
        from apps.vod.tasks import refresh_series_episodes
        
        series = series_rel.series
        
        # Clean series name
        raw_name = series.name or f"Unknown Series {series.id}"
        series_name = self._clean_title(raw_name)
        year = series.year
        
        if year:
            series_folder_name = f"{self._sanitize_filename(series_name)} ({year})"
        else:
            series_folder_name = self._sanitize_filename(series_name)
        
        series_folder = os.path.join(series_root, series_folder_name)
        
        # Check if already processed (has Season folders with content)
        if os.path.exists(series_folder):
            try:
                has_seasons = any(
                    item.startswith("Season") and os.path.isdir(os.path.join(series_folder, item))
                    for item in os.listdir(series_folder)
                )
                if has_seasons:
                    return {
                        "created": False,
                        "skipped": True,
                        "series_name": series_name,
                        "episodes": 0,
                        "nfo_files": 0,
                        "message": f"{series_name} - Already processed"
                    }
            except:
                pass  # If error checking, process anyway
        
        try:
            # Fetch episodes for this series
            custom_props = series_rel.custom_properties or {}
            if not custom_props.get('episodes_fetched', False):
                refresh_series_episodes(
                    account=series_rel.m3u_account,
                    series=series_rel.series,
                    external_series_id=series_rel.external_series_id
                )
            
            # Get episodes for this series
            episodes = M3UEpisodeRelation.objects.filter(
                m3u_account=series_rel.m3u_account
            ).select_related('episode')
            
            # Filter to only episodes belonging to this series
            episodes = [ep for ep in episodes if ep.episode.series and ep.episode.series.id == series.id]
            
            # Sort by season and episode number
            episodes = sorted(episodes, key=lambda ep: (ep.episode.season_number or 0, ep.episode.episode_number or 0))
            
            episode_count = len(episodes)
            
            if episode_count == 0:
                return {
                    "created": False,
                    "skipped": False,
                    "series_name": series_name,
                    "episodes": 0,
                    "nfo_files": 0,
                    "message": f"{series_name} - No episodes found"
                }
            
            # Create series folder
            os.makedirs(series_folder, exist_ok=True)
            
            nfo_count = 0
            
            # Generate tvshow.nfo if enabled
            if generate_nfo:
                tvshow_nfo_path = os.path.join(series_folder, "tvshow.nfo")
                category_name = series_rel.category.name if series_rel.category else ""
                tvshow_content = self._generate_tvshow_nfo(series, category_name)
                with open(tvshow_nfo_path, 'w', encoding='utf-8') as f:
                    f.write(tvshow_content)
                nfo_count += 1
            
            # Process episodes by season
            for episode_rel in episodes:
                episode = episode_rel.episode
                season_num = episode.season_number or 0
                episode_num = episode.episode_number or 0
                
                # Create season folder
                season_folder_name = f"Season {season_num:02d}"
                season_folder = os.path.join(series_folder, season_folder_name)
                os.makedirs(season_folder, exist_ok=True)
                
                # Build episode filename
                episode_title = episode.name or ""
                if episode_title:
                    clean_title = self._clean_title(episode_title)
                    filename = f"{series_name} - S{season_num:02d}E{episode_num:02d} - {clean_title}"
                else:
                    filename = f"{series_name} - S{season_num:02d}E{episode_num:02d}"
                
                filename = self._sanitize_filename(filename)
                
                # Create .strm file
                strm_path = os.path.join(season_folder, f"{filename}.strm")
                proxy_url = f"{dispatcharr_url}/proxy/vod/episode/{episode.uuid}?stream_id={episode_rel.stream_id}"
                
                with open(strm_path, 'w', encoding='utf-8') as f:
                    f.write(proxy_url)
                
                # Create episode .nfo if enabled
                if generate_nfo:
                    nfo_path = os.path.join(season_folder, f"{filename}.nfo")
                    episode_nfo_content = self._generate_episode_nfo(episode)
                    with open(nfo_path, 'w', encoding='utf-8') as f:
                        f.write(episode_nfo_content)
                    nfo_count += 1
            
            return {
                "created": True,
                "skipped": False,
                "series_name": series_name,
                "episodes": episode_count,
                "nfo_files": nfo_count,
                "message": f"{series_name} - ✓ Created {episode_count} episodes"
            }
            
        except Exception as e:
            return {
                "created": False,
                "skipped": False,
                "series_name": series_name,
                "episodes": 0,
                "nfo_files": 0,
                "error": str(e),
                "message": f"{series_name} - ✗ Error: {e}"
            }
    
    def _cleanup_movies(self, settings: Dict[str, Any], logger):
        """Remove movie folders that no longer exist in Dispatcharr (orphan cleanup)."""
        import shutil
        root_folder = settings.get("root_folder", "").strip()

        if not root_folder:
            logger.info("Movie root folder is blank — skipping.")
            return {"status": "ok", "message": "Skipped (root folder blank)"}

        if not os.path.exists(root_folder):
            logger.info("Root folder doesn't exist. Nothing to clean up.")
            return {"status": "ok", "message": "Root folder doesn't exist"}

        # Build set of expected folder names from Dispatcharr DB
        logger.info("Querying Dispatcharr for current movie list...")
        try:
            from apps.vod.models import M3UMovieRelation
            expected = set()
            for rel in M3UMovieRelation.objects.select_related("movie"):
                movie = rel.movie
                name = self._clean_title(movie.name or f"Unknown Movie {movie.id}")
                year = movie.year
                folder = f"{self._sanitize_filename(name)} ({year})" if year else self._sanitize_filename(name)
                expected.add(folder)
            logger.info("  %d movies in Dispatcharr", len(expected))
        except Exception as e:
            logger.error("Failed to query Dispatcharr: %s", e)
            return {"status": "error", "message": f"DB query error: {e}"}

        # Find and delete folders not in the expected set
        deleted = 0
        errors = 0
        orphans = []

        for item in os.listdir(root_folder):
            item_path = os.path.join(root_folder, item)
            if os.path.isdir(item_path) and item not in expected:
                orphans.append((item, item_path))

        logger.info("  %d orphaned movie folders found", len(orphans))

        if not orphans:
            logger.info("Nothing to remove — all folders match Dispatcharr.")
            return {"status": "ok", "message": "No orphaned movie folders found", "deleted": 0}

        logger.info("Removing orphans:")
        logger.info("-" * 60)
        for idx, (name, path) in enumerate(orphans, 1):
            try:
                shutil.rmtree(path)
                deleted += 1
                if idx <= 10 or idx % 50 == 0:
                    logger.info("  [%d/%d] Deleted: %s", idx, len(orphans), name)
            except Exception as e:
                logger.error("  Failed to delete %s: %s", name, e)
                errors += 1

        logger.info("")
        logger.info("MOVIE CLEANUP SUMMARY:")
        logger.info("  Orphans removed: %d", deleted)
        logger.info("  Errors:          %d", errors)

        return {"status": "ok", "message": f"Removed {deleted} orphaned movie folders", "deleted": deleted, "errors": errors}
    
    def _cleanup_series(self, settings: Dict[str, Any], logger):
        """Remove series folders that no longer exist in Dispatcharr (orphan cleanup)."""
        import shutil
        series_root = settings.get("series_root_folder", "").strip()

        if not series_root:
            logger.info("Series root folder is blank — skipping.")
            return {"status": "ok", "message": "Skipped (series root folder blank)"}

        if not os.path.exists(series_root):
            logger.info("Series root doesn't exist. Nothing to clean up.")
            return {"status": "ok", "message": "Series root doesn't exist"}

        # Build set of expected folder names from Dispatcharr DB
        logger.info("Querying Dispatcharr for current series list...")
        try:
            from apps.vod.models import M3USeriesRelation
            expected = set()
            for rel in M3USeriesRelation.objects.select_related("series"):
                series = rel.series
                name = self._clean_title(series.name or f"Unknown Series {series.id}")
                year = series.year
                folder = f"{self._sanitize_filename(name)} ({year})" if year else self._sanitize_filename(name)
                expected.add(folder)
            logger.info("  %d series in Dispatcharr", len(expected))
        except Exception as e:
            logger.error("Failed to query Dispatcharr: %s", e)
            return {"status": "error", "message": f"DB query error: {e}"}

        # Find and delete folders not in the expected set
        deleted = 0
        errors = 0
        orphans = []

        for item in os.listdir(series_root):
            item_path = os.path.join(series_root, item)
            if os.path.isdir(item_path) and item not in expected:
                orphans.append((item, item_path))

        logger.info("  %d orphaned series folders found", len(orphans))

        if not orphans:
            logger.info("Nothing to remove — all folders match Dispatcharr.")
            return {"status": "ok", "message": "No orphaned series folders found", "deleted": 0}

        logger.info("Removing orphans:")
        logger.info("-" * 60)
        for idx, (name, path) in enumerate(orphans, 1):
            try:
                shutil.rmtree(path)
                deleted += 1
                if idx <= 10 or idx % 50 == 0:
                    logger.info("  [%d/%d] Deleted: %s", idx, len(orphans), name)
            except Exception as e:
                logger.error("  Failed to delete %s: %s", name, e)
                errors += 1

        logger.info("")
        logger.info("SERIES CLEANUP SUMMARY:")
        logger.info("  Orphans removed: %d", deleted)
        logger.info("  Errors:          %d", errors)

        return {"status": "ok", "message": f"Removed {deleted} orphaned series folders", "deleted": deleted, "errors": errors}
    
    def _stop_scheduler(self, kind: str):
        """Stop a named scheduler thread (kind = 'generate' or 'cleanup')."""
        stop_attr = f"_{kind}_scheduler_stop"
        thread_attr = f"_{kind}_scheduler_thread"
        stop = getattr(Plugin, stop_attr)
        thread = getattr(Plugin, thread_attr)
        if stop is not None:
            stop.set()
            if thread is not None and thread.is_alive():
                thread.join(timeout=5)
        setattr(Plugin, stop_attr, None)
        setattr(Plugin, thread_attr, None)

    def _start_scheduler(self, kind: str, settings: Dict[str, Any], logger):
        """Start a named scheduler thread (kind = 'generate' or 'cleanup')."""
        import threading

        self._stop_scheduler(kind)

        cron_key = f"{kind}_schedule_cron"
        cron_expr = settings.get(cron_key, "0 3 * * *")
        if len(cron_expr.strip().split()) != 5:
            logger.error("Invalid cron expression for %s schedule: '%s'", kind, cron_expr)
            return

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._scheduler_loop,
            args=(kind, cron_expr, settings, stop_event, logger),
            daemon=True,
            name=f"VOD2MLIB-{kind}-scheduler"
        )
        setattr(Plugin, f"_{kind}_scheduler_stop", stop_event)
        setattr(Plugin, f"_{kind}_scheduler_thread", thread)
        thread.start()
        logger.info("%s scheduler started: %s", kind.capitalize(), cron_expr)

    def _sync_schedulers(self, settings: Dict[str, Any], logger):
        """Start, restart, or stop each scheduler if its cron or root folder settings changed."""
        gen_cron = settings.get("generate_schedule_cron", "").strip()
        cln_cron = settings.get("cleanup_schedule_cron", "").strip()
        root = settings.get("root_folder", "").strip()
        series_root = settings.get("series_root_folder", "").strip()

        settings_sig = (gen_cron, cln_cron, root, series_root)
        last_sig = (Plugin._generate_scheduler_cron, Plugin._cleanup_scheduler_cron,
                    Plugin._last_root_folder, Plugin._last_series_root_folder)

        if settings_sig == last_sig:
            # Also check threads are still alive; restart silently if they died
            for kind, cron in (("generate", gen_cron), ("cleanup", cln_cron)):
                thread = getattr(Plugin, f"_{kind}_scheduler_thread")
                if cron and (thread is None or not thread.is_alive()):
                    self._start_scheduler(kind, settings, logger)
            return

        # Settings changed — apply and record new signature
        for kind, cron in (("generate", gen_cron), ("cleanup", cln_cron)):
            if cron:
                self._start_scheduler(kind, settings, logger)
            else:
                self._stop_scheduler(kind)

        Plugin._generate_scheduler_cron = gen_cron
        Plugin._cleanup_scheduler_cron = cln_cron
        Plugin._last_root_folder = root
        Plugin._last_series_root_folder = series_root

    def _manage_schedules(self, settings: Dict[str, Any], logger):
        """Force-apply current schedule settings then report status."""
        # Reset signature so _sync_schedulers always re-applies
        Plugin._generate_scheduler_cron = None
        Plugin._cleanup_scheduler_cron = None
        Plugin._last_root_folder = None
        Plugin._last_series_root_folder = None
        self._sync_schedulers(settings, logger)

        logger.info("")
        logger.info("SCHEDULE STATUS:")
        for kind in ("generate", "cleanup"):
            thread = getattr(Plugin, f"_{kind}_scheduler_thread")
            cron = settings.get(f"{kind}_schedule_cron", "").strip()
            if thread is not None and thread.is_alive():
                logger.info("  %s: RUNNING  (cron: %s)", kind.capitalize(), cron)
            else:
                logger.info("  %s: %s", kind.capitalize(),
                            "NOT RUNNING" if cron else "DISABLED (cron is blank)")
        movies_enabled = bool(settings.get("root_folder", "").strip())
        series_enabled = bool(settings.get("series_root_folder", "").strip())
        logger.info("  Movies:  %s", settings.get("root_folder") if movies_enabled else "disabled (blank)")
        logger.info("  Series:  %s", settings.get("series_root_folder") if series_enabled else "disabled (blank)")
        return {"status": "ok", "message": "Schedules applied and status logged"}

    def _matches_cron(self, cron_expr: str, dt) -> bool:
        """Check if a datetime matches a 5-field cron expression."""
        try:
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                return False
            minute, hour, dom, month, dow = parts

            def matches(field, value):
                if field == '*':
                    return True
                if '/' in field:
                    base, step = field.split('/', 1)
                    step = int(step)
                    start = 0 if base == '*' else int(base)
                    return value >= start and (value - start) % step == 0
                if ',' in field:
                    return value in [int(x) for x in field.split(',')]
                if '-' in field:
                    lo, hi = field.split('-', 1)
                    return int(lo) <= value <= int(hi)
                return int(field) == value

            return (
                matches(minute, dt.minute) and
                matches(hour, dt.hour) and
                matches(dom, dt.day) and
                matches(month, dt.month) and
                matches(dow, dt.isoweekday() % 7)  # 0=Sunday
            )
        except Exception:
            return False

    def _scheduler_loop(self, kind: str, cron_expr: str, settings: dict, stop_event, logger):
        """Background thread: checks a cron expression every 30 s and fires the matching action."""
        from datetime import datetime

        action = self._generate_all if kind == "generate" else self._cleanup_all
        last_fired_minute = None

        while not stop_event.is_set():
            now = datetime.now()
            current_minute = (now.year, now.month, now.day, now.hour, now.minute)

            if current_minute != last_fired_minute and self._matches_cron(cron_expr, now):
                last_fired_minute = current_minute
                logger.info("%s scheduler triggered at %s", kind.capitalize(), now.strftime("%Y-%m-%d %H:%M"))
                try:
                    action(settings, logger)
                except Exception as e:
                    logger.error("%s scheduled run error: %s", kind.capitalize(), e)

            stop_event.wait(30)

        logger.info("%s scheduler stopped.", kind.capitalize())

    def _clean_title(self, title: str) -> str:
        """Remove language prefixes (EN -, FR -, etc.) from movie titles."""
        if not title:
            return title
        
        # Remove common language prefixes: EN -, FR -, US -, etc.
        cleaned = re.sub(r'^[A-Z]{2,3}\s*-\s*', '', title)
        return cleaned.strip()
    
    def _extract_genres(self, category_name: str) -> list:
        """Extract genre names from category name."""
        if not category_name:
            return []
        
        # Remove common prefixes (EN -, FR -, US -, etc.)
        genre_text = re.sub(r'^[A-Z]{2,3}\s*-\s*', '', category_name)
        
        # Remove (movie) or (series) suffix
        genre_text = re.sub(r'\s*\((movie|series)\)\s*$', '', genre_text, flags=re.IGNORECASE)
        
        # Split on common separators
        genres = re.split(r'[/&,]', genre_text)
        
        # Clean up each genre
        cleaned_genres = []
        for genre in genres:
            genre = genre.strip()
            # Capitalize first letter of each word
            genre = ' '.join(word.capitalize() for word in genre.split())
            if genre:
                cleaned_genres.append(genre)
        
        return cleaned_genres or ["Unknown"]
    
    def _generate_tvshow_nfo(self, series, category_name: str) -> str:
        """Generate tvshow.nfo XML content for a series."""
        # Extract basic info (clean language prefix)
        raw_title = series.name or "Unknown"
        title = self._clean_title(raw_title)
        year = series.year or ""
        plot = series.description or ""
        
        # Extract genres from category
        genres = self._extract_genres(category_name)
        
        # Build XML
        xml_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
        xml_lines.append('<tvshow>')
        xml_lines.append(f'    <title>{self._xml_escape(title)}</title>')
        
        if year:
            xml_lines.append(f'    <year>{year}</year>')
        
        for genre in genres:
            xml_lines.append(f'    <genre>{self._xml_escape(genre)}</genre>')
        
        if plot:
            xml_lines.append(f'    <plot>{self._xml_escape(plot)}</plot>')
        
        xml_lines.append('</tvshow>')
        
        return '\n'.join(xml_lines)
    
    def _generate_episode_nfo(self, episode) -> str:
        """Generate episode.nfo XML content for an episode."""
        # Extract episode info (clean language prefix)
        raw_title = episode.name or ""
        title = self._clean_title(raw_title) if raw_title else "Episode"
        season_num = episode.season_number or 0
        episode_num = episode.episode_number or 0
        plot = episode.description or ""
        
        # Build XML
        xml_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
        xml_lines.append('<episodedetails>')
        xml_lines.append(f'    <title>{self._xml_escape(title)}</title>')
        xml_lines.append(f'    <season>{season_num}</season>')
        xml_lines.append(f'    <episode>{episode_num}</episode>')
        
        if plot:
            xml_lines.append(f'    <plot>{self._xml_escape(plot)}</plot>')
        
        xml_lines.append('</episodedetails>')
        
        return '\n'.join(xml_lines)
    
    def _generate_nfo(self, movie, category_name: str) -> str:
        """Generate NFO XML content for a movie."""
        # Extract basic info (clean language prefix)
        raw_title = movie.name or "Unknown"
        title = self._clean_title(raw_title)
        year = movie.year or ""
        plot = movie.description or ""
        rating = movie.rating or ""
        tmdb_id = movie.tmdb_id or ""
        imdb_id = movie.imdb_id or ""
        
        # Extract genres from category
        genres = self._extract_genres(category_name)
        
        # Build XML
        xml_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
        xml_lines.append('<movie>')
        xml_lines.append(f'    <title>{self._xml_escape(title)}</title>')
        
        if year:
            xml_lines.append(f'    <year>{year}</year>')
        
        for genre in genres:
            xml_lines.append(f'    <genre>{self._xml_escape(genre)}</genre>')
        
        if plot:
            xml_lines.append(f'    <plot>{self._xml_escape(plot)}</plot>')
        
        if rating:
            xml_lines.append(f'    <rating>{rating}</rating>')
        
        if tmdb_id:
            xml_lines.append(f'    <tmdbid>{tmdb_id}</tmdbid>')
        
        if imdb_id:
            xml_lines.append(f'    <imdbid>{imdb_id}</imdbid>')
        
        xml_lines.append('</movie>')
        
        return '\n'.join(xml_lines)
    
    def _xml_escape(self, text: str) -> str:
        """Escape special XML characters."""
        if not text:
            return ""
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        return text
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename by removing invalid characters."""
        if not name:
            return "Unknown"
        
        # Remove invalid characters for Windows/Linux filesystems
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
        
        # Replace multiple spaces with single space
        name = re.sub(r'\s+', ' ', name)
        
        # Trim and limit length
        name = name.strip()[:200]
        
        # Remove trailing dots/spaces (Windows issue)
        name = name.rstrip('. ')
        
        return name or "Unknown"
