#!/usr/bin/env python3
"""Read-only GitHub Actions probe for NBA PropSignal's published card feed.
No notification sends, no GitHub state writes, no spreadsheet changes.
"""
import json
import os
import sys
import urllib.request

FEED_URL = "https://script.google.com/macros/s/AKfycbyhKmpJu5AC_R8jhscBojGDAPzQAAt7Z4lPLdMpQea43HzxIS5dfuX65Rct009iIymk/exec?api=card"
RESULTS = frozenset(("HIT", "MISS", "PUSH", "DNP", "VOID"))

def _id(p):
    return str(p.get("key") or p.get("id") or "|".join(map(str, (
        p.get("date", ""), p.get("player", ""), p.get("stat", ""),
        p.get("direction", ""), p.get("line", "")
    ))))

def stable_snapshot(card):
    """Semantically stable fields: ignore timestamps and background refresh metadata."""
    if not isinstance(card, dict) or card.get("ok") is not True or card.get("page") != "card":
        raise ValueError("Response is not a valid NBA PropSignal card")
    if not isinstance(card.get("tonight"), list) or not isinstance(card.get("recent"), list):
        raise ValueError("Missing tonight/recent card lists")
    projections = {}
    locked = {}
    for p in card["tonight"]:
        if not isinstance(p, dict):
            continue
        key = _id(p)
        projections[key] = [
            p.get("date"), p.get("player"), p.get("stat"),
            p.get("direction"), p.get("decision"), p.get("line"),
            p.get("odds"), p.get("book"), p.get("proj"),
            p.get("grade"), sorted(p.get("lists") or [])
        ]
        if p.get("locked"):
            locked[key] = True
    results = {}
    for p in card["recent"]:
        if not isinstance(p, dict):
            continue
        outcome = str(p.get("outcome") or "").upper()
        if outcome in RESULTS:
            results[_id(p)] = [outcome, p.get("actual"), p.get("units")]
    return {
        "date": card.get("today"),
        "publication": (card.get("publication") or {}).get("status", "UNKNOWN"),
        "projections": projections,
        "locked": locked,
        "results": results
    }

def compare_snapshots(previous, current):
    """Event detector prototype. First observation sets baseline; sends nothing."""
    if previous is None:
        return {"projections": 0, "locked": 0, "results": 0, "baseline": True}
    new_locks = set(current["locked"]) - set(previous["locked"])
    new_results = sum(1 for key, value in current["results"].items()
                      if previous["results"].get(key) != value)
    new_projections = sum(1 for key, value in current["projections"].items()
                          if previous["projections"].get(key) != value)
    removed = len(set(previous["projections"]) - set(current["projections"]))
    approved = current["publication"] == "APPROVED_CURRENT"
    return {
        "projections": new_projections + removed if approved else 0,
        "locked": len(new_locks),
        "results": new_results,
        "baseline": False
    }

def main():
    try:
        url = os.environ.get("NBA_CARD_URL") or FEED_URL
        if not url.startswith("https://script.google.com/macros/s/") or "api=card" not in url:
            raise ValueError("Unexpected source URL; expected Apps Script api=card")
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "NBAPropSignal-GitHub-Actions-ReadOnly-Probe/1.0"
        })
        with urllib.request.urlopen(req, timeout=75) as response:
            raw = response.read(3000001)
            if len(raw) > 3000000:
                raise ValueError("Feed exceeds 3 MB")
            try:
                card = json.loads(raw.decode("utf-8"))
            except Exception as err:
                raise ValueError("Response was not JSON; check Google redirect and deployment") from err
        snapshot = stable_snapshot(card)
        print(json.dumps({
            "read_only_probe": "PASS",
            "page": card.get("page"),
            "today_ct": snapshot["date"],
            "publication": snapshot["publication"],
            "current_plays": len(snapshot["projections"]),
            "locked_plays": len(snapshot["locked"]),
            "graded_plays_in_feed": len(snapshot["results"]),
            "detectable_events": ["projections", "locked", "results"],
            "notification_sent": False,
            "apps_script_modified": False
        }, indent=2, sort_keys=True))
    except Exception as exc:
        print("READ-ONLY PROBE FAILED: " + str(exc), file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
