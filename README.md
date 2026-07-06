# same-post

A tiny CLI that posts the same text to Twitter/X and Bluesky at the same time.

```
$ python post.py "hello world, posted everywhere"
[ok]   bluesky: https://bsky.app/profile/you.bsky.social/post/abc123
[ok]   twitter: https://twitter.com/i/web/status/1234567890
```

Both posts fire in parallel, and each platform's result (success or failure) is reported independently — if one fails, the other still goes through.

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
