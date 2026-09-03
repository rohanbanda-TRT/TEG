"""Drive a whole prospect conversation against a running server.

Real, billed Claude calls end to end: inquiry -> chat turns -> proposal.

    .venv/bin/python scripts/try_full_flow.py [base_url]
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

import httpx
import websockets

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8089"
WS = BASE.replace("http://", "ws://").replace("https://", "wss://")

TURNS = [
    "I head partnerships at Zoho. We want to reach manufacturing and textile "
    "firms in Gujarat who need ERP — the goal is qualified leads for our India "
    "channel team.",
    "We'd send about 5 people, mostly pre-sales and channel. Our buyers are "
    "operations heads and CFOs at mid-size manufacturers.",
    "What would a stall cost us?",
    "That works. Can you put together a proposal we can share internally?",
]


async def main() -> int:
    async with httpx.AsyncClient(timeout=300) as http:
        t0 = time.time()
        r = await http.post(f"{BASE}/inquiries", json={
            "person_name": "Priya Mehta",
            "company_name": "Zoho Corporation",
            "email": "priya@example.com",
            "message": "We build business software and want to reach manufacturing "
                       "buyers in Gujarat. Interested in exhibiting.",
        })
        r.raise_for_status()
        data = r.json()
        sid = data["session_id"]
        print(f"\n{'='*70}\nINQUIRY  ({time.time()-t0:.0f}s)")
        print(f"session : {sid}")
        print(f"persona : {data['persona']}")
        print(f"opening : {data['opening_message']}\n")

        proposal_card = None
        async with websockets.connect(f"{WS}/chat/{sid}", max_size=4_000_000) as ws:
            for i, msg in enumerate(TURNS, 1):
                t = time.time()
                print(f"{'='*70}\nTURN {i} ({time.time()-t0:.0f}s)\nprospect: {msg}")
                await ws.send(json.dumps({"message": msg}))

                # drain until this turn's reply (and any attachment) arrives
                got_reply = False
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=240)
                    except asyncio.TimeoutError:
                        print("  !! timed out waiting for a reply")
                        break
                    ev = json.loads(raw)
                    kind = ev.get("type") or ev.get("kind")
                    if kind in ("reply", "message") or "reply_text" in ev:
                        print(f"agent   : {ev.get('reply_text') or ev.get('text')}")
                        for k in ("cta_status", "guardrail_flags", "wants_proposal"):
                            if ev.get(k):
                                print(f"  {k}: {ev[k]}")
                        got_reply = True
                    elif kind in ("attachment", "proposal_link", "proposal"):
                        proposal_card = ev
                        print(f"  [attachment] {json.dumps(ev)[:200]}")
                        break
                    elif kind in ("typing", "status", "progress"):
                        continue
                    else:
                        print(f"  [{kind}] {json.dumps(ev)[:160]}")
                    if got_reply and kind != "attachment":
                        break
                print(f"  ({time.time()-t:.0f}s)")

        print(f"\n{'='*70}\nSESSION STATE")
        s = (await http.get(f"{BASE}/internal/sessions/{sid}")).json()
        print(f"persona        : {s.get('persona')}")
        print(f"price_requested: {s.get('price_requested')}")
        print(f"learned_facts  : {json.dumps(s.get('learned_facts', {}), indent=2)}")

        if proposal_card:
            pid = proposal_card.get("proposal_id")
            print(f"\n{'='*70}\nPROPOSAL {pid}")
            print(f"page_url : {BASE}{proposal_card.get('page_url','')}")
            pj = (await http.get(f"{BASE}/proposals/{pid}.json")).json()["proposal"]
            print(f"hero     : {pj['hero_headline']}")
            print(f"subline  : {pj['hero_subline']}")
            print(f"summary  : {pj['executive_summary'][:220]}")
            print(f"price    : {pj['recommended_package']['price_line']!r}")
            print(f"industries: {pj.get('target_industries')}")
            print(f"peers    : {pj.get('peer_companies')} of {pj.get('peers_in_sector_total')}")
            html = await http.get(f"{BASE}{proposal_card.get('page_url','')}")
            print(f"landing page: HTTP {html.status_code}")
        else:
            print("\n!! no proposal card was delivered")

        print(f"\ntotal: {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
