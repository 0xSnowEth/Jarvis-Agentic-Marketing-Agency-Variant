import os

path = '/home/snowaflic/agents/asset_store.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the slow ffmpeg command with the blazing fast remux
slow_cmd = """        command = [
            "ffmpeg",
            "-y",
            "-i",
            source_path,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-profile:a",
            "aac_low",
            "-b:a",
            "128k",
            output_path,
        ]"""

fast_cmd = """        # Blazing fast remux to move moov atom to start for instant browser rendering
        command = [
            "ffmpeg",
            "-y",
            "-i",
            source_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_path,
        ]"""

text = text.replace(slow_cmd, fast_cmd)
text = text.replace('normalization_pipeline": "ffmpeg_h264_aac_lc"', 'normalization_pipeline": "ffmpeg_faststart_remux"')

# Also uncomment the call to normalize in JsonAssetStore/SupabaseAssetStore that I disabled earlier
text = text.replace('# filename, file_bytes, normalization_meta = _normalize_video_upload(filename, file_bytes)', 'filename, file_bytes, normalization_meta = _normalize_video_upload(filename, file_bytes)')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Asset store patched for high speed faststart remux.")
