import sys
import json
import logging
from client_store import get_supabase_service_client

logger = logging.getLogger(__name__)

def make_bucket_public(bucket_name="client-assets"):
    client = get_supabase_service_client()
    try:
        # In Supabase JS / Python SDK, we can update a bucket.
        resp = client.storage.update_bucket(bucket_name, public=True)
        print(f"Update response: {resp}")
        print("Successfully made bucket public!")
    except Exception as e:
        print(f"Failed to update bucket via SDK: {e}")

if __name__ == "__main__":
    make_bucket_public()
