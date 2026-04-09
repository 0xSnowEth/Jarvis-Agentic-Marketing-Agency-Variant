import json

with open("clients/Forge House Fitness Kuwait.json", "r", encoding="utf-8") as f:
    data = json.load(f)

tok = data.get("meta_access_token", "")
print(f"Token length in file: {len(tok)}")
print(f"Token begins: {tok[:20]}")
print(f"Token ends: {tok[-20:]}")
if "EAAlvVt24vMYBRA3ZCpm" in tok:
    print("TOKEN CONTAINS THE SECOND PART")
else:
    print("TOKEN DOES NOT CONTAIN THE SECOND PART")
