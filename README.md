# 🎬 DaVinci Resolve Audio Converter

A Python automation tool that monitors your DaVinci Resolve Media Pool and automatically converts AAC and OPUS audio files to PCM format for better compatibility and performance.

## ✨ Features

- 🔍 **Automatic Detection**: Monitors DaVinci Resolve Media Pool for AAC and OPUS audio files
- ⚡ **Hardware Acceleration**: Automatically detects and uses CUDA, VAAPI, or QSV acceleration when available
- 🔄 **Smart Conversion**: Converts audio to PCM 16-bit LE while preserving video streams
- 🚀 **Multi-threaded Processing**: Processes multiple files simultaneously for faster conversion
- 💾 **Smart Caching**: Avoids reprocessing already converted files
- 🔄 **Media Pool Integration**: Optionally replaces original clips in Media Pool with converted versions
- 📊 **Real-time Monitoring**: Continuously monitors for new files added to your project
- 🛡️ **Robust Error Handling**: Graceful handling of errors and edge cases

## 📋 Requirements

- **Python 3.7+**
- **FFmpeg** (with ffprobe)
- **DaVinci Resolve** (Free or Studio version)
- **Linux/macOS/Windows** (tested on Linux)

## 🚀 Installation

### 1. Install System Dependencies

#### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install python3 python3-pip ffmpeg
```

#### CentOS/RHEL/Fedora:
```bash
sudo dnf install python3 python3-pip ffmpeg
```


### 2. Setup DaVinci Resolve Scripting

#### Find Your Python Version:
```bash
python3 --version
# Example output: Python 3.13.5
```

#### Create Symbolic Link:
Replace `3.13` with your Python version:

```bash
sudo ln -s /opt/resolve/Developer/Scripting/Modules/DaVinciResolveScript.py /usr/lib/python3.13/site-packages/DaVinciResolveScript.py
```

#### Set Environment Variable:
```bash
echo 'export PYTHONPATH=$PYTHONPATH:/opt/resolve/Developer/Scripting/Modules' >> ~/.bashrc
source ~/.bashrc
```

### 3. Enable Resolve Scripting

In DaVinci Resolve:
1. Open **Preferences** → **System** → **General**
2. Enable ✅ **"External scripting using"**
3. Select **"Local"**
4. Restart DaVinci Resolve

### 4. Download the Script

```bash
git clone https://github.com/paterkleomenis/resolve-media-converter.git
cd resolve-media-converter
```

## 🎯 Usage

### 1. Start DaVinci Resolve
- Open DaVinci Resolve
- Create or load a project
- Add media files to your Media Pool

### 2. Run the Converter
```bash
python3 script.py
```

### 3. Monitor the Output
The script will display real-time status updates:
```
2024-01-15 10:30:45 - INFO - 🔍 Monitoring for AAC and OPUS files...
2024-01-15 10:30:45 - INFO - Output directory: /home/pater/converter/converted
2024-01-15 10:30:45 - INFO - Using hardware acceleration: cuda
2024-01-15 10:30:46 - INFO - ⏳ Converting AAC file: video_sample
2024-01-15 10:30:48 - INFO - ✅ Converted in 2.1s: video_sample
2024-01-15 10:30:48 - INFO - 🔄 Replaced in media pool: video_sample
```

### 4. Stop the Script
Press `Ctrl+C` to stop monitoring safely.

## ⚙️ Configuration

Edit the `Config` class in `script.py` to customize behavior:

```python
class Config:
    # Processing settings
    MAX_WORKERS = min(os.cpu_count() or 4, 8)  # Number of parallel conversions
    POLL_INTERVAL = 1.0  # How often to check for new files (seconds)
    BATCH_SIZE = 5  # Number of files to process simultaneously

    # Output settings
    OUTPUT_DIR = "/home/pater/converter/converted"  # Where to save converted files
    REPLACE_IN_MEDIA_POOL = True  # Replace original clips in Media Pool

    # FFmpeg settings
    PRESET = 'medium'  # FFmpeg preset: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow

    # Performance
    SKIP_ALREADY_PROCESSED = True  # Skip files that were already converted
    CODEC_CACHE_SIZE = 500  # Number of codec detections to cache

    # Logging
    LOG_LEVEL = logging.INFO  # DEBUG, INFO, WARNING, ERROR
```

## 📁 Output Structure

Converted files are saved with the naming pattern:
```
/home/pater/converter/converted/
├── original_filename_converted.mov
├── another_file_converted.mov
└── ...
```

## 🎛️ Supported Audio Codecs

The script automatically detects and converts:
- **AAC** → PCM 16-bit LE
- **OPUS** → PCM 16-bit LE

All other audio codecs are ignored.

## 🏃‍♂️ Performance Features

### Hardware Acceleration
The script automatically detects and uses:
- **CUDA** (NVIDIA GPUs)
- **VAAPI** (Intel/AMD on Linux)
- **QSV** (Intel Quick Sync)
- **Software encoding** (fallback)

### Smart Processing
- **Codec Caching**: Remembers audio codec information to avoid repeated detection
- **Skip Processed Files**: Maintains a cache of already converted files
- **Batch Processing**: Processes multiple files simultaneously
- **Optimized FFmpeg Settings**: Uses fast presets and stream copying where possible

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. Areas for improvement:

- Support for additional codecs
- Timeline clip replacement (not just Media Pool)
- GUI interface
- Configuration file support
- Enhanced error recovery

## 📄 License

This project is open source. Feel free to use, modify, and distribute.

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Enable debug logging for more details
3. Open an issue on GitHub with:
   - Your operating system
   - Python version
   - DaVinci Resolve version
   - Error messages or logs
