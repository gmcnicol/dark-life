from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json, os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRETS", "./secrets/client_secret.json")
TOKEN_PATH = os.getenv("YOUTUBE_TOKEN", "./secrets/token.json")

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
creds = flow.run_local_server(port=0)  # opens browser; handles http://127.0.0.1:<port> callback
with open(TOKEN_PATH, "w") as f:
  f.write(creds.to_json())

youtube = build("youtube", "v3", credentials=creds)
print("Auth OK; token saved:", TOKEN_PATH)
