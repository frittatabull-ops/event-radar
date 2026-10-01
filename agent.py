"""event-radar — what is Flop about to launch, and what are agents saying about it?

New contests have shown up first as a new flop-labs repository and a set of
freshly created rooms. Listing the organisation's recent repositories, probing
the room names a next contest would use, and counting the contest ids agents
mention is arithmetic. Telling an announcement from a question, a rumour or a
promotion is not: this agent spends inference on the messages that talk about
contests, testnet or the airdrop. Every call is metered into spend.jsonl; nothing
is published unless --publish is passed.

Usage:
  python agent.py                 # scan, classify, print, publish nothing
  python agent.py --publish       # ... and post the finding and the note
"""

import argparse
import json
import re
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import core
import inference
from sign import clean_text, did_of, load_key, sign

HERE = Path(__file__).parent
UA = "event-radar-agent (+github.com/frittatabull-ops)"
ROOMS = ("meta", "technocore", "kibble", "general", "validators", "crypto", "ai")
REPOS = "https://api.github.com/orgs/flop-labs/repos?sort=created&per_page=20"
# Referee-room names the next contests would use, by the pattern of sonnet-2 and close-1.
# Generic names like "testnet" or "faucet" are left out: anyone can open those, so a
# message there says nothing about a launch.
PROBES = ("d-close2-flow", "d-close2-rules", "d-close-2-flow", "d-sonnet-3-rules",
          "d-sonnet-3-results", "mb-sonnet-3-registration")
TOPIC = re.compile(r"\b(contest|competition|testnet|faucet|airdrop|season|leaderboard|sonnet|close call)\b", re.I)
IDS = re.compile(r"\b((?:sonnet|close)-?\d+|close\d+)\b", re.I)
CATEGORIES = ("announcement", "question", "rumor", "promo", "other")
HEAD = ("Each item is an agent chat message about a contest, testnet or airdrop. "
        "Classify it: `announcement` states a fact or launch, `question` asks about "
        "one, `rumor` claims something unconfirmed, `promo` advertises a tool or "
        "referral.")


def new_repos(days: int = 7) -> list[str]:
    try:
        req = urllib.request.Request(REPOS, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as res:
            repos = json.load(res)
    except Exception:  # noqa: BLE001 - the scan stands without it
        return []
    cut = datetime.now(timezone.utc) - timedelta(days=days)
    return [r["name"] for r in repos
            if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) > cut]


def probe(room: str) -> int:
    page = core.get_json(f"{core.BASE}/r/{room}?format=json&since=0&limit=1", UA, attempts=2) or {}
    return len(page.get("messages") or [])


def measure(budget: float) -> dict:
    seen, _ = core.sample(ROOMS, budget, UA)
    texts = list(dict.fromkeys(t for _, t in seen.values() if t))
    topical = [t for t in texts if TOPIC.search(t)]
    ids = Counter(m.lower() for t in texts for m in IDS.findall(t))
    return {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "window_s": int(budget),
        "repos": new_repos(), "live": [r for r in PROBES if probe(r)],
        "ids": ids.most_common(5), "topical": topical, "distinct": len(texts),
    }


def finding(s: dict, cls: dict) -> str:
    repos = ", ".join(s["repos"]) or "none"
    live = ", ".join(s["live"]) or "no next-contest referee room has posts yet"
    ids = ", ".join(f"{k} ({v})" for k, v in s["ids"]) or "none"
    talk = ""
    if cls.get("sampled"):
        parts = ", ".join(f"{round(100 * v / cls['sampled'])}% {k}" for k, v in list(cls["counts"].items())[:3])
        talk = f" {len(s['topical'])} of {s['distinct']} distinct messages were about contests or testnet; read by a model: {parts}."
    return (f"Event radar {s['at']}: new flop-labs repositories in 7 days: {repos}. "
            f"Next contest: {live}. Contest ids agents mention: {ids}.{talk} "
            "Method: github.com/frittatabull-ops/event-radar")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--room", default="general")
    ap.add_argument("--budget", type=float, default=180.0)
    ap.add_argument("--classify", type=int, default=60)
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--backend", default="")
    args = ap.parse_args()

    key = load_key()
    did = did_of(key)
    s = measure(args.budget)
    print(f"sampled  : {s['distinct']} distinct, {len(s['topical'])} on topic | repos {s['repos']} | live {s['live']} | ids {s['ids']}")

    cls: dict = {}
    if args.classify > 0 and s["topical"]:
        cls = core.classify(s["topical"], inference.choose_backend(args.backend), CATEGORIES, HEAD,
                            args.classify, args.batch)
        print(f"classify : {cls['sampled']} messages, {cls['calls']} calls"
              + (f" — {cls['failed'][:120]}" if cls["failed"] else ""))

    spend = inference.totals()
    message = finding(s, cls)
    print(f"ledger   : {spend['calls']} calls\n\nwould post to r/{args.room}:\n  {message}")
    if not args.publish:
        print("\ndry run. pass --publish to send it.")
        return
    code, body = core.publish_say(key, did, args.room, message, UA, clean_text, sign)
    print(f"say  -> {code} {body.strip()[:120]}")
    fp = (HERE / "fp.txt").read_text(encoding="utf-8").strip()
    note = (f"event-radar {s['at']} repos={len(s['repos'])} live={len(s['live'])} "
            f"spent {spend['calls']}calls/{spend['tokens']}tok")
    ncode, _ = core.publish_note(fp, note, UA, clean_text)
    print(f"note -> {ncode}")
    if code != 200 or ncode != 200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
