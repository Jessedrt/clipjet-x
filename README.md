# ClipJet — Telegram X + YouTube downloader (best effort)

Telegram bot: [@ClipJetDownloaderBot](https://t.me/ClipJetDownloaderBot). Send exactly one public X/Twitter post URL, YouTube watch/Shorts/live URL or `youtu.be` link. The bot attempts to find one progressive MP4 with audio that Telegram can retrieve directly. **Use only media you are authorized to save and follow platform terms.** YouTube generally restricts downloading unless its service or the applicable rights holders authorize it.

## Status and architecture

The bot runs on Vercel at `https://clipjet-x.vercel.app/api/webhook`, using the existing Telegram webhook. X and YouTube URL routing share the same Telegram handler, with strict URL validators and media selectors. `yt-dlp` extracts public metadata only; Vercel never downloads, proxies, merges, stores or uploads video bytes. The bot asks Telegram to fetch a remote HTTPS MP4 with `sendVideo`.

- X accepts canonical HTTPS x.com/twitter.com post links; videos must be direct `video.twimg.com` MP4s.
- YouTube accepts HTTPS `youtube.com/watch?v=...`, `/shorts/...`, `/live/...`, and `youtu.be/...` links. It first tries a progressive HTTPS `*.googlevideo.com/videoplayback` MP4 with audio. It does not itself stitch adaptive streams or extract private, age-restricted or DRM content.
- Videos estimated under 18 MB are selected, allowing headroom under Telegram's **20 MB URL-fetch limit**. Actual remote file sizes may be unknown and Telegram may reject delivery.
- **YouTube is experimental.** `yt-dlp` may need an external JavaScript runtime and YouTube may challenge traffic from Vercel. No successful real YouTube video delivery has been verified.

## Optional alternative media API (Cobalt)

There is an **opt-in** integration with an operator-owned or explicitly authorized [Cobalt API](https://github.com/imputnet/cobalt/blob/main/docs/api.md). It activates only when `COBALT_API_URL` is set in the Vercel Production environment. Do not use `api.cobalt.tools` or other hosted instances without their owner's permission; the public hosted API is not intended for third-party automation without permission. Cobalt is not guaranteed to solve YouTube's access challenges, and it may have its own hosting requirements.

Set:

```env
COBALT_API_URL=https://YOUR-AUTHORIZED-COBALT-INSTANCE.example
COBALT_API_KEY=YOUR_INSTANCE_KEY_IF_REQUIRED
```

- Use an actual HTTPS domain at the instance **origin** (no path, trailing port or credentials). The example hostname above is **not a working endpoint**. Keep `COBALT_API_URL` empty until your instance exists. Do not share or commit the key. `COBALT_API_KEY` is optional if your own instance doesn't require authentication.
- The bot tries the optional provider **only if** YouTube challenges our server or there is no compatible progressive MP4. It requests 360p H.264/MP4, `alwaysProxy: true`, and refuses non-MP4, off-domain tunnel URLs, picker and local-processing responses. The provider supplies the media URL, then Telegram fetches it directly. No media bytes pass through Vercel.
- Since Cobalt does not necessarily return a reliable file size and Telegram may be unable to fetch a provider's URL, even a successful provider response does not guarantee a Telegram video. This is a configurable integration, **not a verified working YouTube download service**.
- The fallback is disabled by default, so adding this code does not change the existing working X route or require new Telegram secrets. You do not need to re-register the Telegram webhook when adding `COBALT_API_URL`; redeploy Vercel after changing environment variables.

## Configuration

In Vercel Production environment variables, retain `BOT_TOKEN` and `WEBHOOK_SECRET` (16-256 ASCII letters/digits/underscore/hyphen). Set `BOT_OWNER_ID` while testing if appropriate. Never post keys or cookies in chat. The registered webhook remains `https://clipjet-x.vercel.app/api/webhook`.

`COBALT_API_URL` and optional `COBALT_API_KEY` belong in Vercel Production environment variables, **not GitHub**. If adding them, save and redeploy. The Cobalt key is used only for the processing request and is not returned to Telegram users. Use your own provider or explicit permission from its owner; do not provide your YouTube account cookies or passwords to this bot.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q clipjet.py youtube_video.py cobalt_client.py telegram_api.py setup_webhook.py api/webhook.py
```

Tests mock external network calls; a healthy deployment does **not** prove successful YouTube downloads. Test only with a short public video you own or may download after configuring an authorized provider.

References: [Cobalt API](https://github.com/imputnet/cobalt/blob/main/docs/api.md) · [Telegram Bot API](https://core.telegram.org/bots/api) · [Vercel Python Functions](https://vercel.com/docs/functions/runtimes/python).
