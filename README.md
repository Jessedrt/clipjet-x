# ClipJet — Telegram X + experimental YouTube video delivery

Telegram: [@ClipJetDownloaderBot](https://t.me/ClipJetDownloaderBot). Send a single public X post or YouTube watch/Shorts URL for media you are authorized to save. **Follow source-platform terms and copyright restrictions.** YouTube generally restricts downloads unless its service or the rights holder authorizes them.

## Existing bot

The Telegram webhook stays `https://clipjet-x.vercel.app/api/webhook`. The X route finds a direct public MP4. The YouTube route first attempts a small progressive MP4 with audio using `yt-dlp`. Serverless functions extract metadata only: ClipJet never downloads, merges, stores or uploads video bytes. Telegram is asked to fetch a verified HTTPS video URL with `sendVideo`. Telegram's remote-URL delivery is limited to small videos, and YouTube can challenge Vercel with an anti-bot verification request. A green deployment does **not** prove a successful video download.

## Optional hosted SocialKit API (short clips)

The [SocialKit synchronous YouTube Download API](https://docs.socialkit.dev/api-reference/youtube-download-api) is a configurable backup when the direct YouTube route is challenged or finds no compatible MP4. Its v1 endpoint is documented to return a temporary MP4 URL and limit files to 10 MB. We request 360p, require a reported file size of at most 10,000,000 bytes, validate the provider's documented S3 download bucket, and pass the resulting URL directly to Telegram. ClipJet never fetches the media itself. Large/long videos and some signed URLs may still fail Telegram delivery.

**Explicit opt-in, off by default:** Create your own SocialKit account, check that the provider permits your actual Telegram-bot usage, and configure the following **only in Vercel Production environment variables** (not GitHub or chat):

```env
SOCIALKIT_ACCESS_KEY=YOUR_OWN_KEY
SOCIALKIT_ENABLED=true
```

Do not enable it until ready to spend credits: the provider charges for successful operations at **1 credit per started minute up to 480p**; a small file can still have a long duration. Failed downloads do not consume credits according to the provider's documentation. We make at most **one** SocialKit download request per attempt; no automatic retries. The Free plan advertises 20 credits, so use a very short video you own or may download for initial testing, optionally set `BOT_OWNER_ID`, and check your account's usage. If you add a key but leave `SOCIALKIT_ENABLED=false`, the bot **will not call SocialKit**. A key is never sent to Telegram users. Save variables and redeploy Vercel; the Telegram webhook does not need to be registered again.

This is a **prepared integration, not a live tested download** until you supply an account key and verify the provider's terms permit the particular use. API access from SocialKit does not grant permission from YouTube or rights holders to download arbitrary content. Do not send account passwords, browser cookies or keys in chat.

The hosted v2 API supports larger files via asynchronous jobs, but ClipJet has **not implemented a durable queue or job polling**, so it intentionally uses v1 for this initial short-video experiment. Use v2 only after adding durable job state, scheduled polling, duration-based spending caps and file-size/delivery checks.

## Optional self-hosted Cobalt fallback

An operator-owned or explicitly authorized [Cobalt instance](https://github.com/imputnet/cobalt/blob/main/docs/api.md) is also supported, but is **not configured** by default:

```env
COBALT_API_URL=https://YOUR-AUTHORIZED-COBALT-INSTANCE.example
COBALT_API_KEY=YOUR_INSTANCE_KEY_IF_REQUIRED
```

Use a real HTTPS domain at the instance origin without a path; the sample is not an actual service. Do not automate someone else's public Cobalt instance without consent. On direct YouTube extraction failure, an explicitly enabled SocialKit is tried first. If it fails and authorized Cobalt is configured, Cobalt is tried next. If neither is configured, the bot explains YouTube's challenge or missing MP4. Telegram must still be able to retrieve the returned URL.

## Configuration and verification

Retain `BOT_TOKEN` and `WEBHOOK_SECRET` in Vercel Production. `BOT_OWNER_ID` is recommended during testing. Keep all API keys off GitHub and out of chats. Re-deploy after adding environment variables and test a short, public video you own or are explicitly authorized to download. No external provider has been paid or activated automatically by these code changes.

```bash
python -m unittest discover -s tests -v
python -m compileall -q clipjet.py youtube_video.py cobalt_client.py socialkit_client.py telegram_api.py setup_webhook.py api/webhook.py
```

Tests mock network calls; neither tests nor Vercel health responses demonstrate that an actual YouTube-to-Telegram delivery worked.

References: [SocialKit v1 docs](https://docs.socialkit.dev/api-reference/youtube-download-api) · [SocialKit pricing](https://www.socialkit.dev/pricing) · [Telegram Bot API](https://core.telegram.org/bots/api) · [YouTube developer policies](https://developers.google.com/youtube/terms/developer-policies) · [Vercel Python Functions](https://vercel.com/docs/functions/runtimes/python).
