import DaVinciResolveScript as dvr_script
import subprocess
import os
import time
import concurrent.futures
import logging
import signal
import sys
from typing import Dict, Set, List, Optional, Tuple, Any

# Configuration
class Config:
    # Processing settings
    MAX_WORKERS = min(os.cpu_count() or 4, 8)  # Cap at 8 to prevent overload
    FFMPEG_THREADS = 0  # 0 means auto
    POLL_INTERVAL = 1.0  # Increased for better system performance
    BATCH_SIZE = 5  # Reduced for more responsive processing

    # FFmpeg settings - Try hardware acceleration with fallback
    HWACCEL_OPTIONS = ['cuda', 'vaapi', 'qsv', 'none']  # Priority order
    PRESET = 'medium'  # Better balance of speed vs quality

    # Output settings
    OUTPUT_DIR = "/home/pater/converter/converted"
    REPLACE_IN_MEDIA_POOL = True

    # Performance optimizations
    CODEC_CACHE_SIZE = 500  # Reduced cache size
    SKIP_ALREADY_PROCESSED = True

    # Logging
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Ensure output directory exists
os.makedirs(Config.OUTPUT_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format=Config.LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class FFmpegHandler:
    def __init__(self):
        self.codec_cache: Dict[str, str] = {}
        self.working_hwaccel = self._detect_hwaccel()

    def _detect_hwaccel(self) -> str:
        """Detect working hardware acceleration."""
        for hwaccel in Config.HWACCEL_OPTIONS:
            if hwaccel == 'none':
                logger.info("Using software encoding")
                return 'none'

            try:
                # Test hardware acceleration
                test_cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                           '-hwaccel', hwaccel, '-f', 'null', '-']
                subprocess.run(test_cmd, capture_output=True, check=True, timeout=10)
                logger.info(f"Using hardware acceleration: {hwaccel}")
                return hwaccel
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue

        logger.warning("No hardware acceleration available, using software encoding")
        return 'none'

    def get_audio_codec(self, file_path: str) -> Optional[str]:
        """Get audio codec using ffprobe with caching."""
        if file_path in self.codec_cache:
            return self.codec_cache[file_path]

        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error', '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', file_path
            ], capture_output=True, text=True, check=True, timeout=5)

            codec = result.stdout.strip().lower()

            # Manage cache size
            if len(self.codec_cache) >= Config.CODEC_CACHE_SIZE:
                # Remove oldest entry
                oldest_key = next(iter(self.codec_cache))
                del self.codec_cache[oldest_key]

            self.codec_cache[file_path] = codec
            return codec

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            logger.error(f"FFprobe failed for {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during codec detection: {e}")
            return None

    def convert_audio(self, file_path: str, output_dir: str) -> Optional[str]:
        """Convert media file with optimized settings."""
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        new_file = os.path.join(output_dir, f"{base_name}_converted.mov")

        # Skip if output already exists
        if os.path.exists(new_file):
            logger.debug(f"Output already exists: {new_file}")
            return new_file

        # Build ffmpeg command
        cmd = ['ffmpeg', '-y']

        # Add hardware acceleration if available
        if self.working_hwaccel != 'none':
            cmd.extend(['-hwaccel', self.working_hwaccel])

        # Input and output settings
        cmd.extend([
            '-i', file_path,
            '-threads', str(Config.FFMPEG_THREADS),
            '-c:v', 'copy',  # Copy video stream for speed
            '-c:a', 'pcm_s16le',  # Convert audio to PCM
            '-avoid_negative_ts', 'make_zero',  # Fix potential timing issues
            new_file
        ])

        try:
            process = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            return new_file if os.path.exists(new_file) else None

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed for {file_path}: {e.stderr[:200]}...")
            # Clean up failed conversion
            if os.path.exists(new_file):
                os.remove(new_file)
            return None
        except Exception as e:
            logger.error(f"Unexpected error during conversion: {e}")
            return None

