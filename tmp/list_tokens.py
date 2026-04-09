from client_store import get_client_store
from dotenv import load_dotenv

load_dotenv()
s = get_client_store()
for c in s.list_client_ids():
    tk = s.get_client(c).get('meta_access_token', '')
    print(c, len(tk), tk[-10:])
