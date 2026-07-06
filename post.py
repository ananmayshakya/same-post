#!/usr/bin/env python3
"""Post the same text to Twitter/X and Bluesky at the same time."""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()


def post_to_twitter(text: str) -> tuple[bool, str]:
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
    resp = client.create_tweet(text=text)
    tweet_id = resp.data["id"]
    return True, f"https://twitter.com/i/web/status/{tweet_id}"


def post_to_bluesky(text: str) -> tuple[bool, str]:
    from atproto import Client

    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        return False, "missing env vars: BLUESKY_HANDLE, BLUESKY_APP_PASSWORD"

    client = Client()
    client.login(handle, password)
    resp = client.send_post(text=text)
    post_id = resp.uri.split("/")[-1]
    profile_handle = handle.lstrip("@")
    return True, f"https://bsky.app/profile/{profile_handle}/post/{post_id}"


PLATFORMS = {
    "twitter": post_to_twitter,
    "bluesky": post_to_bluesky,
}

# Twitter/X: 280 chars for standard accounts. Bluesky: 300 graphemes.
MAX_LENGTHS = {
    "twitter": 280,
    "bluesky": 300,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="?", help="tweet text (reads stdin if omitted)")
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
    to_run = []
    for name in targets:
        limit = MAX_LENGTHS[name]
        if len(text) > limit:
            print(f"[fail] {name}: text is {len(text)} chars, over the {limit} char limit")
            exit_code = 1
        else:
            to_run.append(name)

    with ThreadPoolExecutor(max_workers=max(len(to_run), 1)) as pool:
        futures = {pool.submit(PLATFORMS[name], text): name for name in to_run}
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
