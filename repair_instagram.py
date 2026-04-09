import os
from PIL import Image
import io
from asset_store import get_asset_store

def repair_vault():
    print("Initiating surgical vault repair for fake JPEGs...")
    store = get_asset_store()
    
    # We target the Nasar_gym client specifically:
    client_id = "Nasar_gym"
    assets = store.list_assets(client_id)
    
    for a in assets:
        filename = a["filename"]
        if "free-photo" in filename:
            print(f"Found suspect file: {filename}")
            
            # Download the corrupt file from Supabase
            content = store.get_asset_content(client_id, filename)
            if not content:
                continue
            file_bytes, _ = content
            
            try:
                # Pillow will forcefully overwrite the WebP internal bytes
                img = Image.open(io.BytesIO(file_bytes))
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    alpha = img.convert('RGBA').split()[-1]
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=alpha)
                    img = bg
                else:
                    img = img.convert('RGB')
                
                rgb_bytes = io.BytesIO()
                img.save(rgb_bytes, format='JPEG', quality=95)
                new_bytes = rgb_bytes.getvalue()
                
                print(f"File repaired! Flattening internal WebP format into pure JPEG.")
                
                # Overwrite it safely back to Supabase
                store.delete_asset(client_id, filename)
                store.save_asset(client_id, filename, new_bytes)
                print(f"Successfully repaired {filename} in Supabase!")
                
            except Exception as e:
                print(f"Failed to process {filename}: {e}")

if __name__ == "__main__":
    repair_vault()
