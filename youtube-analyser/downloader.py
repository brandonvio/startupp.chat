#!/usr/bin/env python3
"""
simple_yt_fetch.py
Download a YouTube video and its metadata JSON into ./downloads/<videoid>/.

Usage:
  python simple_yt_fetch.py dQw4w9WgXcQ
"""

import sys
import json
from pathlib import Path
import yt_dlp


def progress(d):
    if d.get("status") == "downloading":
        pct = (d.get("_percent_str") or "").strip()
        spd = (d.get("_speed_str") or "").strip()
        eta = (d.get("_eta_str") or "").strip()
        print(f"\r{pct:>6} {spd:>10} ETA {eta:>6}", end="", flush=True)
    elif d.get("status") == "finished":
        print("\nMerging…", flush=True)


def main():
    if len(sys.argv) != 2:
        print("Usage: python simple_yt_fetch.py <VIDEO_ID>")
        sys.exit(1)

    vid = sys.argv[1].strip()
    url = f"https://www.youtube.com/watch?v={vid}"

    out_dir = Path("downloads") / vid
    out_dir.mkdir(parents=True, exist_ok=True)

    # Force filenames to <videoid>.<ext> in ./downloads/<videoid>/
    base = str(out_dir / vid)

    ydl_opts = {
        # Best video+audio, remux to MP4 when needed
        "format": "bv*+ba/best",
        "merge_output_format": "mp4",
        "outtmpl": {"default": base + ".%(ext)s"},
        # Keep it lean: only the media file (no thumbs, subs, etc.)
        "writesubtitles": False,
        "writeautomaticsub": False,
        "writethumbnail": False,
        "writeinfojson": False,  # we'll write our own <videoid>.json
        "skip_download": False,
        "progress_hooks": [progress],
        "retries": 5,
        "fragment_retries": 5,
        "continuedl": True,
        "overwrites": False,
        "quiet": False,
        "no_warnings": False,
        "concurrent_fragment_downloads": 5,
    }

    # Download the video, capture metadata, then write metadata JSON ourselves
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Persist a clean metadata JSON as <videoid>.json alongside the video
    meta_path = out_dir / f"{vid}.json"
    # Use ensure_ascii=False to preserve unicode; indent for readability
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2, default=str)

    # Print the final media path (mp4 or best available ext)
    # ydl.prepare_filename(info) would give us the actual name, but we forced base.
    print(f"Saved video to: {next(out_dir.glob(vid + '.*'))}")
    print(f"Saved metadata to: {meta_path}")


if __name__ == "__main__":
    main()
