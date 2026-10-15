"""Upload to YouTube with a stored OAuth refresh token (no browser needed)."""
from __future__ import annotations

import os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def upload(path: str, title: str, description: str, tags: list[str],
           privacy: str | None = None) -> str:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {"title": title[:100], "description": description[:4900],
                    "tags": tags, "categoryId": "17"},  # 17 = Sports
        "status": {"privacyStatus": privacy or os.environ.get("YT_PRIVACY", "public"),
                   "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(path, mimetype="video/mp4",
                                                        resumable=True, chunksize=-1))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]
