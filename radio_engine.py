"""JakeAI Dynamic Radio — private development engine.

Generates non-repeating DJ breaks for original JakeAI stations. Text generation is
local/combinatorial by default so a station does not incur a model charge on every
break. Optional AI punch-up is fail-closed behind RADIO_AI_PUNCHUP_ENABLED.

No audio generation happens here. The resulting host script is intended for the
private/self-hosted JakeAI Original AI Narration voice renderer.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from mission_dispatcher import _require_control

router = APIRouter()
_rng = random.SystemRandom()

HOST = {
    "name": "JakeAI Original Radio",
    "voice": "JakeAI Original AI Narration",
    "style": [
        "dry and conversational",
        "calm storyteller",
        "mischievous but not mean",
        "underplayed rather than punchline-heavy",
        "specific observations beat generic jokes",
        "occasionally absurd; never random word salad",
        "comfortable with silence and short sentences",
    ],
    "never": [
        "sexual material",
        "political advocacy or political commentary",
        "advertisements or sponsor reads",
        "impersonation of a real person",
        "celebrity voice imitation",
        "copyrighted song lyrics",
        "slurs or targeted harassment",
        "claims that fictional events are real-world news",
    ],
    "credit": "JakeAI Original AI Radio Host",
}

STATIONS = {
    "jakeai_original": {
        "name": "JakeAI Radio",
        "tagline": "The machine found the dial.",
        "genre": "eclectic original JakeAI music",
        "temperature": "balanced",
    },
    "circuit_country": {
        "name": "Circuit Country",
        "tagline": "Pickup trucks. Bad decisions. Surprisingly good bandwidth.",
        "genre": "country-rock comedy and southern-tech originals",
        "temperature": "warm",
    },
    "neural_beats": {
        "name": "Neural Beats",
        "tagline": "Music for people who definitely said they were going to bed an hour ago.",
        "genre": "electronic, hip-hop, synth and cinematic originals",
        "temperature": "energetic",
    },
    "night_shift_404": {
        "name": "Night Shift 404",
        "tagline": "Nothing good happens after midnight. We checked.",
        "genre": "late-night synth, ambient, strange pop and experimental originals",
        "temperature": "weird",
    },
    "foundry_fm": {
        "name": "Foundry FM",
        "tagline": "Still building. Somehow broadcasting.",
        "genre": "industrial, rock, cinematic and machine-room originals",
        "temperature": "driving",
    },
}

OPENERS = [
    "All right, that was {previous}.",
    "That was {previous}, which apparently survived quality control.",
    "You just heard {previous}. I have questions, but none of them are urgent.",
    "{previous}. There it went.",
    "That was {previous}. Nobody was injured during the last three minutes, as far as the station knows.",
    "Coming out of {previous}. We are still technically broadcasting.",
    "{previous} just left the building without signing anything.",
    "That was {previous}. It knew what it was doing. Mostly.",
]

OBSERVATIONS = [
    "Somewhere, a dashboard light just came on and somebody decided not to look at it.",
    "If your plan currently depends on one more cup of coffee, that is not a plan. It is infrastructure.",
    "There is a very specific kind of confidence involved in saying, 'It should be fine,' while holding a wrench.",
    "Today remains undefeated at producing things nobody put on the calendar.",
    "A machine can process a million possibilities a second and still somehow choose the weird one.",
    "The difference between a shortcut and a story you tell for years is usually about twelve minutes.",
    "If you hear a strange noise from the vehicle, turn the radio up. This is not mechanical advice.",
    "Some problems need expertise. Others need somebody to stop touching the button.",
    "We have reviewed the situation and determined that absolutely nobody reviewed the situation.",
    "There is probably a perfectly reasonable explanation. We are trying not to ruin it by finding out.",
    "Nothing says progress like renaming the folder 'final-final-actually-final.'",
    "The station's legal department is just a sticky note that says, 'Maybe don't.'",
    "If this feels unusually organized, something is probably missing.",
    "You can learn a lot from a bad idea, particularly if somebody else tries it first.",
    "That silence you hear is the sound of a notification not being checked.",
    "Somewhere right now, a printer is demanding an emotional commitment before it prints page two.",
    "The future is here. It would like the Wi-Fi password.",
    "Nobody knows why that fixed it. Please do not move anything.",
    "There are two kinds of people: people who make backups and people who are about to.",
    "We support innovation, provided innovation stops unplugging the router.",
]

TRANSITIONS = [
    "Up next is {next}. Let's see what it broke to get here.",
    "Next up: {next}. No paperwork required.",
    "We've got {next} coming in. Try to look occupied.",
    "Next is {next}. It sounded cheaper than therapy.",
    "{next} is on deck. Nobody asked it to be, which feels on brand.",
    "Stay where you are. {next} is next, unless the universe files an objection.",
    "Coming up: {next}. This seemed like a good idea several minutes ago.",
    "Next, {next}. If it gets weird, that's between you and the speakers.",
]

STATION_IDS = [
    "You're on {station}. {tagline}",
    "This is {station}. We annoy the problem, not you.",
    "{station}. Still on the air despite several excellent opportunities to stop.",
    "You're listening to {station}, broadcasting from somewhere between a good idea and a maintenance ticket.",
    "This is {station}. No motivational quote is currently scheduled.",
]

CONTEXT_LINES = {
    "night": [
        "It is late enough that every reasonable decision has already gone home.",
        "Night shift rules apply: if it works, don't wake it up.",
        "This is the hour when a snack quietly becomes a meal.",
    ],
    "driving": [
        "Keep your eyes on the road. The radio has agreed to handle the unnecessary commentary.",
        "If you missed the turn, congratulations, you have discovered alternate routing.",
        "The vehicle is moving. That already puts it ahead of several projects we know.",
    ],
    "building": [
        "Apparently we're building something again. Nobody hide the extension cords.",
        "The Foundry is awake, which is rarely a quiet development.",
        "Something is compiling somewhere. This is a good time to pretend confidence.",
    ],
    "chaos": [
        "Things appear to have become complicated in a very committed way.",
        "We are now past the part where somebody says, 'How bad could it be?'",
        "This situation has developed features.",
    ],
}

class BreakRequest(BaseModel):
    station_id: str = "jakeai_original"
    previous_track: str = "that last track"
    next_track: str = "the next one"
    context: str = ""
    context_tags: list[str] = Field(default_factory=list)
    max_words: int = 52
    ai_punchup: bool = False

def _now():
    return datetime.now(timezone.utc).isoformat()

def _db_path():
    explicit=os.environ.get("RADIO_DATABASE_PATH","").strip()
    if explicit:
        return explicit
    return "/data/jakeai-radio.db" if os.path.isdir("/data") else "/tmp/jakeai-radio.db"

def _conn():
    c=sqlite3.connect(_db_path(),timeout=20)
    c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS radio_breaks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      station_id TEXT NOT NULL,
      previous_track TEXT NOT NULL,
      next_track TEXT NOT NULL,
      context TEXT NOT NULL,
      context_tags TEXT NOT NULL,
      script TEXT NOT NULL,
      script_hash TEXT NOT NULL,
      mode TEXT NOT NULL,
      word_count INTEGER NOT NULL,
      voice_profile TEXT NOT NULL,
      audio_status TEXT NOT NULL DEFAULT 'not_rendered'
    )""")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_radio_break_hash ON radio_breaks(script_hash)")
    c.commit()
    return c

