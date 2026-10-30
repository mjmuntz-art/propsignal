#!/usr/bin/env python3
"""NBA PropSignal external monitor. No Apps Script changes required.

Reads the public card API, creates a compact checkpoint, and optionally sends
OneSignal push notifications to opted-in NBA PropSignal subscribers.

Required to SEND: env NBA_PUSH_SEND_ENABLED=true and ONESIGNAL_REST_API_KEY.
Without both, the monitor is a read-only / checkpoint-only dry run.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from nba_push_probe import FEED_URL, stable_snapshot

APP_ID = "4174a3fe-47af-44be-a68f-257caad1e247"
APP_URL = "https://mjmuntz-art.github.io/propsignal/"
VALID_OUTCOMES = {"HIT", "MISS", "PUSH", "VOID", "DNP"}

def fetch_card():
    req = urllib.request.Request(FEED_URL, headers={
        "Accept": "application/json",
        "User-Agent": "NBAPropSignal-GHA-Push-Monitor/1.0",
    })
    with urllib.request.urlopen(req, timeout=75) as response:
        raw = response.read(3000001)
    if len(raw) > 3000000:
        raise ValueError("Unexpected oversized card response")
    card = json.loads(raw.decode("utf-8"))
    stable_snapshot(card)  # Fail closed for malformed/stale error payloads.
    return card

def stable_key(p):
    return str(p.get("key") or p.get("id") or "|".join(map(str, (
        p.get("date", ""), p.get("player", ""), p.get("stat", ""),
        p.get("direction", ""), p.get("line", "")))))

def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

def projections_from(card):
    out = {}
    for p in card["tonight"]:
        if not isinstance(p, dict):
            continue
        decision = str(p.get("decision") or "").upper()
        if decision not in ("PLAY", "LEAN"):
            continue
        key = stable_key(p)
        out[key] = {
            "decision": decision,
            "player": p.get("player"),
            "stat": p.get("stat"),
            "direction": p.get("direction"),
            "line": p.get("line"),
            # Ignore price movement / refresh timestamps to prevent noise.
            # Notify on meaningful movement of the projected total (nearest unit).
            "projection_band": round(float(p["proj"])) if p.get("proj") not in (None, "") else None,
        }
    return out

def read_state(path):
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(state, dict) or state.get("schema") != 1:
        raise ValueError("Checkpoint has an unexpected schema; refusing to send")
    return state

def current_checkpoint(card, old):
    base = {
        "schema": 1,
        "sequence": (old or {}).get("sequence", 0) + 1,
        "date": card.get("today"),
        "publication": (card.get("publication") or {}).get("status", "UNKNOWN"),
        "projections": projections_from(card),
        "locked": {},
        "results": dict((old or {}).get("results", {})),
    }
    for p in card["tonight"]:
        if isinstance(p, dict) and p.get("locked"):
            base["locked"][stable_key(p)] = True
    for p in card["recent"]:
        if not isinstance(p, dict):
            continue
        result = str(p.get("outcome") or "").upper()
        if result in VALID_OUTCOMES:
            # Keep previous grades to avoid repeat notifications when the
            # server's limited recent-results list rolls forward.
            base["results"][stable_key(p)] = stable_hash({
                "outcome": result, "actual": p.get("actual"), "units": p.get("units")
            })
    # Bounded state: retain up to 1000 graded plays by insertion order.
    base["results"] = dict(list(base["results"].items())[-1000:])
    return base

def changes(old, current):
    if old is None:
        return {"projections": 0, "locked": 0, "results": 0, "baseline": True}
    approved = current["publication"] == "APPROVED_CURRENT"
    nowplays = current["projections"]
    oldplays = old.get("projections", {}) if old.get("date") == current["date"] else {}
    new_picks = sum(1 for key, val in nowplays.items() if oldplays.get(key) != val)
    dropped = sum(1 for key in oldplays if key not in nowplays)
    new_locks = sum(1 for key in current["locked"]
                    if not old.get("locked", {}).get(key))
    new_results = sum(1 for key, digest in current["results"].items()
                      if key not in old.get("results", {}))
    return {
        "projections": new_picks + dropped if approved else 0,
        "locked": new_locks,
        "results": new_results,
        "baseline": False,
    }

def send_alert(category, count, prior_sequence, current):
    key = os.environ.get("ONESIGNAL_REST_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Sending enabled but ONESIGNAL_REST_API_KEY is missing.")
    title = {
        "projections": "NBA PropSignal — Projections Updated",
        "locked": "NBA PropSignal — Plays Locked",
        "results": "NBA PropSignal — Results Graded",
    }[category]
    body = {
        "projections": f"{count} published selection(s) changed. Open your card to review.",
        "locked": f"{count} play(s) locked for tonight.",
        "results": f"{count} new play result(s) available.",
    }[category]
    fingerprint = stable_hash([current["date"],category,count,current["projections"] if category == "projections" else current[category]])
    seed = hashlib.sha256(f"propsignal:{prior_sequence}:{category}:{fingerprint}".encode("utf-8")).digest()
    idem = str(uuid.UUID(bytes=seed[:16], version=4))  # Stable UUIDv4 format for OneSignal retries.
    payload = {
        "app_id": APP_ID,
        "target_channel": "push",
        "headings": {"en": title},
        "contents": {"en": body},
        "url": APP_URL,
        "idempotency_key": idem,
        "filters": [
            {"field": "tag", "key": "push_nba_prop_enabled", "relation": "=", "value": "1"},
            {"operator": "AND"},
            {"field": "tag", "key": f"push_nba_prop_{category}", "relation": "=", "value": "1"},
        ],
    }
    req = urllib.request.Request(
        "https://api.onesignal.com/notifications",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Key " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status, result = response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not print the auth token, request body or subscriber IDs to logs.
        raise RuntimeError(f"OneSignal returned HTTP {exc.code}; checkpoint not advanced.") from None
    if status < 200 or status >= 300 or not isinstance(result, dict) or not result.get("id"):
        raise RuntimeError("OneSignal did not accept the notification; checkpoint not advanced.")
    print(f"OneSignal accepted {category} notification (count={count}).")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    args = parser.parse_args()
    old = read_state(args.old)
    card = fetch_card()
    current = current_checkpoint(card, old)
    events = changes(old, current)
    send_enabled = os.environ.get("NBA_PUSH_SEND_ENABLED", "").strip().lower() == "true"
    print(json.dumps({
        "checkpoint": "baseline" if events["baseline"] else "updated",
        "today": current["date"],
        "publication": current["publication"],
        "plays": len(current["projections"]),
        "locked": len(current["locked"]),
        "known_results": len(current["results"]),
        "detected_events": {k:v for k,v in events.items() if k!="baseline"},
        "send_enabled": send_enabled,
    }, sort_keys=True))
    if send_enabled:
        for category in ("projections", "locked", "results"):
            if events[category]:
                send_alert(category, events[category], (old or {}).get("sequence",0), current)
    else:
        print("DRY RUN: no OneSignal request sent.")
    # Only persist after all required OneSignal requests were accepted.
    Path(args.new).write_text(json.dumps(current, separators=(",", ":"), sort_keys=True)+"\n", encoding="utf-8")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("MONITOR FAILED: "+str(exc), file=sys.stderr)
        sys.exit(1)
