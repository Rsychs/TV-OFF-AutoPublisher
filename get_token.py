import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

client_file = Path("client_secret.json")
if not client_file.exists():
    raise SystemExit("Place your Google OAuth Desktop client JSON in client_secret.json")

flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
credentials = flow.run_local_server(port=0, prompt="consent")
Path("token.json").write_text(credentials.to_json(), encoding="utf-8")
print("Saved token.json. Keep it private; do not commit it.")
