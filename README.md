# ClipJet X — Vercel + Telegram webhook MVP

A **separate** X/Twitter-only Telegram bot for [@ClipJetDownloaderBot](https://t.me/ClipJetDownloaderBot). Paste one ordinary `https://x.com/username/status/123...` link. ClipJet extracts public metadata with `yt-dlp`, chooses a direct X-hosted progressive `.mp4`, and asks Telegram to fetch that HTTPS media URL using `sendVideo` — **no video bytes pass through Vercel**.

**This is a tested code starter, not a deployed service.** Live X extraction and remote Telegram fetches have not been tested. X can change its APIs and deny extraction; private, restricted, subscription-only, DRM-protected and login-required videos aren't supported. Some media URLs cannot be fetched by Telegram, or may exceed limits. Only download videos you own or have permission to save, and comply with applicable platform terms.

## Launch on Vercel

1. Make a new GitHub repo, e.g. `clipjet-x`, **separate from AUREX**. Upload the *contents* of this directory to the repo root (include `api/webhook.py` and `vercel.json`). Do not upload `.env` or any token. The included `.gitignore` prevents ordinary commits of `.env`.
2. Go to [Vercel → Add New Project](https://vercel.com/new) and import that GitHub repository; set Framework Preset to **Other**, root directory to `/`. Don't point it at your AUREX repository.
3. In Vercel Project → Settings → Environment Variables, create these for **Production**:
   - `BOT_TOKEN`: the **replacement** Telegram bot token you generated after the old one was exposed. Never send it in chat or commit it.
   - `WEBHOOK_SECRET`: locally generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and enter the value in Vercel. Must be 16+ letters/digits/_/-. It is sent and checked using Telegram's secret webhook header.
   - `BOT_OWNER_ID` (optional, strongly recommended during first tests): your Telegram numeric user ID.
4. Deploy and verify `https://YOUR-PROJECT.vercel.app/api/webhook` returns `{"service":"clipjet-x","status":"ready"}`. **GET health doesn't prove the bot token, Telegram API, X extraction, or video delivery.** Vercel's account-level build restriction may prevent deployment until it expires.
5. On your **own computer**, copy `.env.example` to `.env`; set the *same* replacement `BOT_TOKEN`, `WEBHOOK_SECRET`, and production `APP_URL` (no `/api/webhook` suffix). Install requirements (`python -m pip install -r requirements.txt`), then run `python setup_webhook.py`. This registers Telegram's webhook to Vercel; `python setup_webhook.py --info` shows its status. **Don't set the webhook until the production function and both secrets are in place.** Don't have a polling bot running simultaneously.
6. Open [ClipJet](https://t.me/ClipJetDownloaderBot), send `/start`, then try a short, public X video post you own or may download. Check Vercel runtime logs if there are errors.

## Technical design

```
Telegram POST -> /api/webhook (verify X-Telegram-Bot-Api-Secret-Token)
 -> validate x.com/twitter.com post link and canonicalize it
 -> yt-dlp metadata only (no download, no cookies)
 -> select trusted video.twimg.com HTTPS .mp4, prefer <= 720p and <= 18 MB when estimable
 -> Telegram sendVideo with the MP4 URL (Telegram fetches the video)
```

This avoids Vercel Functions' **4.5 MB response body limit**, but **Telegram URL sending is limited to 20 MB for videos** (standard Bot API). X's CDN may reject Telegram's request. Estimated/unknown sizes can be inaccurate; an error message is shown if Telegram fails. `yt-dlp` does not guarantee X extraction will always work, and syndication may omit posts.

## Security and limitations

- Only specific HTTPS X/Twitter hosts and numeric `/status/<id>` links; rejects user info, unexpected ports, extra URL content and lookalike domains. Metadata-only extraction avoids storing user files. The final direct-media URL must use exactly `video.twimg.com` and end in `.mp4`. CDN redirects are subsequently handled by **Telegram**, not Vercel; the source cannot be fully controlled by this code.
- Telegram webhook requests require `WEBHOOK_SECRET`. Bot token is read only from server environment; no real secrets in this repository.
- Best-effort 20-second per-user cooldown and update de-dup use **per-instance RAM only**. Vercel may start other instances or restart, so this is **not global rate limiting or durable idempotency**. Keep `BOT_OWNER_ID` set until you add shared rate limits and durable state. An asynchronous job queue is recommended for heavier use because Telegram may retry slow webhook requests.
- One short video only, no quality buttons, no login/cookies, no proxying, no FFmpeg, no file uploads, no guaranteed delivery and no 24/7 availability guarantee. Large/segmented videos require a separate worker. Do not use this as a mass downloader.

## Run offline checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q clipjet.py telegram_api.py setup_webhook.py api/webhook.py
```

Useful references: [Telegram Bot API](https://core.telegram.org/bots/api) · [Vercel Python Functions](https://vercel.com/docs/functions/runtimes/python) · [Vercel limits](https://vercel.com/docs/functions/limitations).
