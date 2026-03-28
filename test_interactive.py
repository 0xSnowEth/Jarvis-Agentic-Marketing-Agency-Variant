import os
import sys
import json
from dotenv import load_dotenv

sys.path.append("/Ubuntu/home/snowaflic/agents")
os.chdir("/Ubuntu/home/snowaflic/agents")
load_dotenv()

from webhook_server import send_interactive_whatsapp_approval, get_agency_config

phone = get_agency_config().get("owner_phone", "")
if not phone:
    print("No owner phone found!")
    sys.exit(1)

print(f"Sending interactive test to {phone}...")
send_interactive_whatsapp_approval(phone, "TEST_ID_123", "🍔 *Burger Grillz* - New Post Drafted!\n\nCaption: Enjoy our new double cheese burger today!")
print("Done!")
