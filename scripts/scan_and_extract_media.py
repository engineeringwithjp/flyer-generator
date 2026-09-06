"""Analyzes SD card drone media (/Volumes/Untitled/DCIM/101MEDIA) and extracts best candidate frames for flyers."""

import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CLIENTS_DIR


def get_video_duration(video_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        return float(out)
    except Exception:
        return 0.0

def extract_frame_at_time(video_path: str, timestamp: float, output_path: str) -> bool:
    cmd = [
        "ffmpeg", "-y", "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    except Exception:
        return False

def calculate_image_metrics(img_path: str) -> dict:
    """Calculates sharpness approximation, brightness, and color spread."""
    try:
        with Image.open(img_path) as img:
            w, h = img.size
            gray = img.convert("L")
            stat = ImageStat.Stat(gray)
            mean_brightness = stat.mean[0]
            rms = stat.rms[0]

            # Fast edge contrast check (downsampled)
            small = gray.resize((200, 200))
            # Calculate simple gradient variance
            pixels = list(small.getdata())
            diffs = [abs(pixels[i] - pixels[i-1]) for i in range(1, len(pixels))]
            sharpness_score = sum(diffs) / len(diffs)

            return {
                "width": w,
                "height": h,
                "brightness": mean_brightness,
                "contrast": rms,
                "sharpness": sharpness_score
            }
    except Exception as e:
        return {"error": str(e)}

def main():
    media_dir = Path("/Volumes/Untitled/DCIM/101MEDIA")
    if not media_dir.exists():
        print(f"Error: {media_dir} not found. Is the SD card or drive mounted?")
        return

    output_dir = CLIENTS_DIR / "all-elite" / "photos" / "drone_media"
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "extracted_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    best_photos_dir = output_dir / "high_res_photos"
    best_photos_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning media directory: {media_dir}")

    files = [f for f in media_dir.iterdir() if not f.name.startswith(".")]
    jpgs = sorted([f for f in files if f.suffix.upper() in [".JPG", ".JPEG", ".DNG"]])
    mp4s = sorted([f for f in files if f.suffix.upper() in [".MP4", ".MOV"]])

    print(f"Found {len(jpgs)} still photos and {len(mp4s)} video clips.\n")

    # 1. Process and evaluate still photos
    print("--- 1. EVALUATING HIGH-RES STILL DRONE PHOTOS ---")
    photo_evals = []
    for j in jpgs:
        metrics = calculate_image_metrics(str(j))
        sz_mb = j.stat().st_size / (1024 * 1024)
        photo_evals.append((j, sz_mb, metrics))
        # Copy to client photos
        dest = best_photos_dir / j.name
        if not dest.exists():
            import shutil
            shutil.copy2(j, dest)
        print(f"  📸 {j.name}: {metrics.get('width')}x{metrics.get('height')} | Sharpness: {metrics.get('sharpness', 0):.1f} | {sz_mb:.1f}MB")

    # 2. Sample and extract best frames from key video clips
    print("\n--- 2. SAMPLING & EXTRACTING BEST FRAMES FROM 4K VIDEOS ---")
    # Sample every 5th video or videos with substantial file size (> 100MB)
    selected_videos = [v for v in mp4s if v.stat().st_size > 100 * 1024 * 1024]
    if not selected_videos:
        selected_videos = mp4s[:20]

    # Limit to 15 representative videos across different flight sessions
    step = max(1, len(selected_videos) // 15)
    sampled_videos = selected_videos[::step][:15]

    extracted_candidates = []

    for v in sampled_videos:
        dur = get_video_duration(str(v))
        if dur < 2.0:
            continue

        # Sample at 25%, 50%, and 75%
        timestamps = [dur * 0.25, dur * 0.50, dur * 0.75]
        best_frame_for_vid = None
        best_score = -1

        for i, t in enumerate(timestamps, start=1):
            temp_frame_path = frames_dir / f"{v.stem}_frame_{i}.jpg"
            success = extract_frame_at_time(str(v), t, str(temp_frame_path))
            if success:
                metrics = calculate_image_metrics(str(temp_frame_path))
                sharpness = metrics.get("sharpness", 0)
                brightness = metrics.get("brightness", 0)

                # Prioritize good lighting (brightness 70-190) and high sharpness
                quality_score = sharpness
                if 80 <= brightness <= 180:
                    quality_score += 15

                if quality_score > best_score:
                    best_score = quality_score
                    best_frame_for_vid = (temp_frame_path, metrics, dur, t)

        if best_frame_for_vid:
            path, metrics, dur, t = best_frame_for_vid
            sz_mb = path.stat().st_size / (1024 * 1024)
            print(f"  🎬 {v.name} (dur: {dur:.1f}s): Extracted best frame at {t:.1f}s | {metrics.get('width')}x{metrics.get('height')} | Score: {best_score:.1f}")
            extracted_candidates.append(path)

    print(f"\nExtracted {len(extracted_candidates)} top candidate frames to: {frames_dir}")
    print(f"Copied {len(jpgs)} high-res still photos to: {best_photos_dir}")

if __name__ == "__main__":
    main()
