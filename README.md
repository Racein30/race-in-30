# Race in 30: automated F1 data Shorts

After every Grand Prix and Sprint, this makes a 30-second vertical video from
official F1 timing data and posts it to your channel. It runs free on GitHub
Actions, so your computer doesn't need to be on.

**What each Short contains:** an animated position chart of the whole race,
lap counter, live leader banner, burned-in captions, a British AI voiceover,
and a podium card at the end. Title, description and tags are written
automatically from the result.

**No broadcast footage is used**, so there's nothing for Content ID to claim.

## How it runs

Every 3 hours GitHub checks the F1 calendar. When a race or sprint finished
more than ~2 hours ago and hasn't been posted, it:

1. downloads lap-by-lap timing with FastF1
2. works out the story (winner, lead changes, biggest gainer, retirements, fastest lap)
3. writes the script (template, or Claude if you add an API key)
4. generates the voiceover and caption timings (Edge TTS, free)
5. renders the 1080x1920 video
6. uploads it as a Short and records it in `state.json` so it never posts twice

Videos are also kept for 14 days under the workflow run's Artifacts.

## One-time setup

Already done: Google Cloud project, YouTube Data API, sign-in screen, OAuth client
(Web application, redirect `https://developers.google.com/oauthplayground`), this repo.

### Get your YouTube refresh token (no software needed)
1. Open https://developers.google.com/oauthplayground
2. Click the gear icon (top right), tick **Use your own OAuth credentials**, and paste
   your **Client ID** and **Client secret**.
3. In the box under the API list on the left, type
   `https://www.googleapis.com/auth/youtube.upload` and click **Authorize APIs**.
4. Sign in with the channel's Google account, choose the **Race in 30** channel, and allow.
5. Click **Exchange authorization code for tokens** and copy the **Refresh token**.

(Alternative for developers: `python get_youtube_token.py client_secret.json`.)

### Add the secrets to GitHub
Repo **Settings > Secrets and variables > Actions > New repository secret**:
`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
Optional: secret `ANTHROPIC_API_KEY`, variable `CHANNEL_HANDLE` (e.g. `@racein30`).

### Test it
**Actions > F1 Shorts > Run workflow**, mode `sample`, then download the video from the
run's Artifacts.

### Get uploads approved for public posting
YouTube locks videos uploaded through new, unaudited API projects to **private**.
Submit the free **YouTube API Services audit** form describing this as a tool that posts
your own original data-visualisation videos to your own channel. Until it's approved,
flip each video to public in YouTube Studio.

## Running locally
```
pip install -r requirements.txt     # plus ffmpeg on your system
python -m f1shorts.main --sample --no-voice          # offline preview
python -m f1shorts.main --race 2026 18 Race --no-upload   # any past race
```

## Customising
- Voice: set `TTS_VOICE` (e.g. `en-US-GuyNeural`, `en-AU-WilliamNeural`) and `TTS_RATE`.
- Look: colours and layout are at the top of `f1shorts/render.py`.
- Script wording: `template_script()` in `f1shorts/story.py`.

## Staying on the right side of YouTube and F1
- Content is generated from timing data, which is why it's original. Don't add
  broadcast clips, F1 logos or copyrighted music.
- The description says it's an unofficial fan channel; keep that.
- YouTube refuses monetisation for mass-produced, repetitive content. One Short per
  session, each with a different race story, is fine. Adding more formats later
  (qualifying battles, speed-trace duels) makes the channel stronger.