class ResolveMediaHandler:
    def __init__(self):
        self.resolve = None
        self.project = None
        self.media_pool = None
        self.root_folder = None
        self.processed_files: Set[str] = set()
        self.ffmpeg_handler = FFmpegHandler()

        # Load already converted files
        self._load_converted_files()

    def _load_converted_files(self):
        """Load list of already converted files to avoid reprocessing."""
        if Config.SKIP_ALREADY_PROCESSED and os.path.exists(Config.OUTPUT_DIR):
            for file in os.listdir(Config.OUTPUT_DIR):
                if file.endswith('_converted.mov'):
                    original_name = file.replace('_converted.mov', '')
                    self.processed_files.add(original_name)

    def initialize(self) -> bool:
        """Initialize connection to DaVinci Resolve."""
        try:
            self.resolve = dvr_script.scriptapp("Resolve")
            if not self.resolve:
                logger.error("Failed to connect to DaVinci Resolve")
                return False

            self.project = self.resolve.GetProjectManager().GetCurrentProject()
            if not self.project:
                logger.error("No active project found")
                return False

            self.media_pool = self.project.GetMediaPool()
            self.root_folder = self.media_pool.GetRootFolder()

            logger.info("Successfully connected to DaVinci Resolve")
            return True

        except Exception as e:
            logger.error(f"Error initializing Resolve connection: {e}")
            return False

    def get_clips_needing_conversion(self) -> List[Tuple[str, Any]]:
        """Get clips that need audio conversion."""
        try:
            clips = self.root_folder.GetClips()
            clips_to_convert = []

            for clip in clips.values():
                file_path = clip.GetClipProperty("File Path")
                if not file_path or not os.path.exists(file_path):
                    continue

                base_name = os.path.splitext(os.path.basename(file_path))[0]
                if base_name in self.processed_files:
                    continue

                # Check audio codec
                codec = self.ffmpeg_handler.get_audio_codec(file_path)
                if codec in ['aac', 'opus']:
                    clips_to_convert.append((file_path, clip))

            return clips_to_convert

        except Exception as e:
            logger.error(f"Error getting clips: {e}")
            return []

    def process_clip(self, file_path: str, clip: Any) -> bool:
        """Process a single clip."""
        try:
            base_name = os.path.splitext(os.path.basename(file_path))[0]

            # Get codec for logging
            codec = self.ffmpeg_handler.get_audio_codec(file_path)
            logger.info(f"⏳ Converting {codec.upper()} file: {base_name}")

            start_time = time.time()
            new_file = self.ffmpeg_handler.convert_audio(file_path, Config.OUTPUT_DIR)

            if not new_file:
                logger.error(f"❌ Conversion failed: {file_path}")
                return False

            # Replace in media pool if requested
            if Config.REPLACE_IN_MEDIA_POOL:
                try:
                    self.media_pool.DeleteClips([clip])
                    imported_clips = self.media_pool.ImportMedia([new_file])
                    logger.info(f"🔄 Replaced in media pool: {base_name}")
                except Exception as e:
                    logger.warning(f"Could not replace in media pool: {e}")

            # Mark as processed
            self.processed_files.add(base_name)

            duration = time.time() - start_time
            logger.info(f"✅ Converted in {duration:.1f}s: {base_name}")
            return True

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return False

def main():
    """Main monitoring loop."""
    handler = ResolveMediaHandler()
    if not handler.initialize():
        logger.error("Failed to initialize. Exiting.")
        return

    logger.info(f"🔍 Monitoring for AAC and OPUS files...")
    logger.info(f"Output directory: {Config.OUTPUT_DIR}")
    logger.info(f"Using {Config.MAX_WORKERS} worker threads")

    # Setup graceful shutdown
    shutdown_event = threading.Event()
    def signal_handler(sig, frame):
        logger.info("\n🛑 Shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while not shutdown_event.is_set():
            clips_to_process = handler.get_clips_needing_conversion()

            if clips_to_process:
                logger.info(f"Found {len(clips_to_process)} clips to process")

                with concurrent.futures.ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
                    futures = {
                        executor.submit(handler.process_clip, file_path, clip): file_path
                        for file_path, clip in clips_to_process[:Config.BATCH_SIZE]
                    }

                    for future in concurrent.futures.as_completed(futures, timeout=300):
                        file_path = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"Processing failed for {file_path}: {e}")

            # Wait before next check
            time.sleep(Config.POLL_INTERVAL)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Monitoring stopped")

if __name__ == "__main__":
    import threading
    main()
