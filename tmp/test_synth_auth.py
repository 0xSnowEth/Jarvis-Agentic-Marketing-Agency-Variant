import requests
import json
import os

payload = {
    "client_name": "Test Burger",
    "raw_context": "We are a new burger joint in Dubai. We sell smashed burgers and normal fries. We want to be cool and appealing to teens."
}

# The password in .env is Agency
cookies = {"jarvis_auth_token": "Agency"}
res = requests.post("http://localhost:8000/api/synthesize-client", json=payload, cookies=cookies)

print(f"Status Code: {res.status_code}")
try:
    print(json.dumps(res.json(), indent=2))
except Exception as e:
    print("Raw text response:")
    print(res.text)
