import requests
import json

payload = {
    "client_name": "Test Burger",
    "raw_context": "We are a new burger joint in Dubai. We sell smashed burgers and normal fries. We want to be cool and appealing to teens."
}

res = requests.post("http://localhost:8000/api/synthesize-client", json=payload)
print(res.status_code)
try:
    print(json.dumps(res.json(), indent=2))
except Exception as e:
    print(res.text)
