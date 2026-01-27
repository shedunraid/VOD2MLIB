"""
VOD .strm Generator Plugin for Dispatcharr
Beta v0.1 - Minimal working version
"""
import os
import re
from typing import Dict, Any


class Plugin:
    """Generate .strm files for VOD movies from Dispatcharr."""
    
    name = "VOD2MLIB"
    version = "1.0.2"
    description = """• Convert Dispatcharr VODs to media library format (.strm files).        • SETUP: Map a host folder to /VODS in your Dispatcharr container (e.g., /mnt/media:/VODS).        • Configure root folders in plugin settings (/VODS/Movies and /VODS/Series by default).        • USAGE: Click 'Scan for VODs' to see totals.        • Use 'Generate Movie/Series .strm Files' with batch sizes (start small like 10 to test).        • Episodes auto-fetch per series as needed.        • Repeat clicks until complete - smart skip logic prevents duplicates.        • TIMING: Movies are fast (~30 sec per 250).        • Series slower (~2-3 min per 10 series, longer for large series with many episodes).        • Use batch of 1 for testing.        • NOTE: If you get errors, do a full browser refresh (Ctrl+F5 / Cmd+Shift+R) and try again.        • If you like this plugin please donate: https://paypal.me/shedunraid"""
    
    fields = [
        {
            "id": "root_folder",
            "label": "Root Folder for Movies",
            "type": "string",
            "default": "/VODS/Movies",
            "help_text": "Path where movie folders will be created"
        },
        {
            "id": "series_root_folder",
            "label": "Root Folder for Series",
            "type": "string",
            "default": "/VODS/Series",
            "help_text": "Path where series folders will be created"
        },
        {
            "id": "dispatcharr_url",
            "label": "Dispatcharr URL (IMPORTANT!)",
            "type": "string",
            "default": "http://192.168.99.11:9191",
            "help_text": "⚠️ MUST be your actual IP address (not localhost)! This URL goes into .strm files and must be accessible from your media server."
        },
        {
            "id": "batch_size",
            "label": "Batch Size (Movies)",
            "type": "select",
            "default": "250",
            "options": [
                {"value": "10", "label": "10 movies"},
                {"value": "100", "label": "100 movies"},
                {"value": "200", "label": "200 movies"},
                {"value": "500", "label": "500 movies"},
                {"value": "1000", "label": "1000 movies"},
                {"value": "all", "label": "All movies"}
            ],
            "help_text": "Number of movies to process in this run"
        },
        {
            "id": "generate_nfo",
            "label": "Generate Movie NFO Files",
            "type": "checkbox",
            "default": True,
            "help_text": "Create .nfo metadata files for movies"
        },
        {
            "id": "series_batch_size",
            "label": "Batch Size (Series)",
            "type": "select",
            "default": "10",
            "options": [
                {"value": "1", "label": "1 series (testing)"},
                {"value": "5", "label": "5 series"},
                {"value": "10", "label": "10 series"},
                {"value": "25", "label": "25 series"},
                {"value": "all", "label": "All series (slow!)"}
            ],
            "help_text": "Series to process (episodes auto-fetched for each)"
        },
        {
            "id": "generate_series_nfo",
            "label": "Generate Series NFO Files",
            "type": "checkbox",
            "default": True,
            "help_text": "Create .nfo metadata files for series and episodes"
        }
    ]
    
    actions = [
        {
            "id": "scan_all_vods",
            "label": "Scan for VODs to Convert",
            "description": "Show total movies and series available in Dispatcharr"
        },
        {
            "id": "generate_movies",
            "label": "Generate Movie .strm Files",
            "description": "Process movies according to batch size"
        },
        {
            "id": "generate_series",
            "label": "Generate Series .strm Files",
            "description": "Fetch episodes + create .strm files (auto-fetch per series)"
        },
        {
            "id": "cleanup_movies",
            "label": "Clean Up Movies",
            "description": "⚠️ Remove all movie folders and .strm files"
        },
        {
            "id": "cleanup_series",
            "label": "Clean Up Series",
            "description": "⚠️ Remove all series folders and .strm files"
        }
    ]
    
    def run(self, action: str, params: dict, context: dict):
        """Execute plugin action."""
        logger = context.get("logger")
        settings = context.get("settings", {})
        
        logger.info("=" * 60)
        logger.info("VOD .strm Generator v%s", self.version)
        logger.info("Action: %s", action)
        logger.info("=" * 60)
        
        if action == "scan_all_vods":
            return self._scan_all_vods(settings, logger)
        elif action == "generate_movies":
            return self._generate_movies(settings, logger)
        elif action == "generate_series":
            return self._generate_series(settings, logger)
        elif action == "cleanup_movies":
            return self._cleanup_movies(settings, logger)
        elif action == "cleanup_series":
            return self._cleanup_series(settings, logger)
        
        return {"status": "error", "message": f"Unknown action: {action}"}
    
    def _scan_all_vods(self, settings: Dict[str, Any], logger):
        """Scan and show total movies and series available."""
        logger.info("Scanning VODs in Dispatcharr...")
        logger.info("")
        
        try:
            from apps.vod.models import M3UMovieRelation, M3USeriesRelation
        except ImportError as e:
            logger.error("Failed to import models: %s", e)
            return {"status": "error", "message": f"Import error: {e}"}
        
        try:
            # Count movies and series
            movie_count = M3UMovieRelation.objects.count()
            series_count = M3USeriesRelation.objects.count()
            
            logger.info("=" * 60)
            logger.info("MOVIES: %d", movie_count)
            logger.info("SERIES: %d", series_count)
            logger.info("=" * 60)
            logger.info("")
            logger.info("Use 'Generate Movie .strm Files' for movies")
            logger.info("Use 'Generate Series .strm Files' for series")
            
            return {
                "status": "ok",
                "message": f"Found {movie_count} movies and {series_count} series",
                "movies": movie_count,
                "series": series_count
            }
        except Exception as e:
            logger.error("Scan failed: %s", e)
            return {"status": "error", "message": f"Scan error: {e}"}
    
    def _generate_movies(self, settings: Dict[str, Any], logger):
        """Generate movie .strm files according to batch size."""
        root_folder = settings.get("root_folder", "/VODS/Movies")
        dispatcharr_url = settings.get("dispatcharr_url", "http://192.168.99.11:9191").rstrip("/")
        batch_size = settings.get("batch_size") or "250"
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
        """Generate series .strm files with episodes."""
        series_root = settings.get("series_root_folder", "/VODS/Series")
        dispatcharr_url = settings.get("dispatcharr_url", "http://192.168.99.11:9191").rstrip("/")
        batch_size = settings.get("series_batch_size") or "250"
        generate_nfo = settings.get("generate_series_nfo", True)
        
        # Validate URL
        if "localhost" in dispatcharr_url.lower() or "127.0.0.1" in dispatcharr_url:
            return {"status": "error", "message": "Dispatcharr URL must be an actual IP address!"}
        
        logger.info("")
        logger.info("Configuration:")
        logger.info("  Series Root: %s", series_root)
        logger.info("  Dispatcharr URL: %s", dispatcharr_url)
        logger.info("  Batch Size: %s", batch_size)
        logger.info("  Generate NFO: %s", "Yes" if generate_nfo else "No")
        logger.info("")
        
        try:
            from apps.vod.models import Series, M3USeriesRelation, M3UEpisodeRelation
            from apps.vod.tasks import refresh_series_episodes
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
                # Fetch 3x batch size to account for skips
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
        
        # Process series until we've created the target batch
        created_strm = 0
        created_nfo = 0
        errors = 0
        series_created = 0
        
        logger.info("Processing series:")
        logger.info("-" * 60)
        
        for idx, series_rel in enumerate(series_relations, 1):
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
            
            # Stop if we've created enough series for this batch (unless processing all)
            if batch_size != "all" and series_created >= target_batch:
                logger.info("")
                logger.info("Batch complete! Created %d series.", target_batch)
                break
            
            # Check if already processed (has Season folders with content)
            if os.path.exists(series_folder):
                try:
                    has_seasons = any(
                        item.startswith("Season") and os.path.isdir(os.path.join(series_folder, item))
                        for item in os.listdir(series_folder)
                    )
                    if has_seasons:
                        logger.info("")
                        logger.info("[%d/%d] %s - Already processed, skipping", idx, len(series_relations), series_name)
                        continue
                except:
                    pass  # If error checking, process anyway
            
            logger.info("")
            logger.info("[%d/%d] %s - Fetching episodes...", idx, len(series_relations), series_name)
            
            # Fetch episodes for this series (just-in-time)
            try:
                # Check if episodes already fetched
                custom_props = series_rel.custom_properties or {}
                if not custom_props.get('episodes_fetched', False):
                    # Fetch episodes from provider
                    refresh_series_episodes(
                        account=series_rel.m3u_account,
                        series=series_rel.series,
                        external_series_id=series_rel.external_series_id
                    )
                
                # Now get episodes for this series
                # Get all episodes for this account, then filter by series ID
                episodes = M3UEpisodeRelation.objects.filter(
                    m3u_account=series_rel.m3u_account
                ).select_related('episode')
                
                # Filter to only episodes belonging to this series
                episodes = [ep for ep in episodes if ep.episode.series and ep.episode.series.id == series.id]
                
                # Sort by season and episode number
                episodes = sorted(episodes, key=lambda ep: (ep.episode.season_number or 0, ep.episode.episode_number or 0))
                
                episode_count = len(episodes)
                logger.info("  Episodes: %d", episode_count)
                
                if episode_count == 0:
                    logger.info("  No episodes found, skipping")
                    continue
                
                logger.info("  Creating %d episodes...", episode_count)
                
                # Create series folder
                os.makedirs(series_folder, exist_ok=True)
                
                # Generate tvshow.nfo if enabled
                if generate_nfo:
                    tvshow_nfo_path = os.path.join(series_folder, "tvshow.nfo")
                    category_name = series_rel.category.name if series_rel.category else ""
                    tvshow_content = self._generate_tvshow_nfo(series, category_name)
                    with open(tvshow_nfo_path, 'w', encoding='utf-8') as f:
                        f.write(tvshow_content)
                    created_nfo += 1
                
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
                    created_strm += 1
                    
                    # Create episode .nfo if enabled
                    if generate_nfo:
                        nfo_path = os.path.join(season_folder, f"{filename}.nfo")
                        episode_nfo_content = self._generate_episode_nfo(episode)
                        with open(nfo_path, 'w', encoding='utf-8') as f:
                            f.write(episode_nfo_content)
                        created_nfo += 1
                
                logger.info("  ✓ Done! Created %d episodes", episode_count)
                series_created += 1
                
            except Exception as e:
                logger.error("  ✗ Error fetching/creating episodes: %s", e)
                errors += 1
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("SUMMARY:")
        logger.info("  Series created: %d", series_created)
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
    
    def _cleanup_movies(self, settings: Dict[str, Any], logger):
        """Clean up all generated movie .strm files and folders."""
        root_folder = settings.get("root_folder", "/VODS/Movies")
        
        logger.info("=" * 60)
        logger.info("VOD .strm Generator v%s", self.version)
        logger.info("Action: cleanup")
        logger.info("=" * 60)
        logger.info("")
        logger.info("⚠️  WARNING: This will delete ALL movie folders from Movies root!")
        logger.info("Root Folder: %s", root_folder)
        logger.info("")
        
        # Check if root folder exists
        if not os.path.exists(root_folder):
            logger.info("Root folder doesn't exist. Nothing to clean up.")
            return {
                "status": "ok",
                "message": "Root folder doesn't exist",
                "deleted_folders": 0,
                "deleted_files": 0
            }
        
        # Scan for folders with .strm or .nfo files
        logger.info("Scanning for movie folders...")
        folders_to_delete = []
        strm_files_found = 0
        nfo_files_found = 0
        
        try:
            for item in os.listdir(root_folder):
                item_path = os.path.join(root_folder, item)
                
                # Only process directories
                if os.path.isdir(item_path):
                    # Check if this folder contains .strm or .nfo files
                    has_plugin_files = False
                    for file in os.listdir(item_path):
                        if file.endswith('.strm'):
                            has_plugin_files = True
                            strm_files_found += 1
                        elif file.endswith('.nfo'):
                            nfo_files_found += 1
                    
                    if has_plugin_files:
                        folders_to_delete.append(item_path)
            
            logger.info("Found %d folders with plugin files", len(folders_to_delete))
            logger.info("  .strm files: %d", strm_files_found)
            logger.info("  .nfo files: %d", nfo_files_found)
            logger.info("")
            
            if len(folders_to_delete) == 0:
                logger.info("No movie folders found. Nothing to delete.")
                return {
                    "status": "ok",
                    "message": "No .strm files found",
                    "deleted_folders": 0,
                    "deleted_files": 0
                }
            
            # Show what will be deleted
            logger.info("Folders to be deleted:")
            logger.info("-" * 60)
            for idx, folder in enumerate(folders_to_delete[:10], 1):  # Show first 10
                logger.info("  [%d] %s", idx, os.path.basename(folder))
            
            if len(folders_to_delete) > 10:
                logger.info("  ... and %d more folders", len(folders_to_delete) - 10)
            
            logger.info("")
            logger.info("Proceeding with deletion...")
            logger.info("")
            
            # Delete folders
            deleted_folders = 0
            deleted_strm = 0
            deleted_nfo = 0
            errors = 0
            
            for idx, folder_path in enumerate(folders_to_delete, 1):
                try:
                    # Count files before deletion
                    strm_count = sum(1 for f in os.listdir(folder_path) if f.endswith('.strm'))
                    nfo_count = sum(1 for f in os.listdir(folder_path) if f.endswith('.nfo'))
                    
                    # Delete the entire folder
                    import shutil
                    shutil.rmtree(folder_path)
                    
                    deleted_folders += 1
                    deleted_strm += strm_count
                    deleted_nfo += nfo_count
                    
                    # Log progress every 50 folders
                    if idx % 50 == 0 or idx == len(folders_to_delete):
                        logger.info("Progress: %d/%d folders deleted", idx, len(folders_to_delete))
                    
                except Exception as e:
                    logger.error("Failed to delete %s: %s", folder_path, e)
                    errors += 1
            
            logger.info("")
            logger.info("=" * 60)
            logger.info("CLEANUP SUMMARY:")
            logger.info("  Folders deleted:    %d", deleted_folders)
            logger.info("  .strm deleted:      %d", deleted_strm)
            logger.info("  .nfo deleted:       %d", deleted_nfo)
            logger.info("  Errors:             %d", errors)
            logger.info("=" * 60)
            logger.info("")
            logger.info("Cleanup complete!")
            
            summary_msg = f"Deleted {deleted_folders} folders ({deleted_strm} .strm"
            if deleted_nfo > 0:
                summary_msg += f" + {deleted_nfo} .nfo"
            summary_msg += " files)"
            
            return {
                "status": "ok",
                "message": summary_msg,
                "deleted_folders": deleted_folders,
                "deleted_strm": deleted_strm,
                "deleted_nfo": deleted_nfo,
                "errors": errors
            }
            
        except Exception as e:
            logger.error("Cleanup failed: %s", e)
            return {
                "status": "error",
                "message": f"Cleanup error: {e}"
            }
    
    def _cleanup_series(self, settings: Dict[str, Any], logger):
        """Clean up all generated series .strm files and folders."""
        series_root = settings.get("series_root_folder", "/VODS/Series")
        
        logger.info("=" * 60)
        logger.info("Series Cleanup")
        logger.info("=" * 60)
        logger.info("")
        logger.info("⚠️  WARNING: This will delete ALL series folders!")
        logger.info("Series Root: %s", series_root)
        logger.info("")
        
        if not os.path.exists(series_root):
            logger.info("Series root doesn't exist. Nothing to clean up.")
            return {"status": "ok", "message": "Series root doesn't exist", "deleted": 0}
        
        # Scan for series folders (they contain Season folders)
        logger.info("Scanning for series folders...")
        folders_to_delete = []
        strm_count = 0
        nfo_count = 0
        
        try:
            import shutil
            
            for item in os.listdir(series_root):
                item_path = os.path.join(series_root, item)
                
                if os.path.isdir(item_path):
                    # Check if has Season folders or .strm files
                    has_series_content = False
                    
                    for subitem in os.listdir(item_path):
                        subitem_path = os.path.join(item_path, subitem)
                        
                        # Check for Season folders
                        if os.path.isdir(subitem_path) and subitem.startswith("Season"):
                            has_series_content = True
                            # Count files in season folder
                            for file in os.listdir(subitem_path):
                                if file.endswith('.strm'):
                                    strm_count += 1
                                elif file.endswith('.nfo'):
                                    nfo_count += 1
                        
                        # Count tvshow.nfo
                        if subitem == "tvshow.nfo":
                            nfo_count += 1
                    
                    if has_series_content:
                        folders_to_delete.append(item_path)
            
            logger.info("Found %d series folders", len(folders_to_delete))
            logger.info("  .strm files: ~%d", strm_count)
            logger.info("  .nfo files: ~%d", nfo_count)
            logger.info("")
            
            if len(folders_to_delete) == 0:
                logger.info("No series folders found. Nothing to delete.")
                return {"status": "ok", "message": "No series found", "deleted": 0}
            
            # Show first 10
            logger.info("Series to be deleted:")
            logger.info("-" * 60)
            for idx, folder in enumerate(folders_to_delete[:10], 1):
                logger.info("  [%d] %s", idx, os.path.basename(folder))
            
            if len(folders_to_delete) > 10:
                logger.info("  ... and %d more", len(folders_to_delete) - 10)
            
            logger.info("")
            logger.info("Proceeding with deletion...")
            logger.info("")
            
            # Delete series folders
            deleted = 0
            errors = 0
            
            for idx, folder_path in enumerate(folders_to_delete, 1):
                try:
                    shutil.rmtree(folder_path)
                    deleted += 1
                    
                    if idx % 10 == 0 or idx == len(folders_to_delete):
                        logger.info("Progress: %d/%d deleted", idx, len(folders_to_delete))
                
                except Exception as e:
                    logger.error("Failed to delete %s: %s", folder_path, e)
                    errors += 1
            
            logger.info("")
            logger.info("=" * 60)
            logger.info("CLEANUP SUMMARY:")
            logger.info("  Series deleted: %d", deleted)
            logger.info("  Errors: %d", errors)
            logger.info("=" * 60)
            
            return {
                "status": "ok",
                "message": f"Deleted {deleted} series folders",
                "deleted": deleted,
                "errors": errors
            }
            
        except Exception as e:
            logger.error("Cleanup failed: %s", e)
            return {"status": "error", "message": f"Cleanup error: {e}"}
    
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