def _clean_title(value):
    value=re.sub(r"[\r\n\t]+"," ",str(value or "")).strip()
    return re.sub(r"\s+"," ",value)[:140] or "that track"

def _recent(limit=40, station_id=None):
    c=_conn()
    if station_id:
        rows=c.execute("SELECT * FROM radio_breaks WHERE station_id=? ORDER BY id DESC LIMIT ?",(station_id,limit)).fetchall()
    else:
        rows=c.execute("SELECT * FROM radio_breaks ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]

def _fingerprint(text):
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

def _tokens(text):
    return re.findall(r"[a-z0-9']+",text.lower())

def _similarity(a,b):
    aa=set(_tokens(a)); bb=set(_tokens(b))
    if not aa or not bb:
        return 0.0
    return len(aa&bb)/len(aa|bb)

def _safe(script):
    s=script.lower()
    banned=[
        "vote for","vote against","democrat","republican","campaign donation",
        "sponsored by","our sponsor","buy now","limited time offer",
        "onlyfans","porn","sex toy",
        "in the voice of","sounds just like","impersonating",
    ]
    return not any(x in s for x in banned)

def _context_line(tags):
    pool=[]
    for t in tags:
        pool.extend(CONTEXT_LINES.get(str(t).lower(),[]))
    return _rng.choice(pool) if pool else ""

def _candidate(req):
    st=STATIONS[req.station_id]
    previous=_clean_title(req.previous_track)
    nxt=_clean_title(req.next_track)
    style=_rng.choice(["short","observational","station","context","double"])
    pieces=[]
    if style in {"short","double","observational","context"}:
        pieces.append(_rng.choice(OPENERS).format(previous=previous))
    if style in {"observational","double"}:
        pieces.append(_rng.choice(OBSERVATIONS))
    if style=="context":
        line=_context_line(req.context_tags)
        pieces.append(line or _rng.choice(OBSERVATIONS))
    if style=="station":
        pieces.append(_rng.choice(STATION_IDS).format(station=st["name"],tagline=st["tagline"]))
    if style in {"short","double","station","context"}:
        pieces.append(_rng.choice(TRANSITIONS).format(next=nxt))
    return " ".join(x for x in pieces if x).strip()

def _trim_words(text,max_words):
    words=text.split()
    if len(words)<=max_words:
        return text
    clipped=" ".join(words[:max_words]).rstrip(" ,;:-")
    if clipped[-1:] not in ".!?":
        clipped+="."
    return clipped

def _fallback(req):
    recent=_recent(50,req.station_id)
    for _ in range(120):
        text=_trim_words(_candidate(req),max(16,min(80,int(req.max_words))))
        fp=_fingerprint(text)
        if any(r["script_hash"]==fp for r in recent):
            continue
        if any(_similarity(text,r["script"])>.66 for r in recent[:18]):
            continue
        if not _safe(text):
            continue
        return text
    # The fallback is intentionally plain rather than repeating a known break.
    st=STATIONS[req.station_id]
    return f"This is {st['name']}. That was {_clean_title(req.previous_track)}. Next is {_clean_title(req.next_track)}."

def _ai_enabled():
    return os.environ.get("RADIO_AI_PUNCHUP_ENABLED","").strip().lower() in {"1","true","yes","on"}

def _ai_punchup(req,draft):
    if not (req.ai_punchup and _ai_enabled()):
        return draft,"local"
    try:
        from direct_billing import _call_openai
        recent=[r["script"] for r in _recent(12,req.station_id)]
        prompt=f"""You are writing ONE short radio-DJ break for JakeAI Radio.

HOST VOICE:
- dry, conversational, calm, mischievous, underplayed
- funny through specific observations, not forced punchlines
- occasional self-aware machine humor, never 'beep boop'
- sounds like a real late-night/local radio host, not marketing copy

HARD RULES:
- maximum {max(16,min(80,int(req.max_words)))} words
- do not quote or reproduce song lyrics
- no politics, political commentary or advocacy
- no sexual material
- no advertisements, sponsors, calls to buy, or product pitches
- no impersonation of any real person
- don't claim fictional context is real news
- do not say 'as an AI'
- return ONLY the spoken DJ words

Station: {STATIONS[req.station_id]['name']}
Station identity: {STATIONS[req.station_id]['tagline']}
Previous track: {_clean_title(req.previous_track)}
Next track: {_clean_title(req.next_track)}
Context tags: {json.dumps(req.context_tags)}
Optional context: {str(req.context)[:600]}
Local draft you may improve or replace: {draft}

DO NOT reuse phrasing from these recent breaks:
{json.dumps(recent)}
"""
        result=_call_openai(prompt,"general")
        text=_trim_words(str(result.get("text") or "").strip(),max(16,min(80,int(req.max_words))))
        if not text or not _safe(text):
            return draft,"local_ai_rejected"
        if any(_similarity(text,r)>.58 for r in recent):
            return draft,"local_ai_repeated"
        return text,"ai_punchup"
    except Exception:
        return draft,"local_ai_unavailable"

def generate_break(req):
    if req.station_id not in STATIONS:
        raise HTTPException(400,"Unknown JakeAI station")
    draft=_fallback(req)
    script,mode=_ai_punchup(req,draft)
    fp=_fingerprint(script)
    c=_conn()
    try:
        c.execute("""INSERT INTO radio_breaks
          (created_at,station_id,previous_track,next_track,context,context_tags,script,script_hash,mode,word_count,voice_profile,audio_status)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",(
            _now(),req.station_id,_clean_title(req.previous_track),_clean_title(req.next_track),
            str(req.context or "")[:1000],json.dumps(req.context_tags),script,fp,mode,
            len(script.split()),HOST["voice"],"not_rendered"
        ))
        c.commit()
        break_id=int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
    except sqlite3.IntegrityError:
        c.close()
        # Collision means memory worked but randomness landed on an old line; retry.
        return generate_break(req)
    row=c.execute("SELECT * FROM radio_breaks WHERE id=?",(break_id,)).fetchone()
    c.close()
    return dict(row)

@router.get("/api/v1/radio/private/status")
@router.get("/v1/radio/private/status")
def radio_status(request:Request,authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    rows=_recent(20)
    c=_conn()
    total=int(c.execute("SELECT COUNT(*) FROM radio_breaks").fetchone()[0])
    c.close()
    return {
      "status":"development_live",
      "host":HOST,
      "stations":STATIONS,
      "breaks_generated":total,
      "recent":rows,
      "ai_punchup_enabled":_ai_enabled(),
      "default_generation":"local_non_metered",
      "voice_rendering":"JakeAI Original AI Narration / self-hosted Chatterbox",
      "public_broadcast":False,
      "music_public_playback":"rights-gated",
    }

@router.post("/api/v1/radio/private/break")
@router.post("/v1/radio/private/break")
def radio_break(body:BreakRequest,request:Request,authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    row=generate_break(body)
    return {
      "id":row["id"],
      "created_at":row["created_at"],
      "station_id":row["station_id"],
      "script":row["script"],
      "mode":row["mode"],
      "word_count":row["word_count"],
      "voice_profile":row["voice_profile"],
      "audio_status":row["audio_status"],
      "public":False,
    }

@router.get("/api/v1/radio/private/history")
@router.get("/v1/radio/private/history")
def radio_history(request:Request,authorization:Optional[str]=Header(None),limit:int=30):
    _require_control(authorization,request)
    limit=max(1,min(200,int(limit)))
    return {"items":_recent(limit),"count":limit}

def register_radio_routes(app):
    _conn().close()
    app.include_router(router)
