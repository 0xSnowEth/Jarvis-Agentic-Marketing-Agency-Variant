import requests
from client_store import get_client_store
from dotenv import load_dotenv

load_dotenv()
store = get_client_store()
cdata = store.get_client("Forge House Fitness Kuwait")
if cdata:
    tok = cdata.get("meta_access_token", "")
    print(f"Current token ends with: {tok[-10:]}")
    res = requests.get(f"https://graph.facebook.com/v19.0/me?access_token={tok}", timeout=5).json()
    print(f"Meta says: {res}")
else:
    print("Client not found.")
