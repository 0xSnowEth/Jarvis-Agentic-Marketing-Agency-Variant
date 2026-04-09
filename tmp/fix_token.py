from client_store import get_client_store
from dotenv import load_dotenv

load_dotenv()
store = get_client_store()
cdata = store.get_client("Forge House Fitness Kuwait")
if cdata:
    tok = cdata.get("meta_access_token", "")
    if len(tok) > 400 and "ZDZDEAA" in tok:
        # Split it and keep the second part (the new one)
        parts = tok.split("ZDZDEAA")
        if len(parts) == 2:
            new_tok = "EAA" + parts[1]
            if new_tok.endswith("."):
                new_tok = new_tok[:-1]
            cdata["meta_access_token"] = new_tok
            store.save_client("Forge House Fitness Kuwait", cdata)
            print("Successfully fixed concatenated token!")
        else:
            print("Couldn't split cleanly.")
    else:
        print(f"Token length {len(tok)}, not cleanly concatenated. Ends with {tok[-10:]}")
else:
    print("Client not found.")
