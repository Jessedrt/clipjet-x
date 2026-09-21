# ClipJet — Telegram X + YouTube downloader (best effort)

Telegram bot: [@ClipJetDownloaderBot](https://t.me/ClipJetDownloaderBot). Send exactly one public X/Twitter post URL, YouTube watch/Shorts/live URL or `youtu.be` link. The bot attempts to find one progressive MP4 with audio that Telegram can retrieve directly. **Use only media you are authorized to save and follow platform terms.** In particular, YouTube generally restricts downloading unless its service or the applicable rights holders authorize it.

## Status and architecture

The bot runs on Vercel at `https://clipjet-x.vercel.app/api/webhook`, using the existing Telegram webhook. X and YouTube URL routing share the same Telegram handler, with separate strict validators and media selectors. `yt-dlp` extracts public metadata only; Vercel never downloads, proxies, merges, stores or uploads video bytes. The bot asks Telegram to fetch a remote HTTPS MP4 with `sendVideo`.

- X accepts canonical HTTPS x.com/twitter.com post links; videos must be direct `video.twimg.com` MP4s.
- YouTube accepts HTTPS `youtube.com/watch?v=...`, `/shorts/...`, `/live/...`, and `youtu.be/...` links with exactly one 11-character video ID. It accepts only HTTPS `*.googlevideo.com/videoplayback` MP4 video+audio formats. It will **not** stitch adaptive streams or extract private/age-restricted/DRM content.
- The bot chooses a format estimated under 18 MB to allow headroom under Telegram's 20 MB URL-fetch limit. File sizes can be wrong or absent and Telegram may reject a CDN URL. Videos over the limit, video-only YouTube streams, live feeds without a progressive MP4, and segmented formats aren't supported.
- **YouTube is experimental:** since late 2025, `yt-dlp` needs a supported external JavaScript runtime and its EJS companion for full YouTube extraction. `yt-dlp[default]` provides EJS, but a supported runtime such as Deno must also be available in the function environment. This deployment has not been verified to provide one; YouTube may deny extraction and can refuse Telegram's server-side URL fetch. No successful real YouTube video delivery is claimed.
- `BOT_OWNER_ID` is recommended during initial tests. Per-instance 20-second cooldown and dedup are not distributed; high-traffic production use needs durable state and a queue.

## Configuration

In Vercel Production environment variables, set `BOT_TOKEN` and `WEBHOOK_SECRET` (16-256 ASCII letters/digits/underscore/hyphen). Do not post real values in chat or commit them. The Telegram webhook URL is `https://clipjet-x.vercel.app/api/webhook`; register/re-register using `setup_webhook.py` with the same token and secret (and `APP_URL=https://clipjet-x.vercel.app`) in a local private `.env` file. Do not commit `.env` or register the webhook before the Vercel environment is configured.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q clipjet.py youtube_video.py telegram_api.py setup_webhook.py api/webhook.py
```

Local unit tests mock network calls; a successful production health GET does **not** prove YouTube video downloads. Test with a short public video you own or may download.

References: [Telegram Bot API](https://core.telegram.org/bots/api) · [yt-dlp YouTube EJS setup](https://github.com/yt-dlp/yt-dlp/wiki/EJS) · [Vercel Python Functions](https://vercel.com/docs/functions/runtimes/python).
