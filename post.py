#!/usr/bin/env python3
"""Post the same text to Twitter/X and Bluesky at the same time.

If the text is too long for a platform's single-post limit, it's automatically
split into a reply-chained thread on that platform only.
"""

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()

# Twitter/X: 280 chars for standard accounts, more for Premium/Pro long-form posts
# (bump TWITTER_MAX_LEN in .env if your account + API access supports longer single posts).
# Bluesky: 300 graphemes, no Premium tier changes this.
MAX_LENGTHS = {
    "twitter": int(os.environ.get("TWITTER_MAX_LEN", "280")),
    "bluesky": int(os.environ.get("BLUESKY_MAX_LEN", "300")),
}

_URL_RE = re.compile(r"https?://\S+")
_TWITTER_URL_WEIGHT = 23  # every link is wrapped to a fixed-length t.co URL

# Approximate emoji ranges. Twitter weights these 2x; Bluesky counts them as 1 grapheme.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "]"
)


def twitter_length(text: str) -> int:
    """Approximate Twitter's weighted length: links fixed at 23 chars, emoji weighted 2x.

    This is an approximation of twitter-text's real weighting rules (which also
    double-weight some CJK/full-width ranges) - good enough to catch the common
    case, not a byte-exact reimplementation.
    """
    without_urls = _URL_RE.sub("", text)
    url_count = len(_URL_RE.findall(text))
    length = url_count * _TWITTER_URL_WEIGHT
    for ch in without_urls:
        length += 2 if _EMOJI_RE.match(ch) else 1
    return length


def bluesky_length(text: str) -> int:
    """Approximate Bluesky's grapheme length: emoji count as 1, links aren't shortened.

    Uses Python's code-point count as a stand-in for grapheme clusters - accurate
    for plain text and single-codepoint emoji, slightly undercounts multi-codepoint
    sequences like flags or ZWJ emoji.
    """
    return len(text)


LENGTH_FNS = {
    "twitter": twitter_length,
    "bluesky": bluesky_length,
}


def _balanced_parts(text: str, n: int, count_fn) -> list[str]:
    """Split text into n word-boundary chunks of roughly even weighted length."""
    words = text.split()
    target = count_fn(text) / n

    parts = []
    remaining = words
    for i in range(n):
        parts_left = n - i
        if parts_left == 1 or not remaining:
            chunk, remaining = remaining, []
        else:
            chunk = []
            while remaining:
                trial = chunk + [remaining[0]]
                if chunk and count_fn(" ".join(trial)) > target:
                    break
                chunk.append(remaining[0])
                remaining = remaining[1:]
        parts.append(" ".join(chunk))
    return [p for p in parts if p]


def split_into_thread(text: str, budget: int, count_fn) -> list[str]:
    """Split text into parts that each fit budget, numbering them if there's more than one.

    Splitting is balanced (each part targets an even share of the total length)
    rather than greedily filling each part to the limit, so the thread doesn't
    end with an awkward 2-3 word final post.
    """
    if count_fn(text) <= budget:
        return [text]

    too_long = [w for w in text.split() if count_fn(w) > budget]
    if too_long:
        raise ValueError(f"a single word doesn't fit the {budget}-char budget: {too_long[0]!r}")

    n = 2
    while n <= 100:
        raw_parts = _balanced_parts(text, n, count_fn)
        numbered = [f"{p} ({i + 1}/{len(raw_parts)})" for i, p in enumerate(raw_parts)]
        if all(count_fn(p) <= budget for p in numbered):
            return numbered
        n += 1

    raise ValueError(f"could not split text to fit the {budget}-char budget")


def _thread_result(urls: list[str]) -> str:
    if len(urls) == 1:
        return urls[0]
    return f"{len(urls)}-post thread starting at {urls[0]}"


def post_to_twitter(parts: list[str]) -> tuple[bool, str]:
    import tweepy

    required = [
        "TWITTER_CONSUMER_KEY",
        "TWITTER_CONSUMER_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, f"missing env vars: {', '.join(missing)}"

    client = tweepy.Client(
        consumer_key=os.environ["TWITTER_CONSUMER_KEY"],
        consumer_secret=os.environ["TWITTER_CONSUMER_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )

    urls = []
    prev_id = None
    for part in parts:
        resp = client.create_tweet(text=part, in_reply_to_tweet_id=prev_id)
        prev_id = resp.data["id"]
        urls.append(f"https://twitter.com/i/web/status/{prev_id}")
    return True, _thread_result(urls)


def post_to_bluesky(parts: list[str]) -> tuple[bool, str]:
    from atproto import Client, models

    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        return False, "missing env vars: BLUESKY_HANDLE, BLUESKY_APP_PASSWORD"

    client = Client()
    client.login(handle, password)
    profile_handle = handle.lstrip("@")

    urls = []
    root_ref = None
    parent_ref = None
    for part in parts:
        reply_to = None
        if parent_ref is not None:
            reply_to = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
        resp = client.send_post(text=part, reply_to=reply_to)
        parent_ref = models.create_strong_ref(resp)
        root_ref = root_ref or parent_ref
        post_id = resp.uri.split("/")[-1]
        urls.append(f"https://bsky.app/profile/{profile_handle}/post/{post_id}")
    return True, _thread_result(urls)


PLATFORMS = {
    "twitter": post_to_twitter,
    "bluesky": post_to_bluesky,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="?", help="post text (reads stdin if omitted)")
    parser.add_argument(
        "--only",
        choices=sorted(PLATFORMS),
        action="append",
        help="post to only this platform (repeatable)",
    )
    args = parser.parse_args()

    text = args.text
    if text is None:
        text = sys.stdin.read().strip()
    if not text:
        parser.error("no text provided")

    targets = args.only or list(PLATFORMS)

    exit_code = 0
    jobs = {}
    for name in targets:
        try:
            jobs[name] = split_into_thread(text, MAX_LENGTHS[name], LENGTH_FNS[name])
        except ValueError as e:
            print(f"[fail] {name}: {e}")
            exit_code = 1

    with ThreadPoolExecutor(max_workers=max(len(jobs), 1)) as pool:
        futures = {pool.submit(PLATFORMS[name], parts): name for name, parts in jobs.items()}
        for future in futures:
            name = futures[future]
            try:
                ok, message = future.result()
            except Exception as e:
                ok, message = False, f"{type(e).__name__}: {e}"
            if ok:
                print(f"[ok]   {name}: {message}")
            else:
                print(f"[fail] {name}: {message}")
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
