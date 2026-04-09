import os

path = '/home/snowaflic/agents/asset_store.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# I want to add poster generation to _normalize_video_upload
poster_logic = """
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
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
        if result.returncode != 0 or not os.path.exists(output_path):
            detail = (result.stderr or result.stdout or "").strip()[:300]
            raise RuntimeError(detail or "ffmpeg failed to faststart remux the uploaded video.")

        # INSTANT POSTER GENERATION
        poster_path = output_path + ".jpg"
        poster_cmd = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:00.000",
            "-i", source_path,
            "-vframes", "1",
            "-q:v", "2",
            poster_path
        ]
        subprocess.run(poster_cmd, capture_output=True, timeout=10)
        
        with open(output_path, "rb") as f:
            normalized_bytes = f.read()
            
        poster_bytes = b""
        if os.path.exists(poster_path):
            with open(poster_path, "rb") as pf:
                poster_bytes = pf.read()

        stem = os.path.splitext(str(filename or "").strip() or "video")[0]
        normalized_filename = f"{stem}.mp4"
        metadata = {
            "normalized_for_meta": True,
            "original_filename": filename,
            "original_extension": extension,
            "normalization_pipeline": "ffmpeg_faststart_remux",
            "has_poster": True,
            "poster_bytes": poster_bytes
        }
        return normalized_filename, normalized_bytes, metadata
"""

# Replace the block from `command = [` to `return normalized_filename, normalized_bytes, metadata`
import re
block_search = re.compile(r'        command = \[.*?return normalized_filename, normalized_bytes, metadata', re.DOTALL)
text = re.sub(block_search, poster_logic.strip(), text)

# Now we must update `JsonAssetStore` to save the poster if it exists
json_save_search = """        path = self._asset_path(client_id, filename)
        with open(path, "wb") as f:
            f.write(file_bytes)"""
json_save_replace = """        path = self._asset_path(client_id, filename)
        with open(path, "wb") as f:
            f.write(file_bytes)
            
        poster_bytes = normalization_meta.get("poster_bytes")
        if poster_bytes:
            with open(path + ".jpg", "wb") as pf:
                pf.write(poster_bytes)"""
text = text.replace(json_save_search, json_save_replace)

# We must update `SupabaseAssetStore` to upload the poster too
supabase_save_search = """        self._upload_bytes(storage_path, filename, file_bytes, mime_type)"""
supabase_save_replace = """        self._upload_bytes(storage_path, filename, file_bytes, mime_type)
        poster_bytes = normalization_meta.get("poster_bytes")
        if poster_bytes:
            self._upload_bytes(storage_path + ".jpg", filename + ".jpg", poster_bytes, "image/jpeg")"""
text = text.replace(supabase_save_search, supabase_save_replace)

# Cleanup poster_bytes from metadata so it doesn't get saved into the DB json payload
poster_cleanup_search = """        return {
            "filename": filename,
            "kind": detect_media_kind(filename),"""
poster_cleanup_replace = """        if "poster_bytes" in normalization_meta:
            del normalization_meta["poster_bytes"]
            
        return {
            "filename": filename,
            "kind": detect_media_kind(filename),"""
text = text.replace(poster_cleanup_search, poster_cleanup_replace)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print("asset_store.py patched with poster generation!")
