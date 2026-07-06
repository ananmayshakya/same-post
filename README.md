# same-post

A tiny CLI that posts the same text to Twitter/X and Bluesky at the same time.

```
$ python post.py "hello world, posted everywhere"
[ok]   bluesky: https://bsky.app/profile/you.bsky.social/post/abc123
[ok]   twitter: https://twitter.com/i/web/status/1234567890
```

Both posts fire in parallel, and each platform's result (success or failure) is reported independently — if one fails, the other still goes through.

If your text is too long for a platform's single-post limit, it's automatically split into a reply-chained thread on that platform only — the other platform still gets a single post if it fits. For example, a 290-character post exceeds Twitter's 280-char limit but fits Bluesky's 300, so Twitter gets a 2-post thread while Bluesky gets one post. This works in either direction, including if you have Twitter Premium/Pro and raise `TWITTER_MAX_LEN` (see below) to post something long as a single tweet — Bluesky would then thread it instead.

Threads are split on word boundaries and balanced evenly across parts (not greedily filled), so you don't end up with an awkward 2-3 word final post. Each part is numbered, e.g. `(1/3)`.

## Setup

```
pip install -r requirements.txt
cp .env.example .env
```

Then fill in `.env` with your own credentials (see below). `.env` is gitignored — never commit it.

### Bluesky credentials

1. Go to bsky.app → **Settings → Privacy and Security → App Passwords**
2. Create a new app password (don't use your real account password)
3. Put your handle and the app password into `.env`:
   ```
   BLUESKY_HANDLE=yourhandle.bsky.social
   BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```

### Twitter/X credentials

1. Sign up for a developer account at [developer.twitter.com](https://developer.twitter.com)
2. Create a Project and an App
3. In the app's **User authentication settings**, set App permissions to **Read and Write**
4. In the **Keys and tokens** tab, generate/copy the API Key & Secret and Access Token & Secret
   (regenerate the access token *after* setting Read+Write, otherwise it'll be read-only)
5. Put all four into `.env`:
   ```
   TWITTER_CONSUMER_KEY=
   TWITTER_CONSUMER_SECRET=
   TWITTER_ACCESS_TOKEN=
   TWITTER_ACCESS_TOKEN_SECRET=
   ```

### Optional: per-platform length limits

```
TWITTER_MAX_LEN=280
BLUESKY_MAX_LEN=300
```

Defaults shown above. If you have Twitter Premium/Pro and your API access supports posting longer than 280 characters in a single tweet, raise `TWITTER_MAX_LEN` accordingly — this isn't guaranteed by the standard API, so test it with a real post first. Bluesky's 300-grapheme limit isn't affected by any subscription tier.

Length is estimated per platform's own counting rules, not just raw character count:
- **Twitter**: links always count as 23 characters regardless of actual length, emoji count double. This approximates twitter-text's real weighting, not a byte-exact reimplementation.
- **Bluesky**: counts Unicode code points as a stand-in for grapheme clusters (accurate for plain text and most emoji, slightly undercounts multi-codepoint sequences like flags), and links count at their full displayed length.

## Usage

```
python post.py "your text here"
```

Read text from stdin instead:

```
echo "your text here" | python post.py
```

Post to only one platform:

```
python post.py "your text here" --only twitter
python post.py "your text here" --only bluesky
```

## License

MIT
