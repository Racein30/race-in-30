"""One-time setup: run this on your own computer to authorise your YouTube channel.

  pip install google-auth-oauthlib
  python get_youtube_token.py client_secret.json

A browser opens; pick the channel to post to and allow access. The script then
prints the three values to paste into your GitHub repo's secrets.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

path = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
flow = InstalledAppFlow.from_client_secrets_file(path, SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
info = json.load(open(path))
info = info.get("installed") or info.get("web")

print("\nAdd these as GitHub secrets (Settings > Secrets and variables > Actions):\n")
print(f"YT_CLIENT_ID      = {info['client_id']}")
print(f"YT_CLIENT_SECRET  = {info['client_secret']}")
print(f"YT_REFRESH_TOKEN  = {creds.refresh_token}")
