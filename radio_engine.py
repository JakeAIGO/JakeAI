"""JakeAI Dynamic Radio Engine.

KJAI 404 — Signal Found

Creates fresh, contextual DJ breaks between songs while preserving strict voice-use
boundaries. It is designed to pair with the local JakeAI Original AI Narration
voice and locally generated/original music.

This module does NOT generate or publish audio by itself. It produces approved
spoken copy + metadata for the local narrator/mixer layer.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DB = "/data/jakeai-radio.db" if os.path.isdir("/data") else "/tmp/jakeai-radio.db"

VOICE_BANNED_TOPICS = {
    "advertising",
    "political",
    "sexual",
    "impersonation",
}

HUMOR_RULES = {
    "tone": [
        "dry",
        "conversational",
        "slightly absurd",
        "observational",
        "understated",
        "self-aware",
    ],
    "avoid": [
        "salesy language",
        "forced punchlines",
        "repeated catchphrases",
        "mean-spirited jokes",
        "fourth-wall exposition dumps",
        "celebrity imitation",
    ],
    "canon": [
        "Treat strange situations as mildly inconvenient rather than astonishing.",
        "Underplay chaos instead of shouting about it.",
        "Use the occasional deadpan correction or unnecessary practical observation.",
        "Humor should sound improvised, not like a joke book.",
        "The host may gently acknowledge that the station is unusually competent for radio.",
    ],
}

@dataclass
class Song:
    id: str
    title: str
    artist: str
    genre: str
    energy: float = 0.5
    mood: str = "neutral"
    instrumental: bool = False
    source: str = "original"
    commercial_ok: bool = True

@dataclass
class RadioContext:
    station_id: str
    previous_song: Song | None
    next_song: Song
    game_time: str | None = None
    location: str | None = None
    weather: str | None = None
    recent_event: str | None = None
    player_state: str | None = None
    listen_minutes: float | None = None
    session_id: str = "default"

@dataclass
class BreakResult:
    id: str
    station_id: str
    text: str
    style: str
    generated_at: float
    previous_song_id: str | None
    next_song_id: str
    memory_key: str
    voice_profile: str = "JakeAI Original AI Narration"
    publishable: bool = False
    public_release_approved: bool = False

class BreakGeneratorAdapter:
    """Optional smarter composition adapter.

    Implementations receive structured context plus recent memory and must return
    plain DJ copy only. The engine still applies voice restrictions, length
    limits, repetition checks and release gates after generation.
    """
    name = "base"

    def generate(self, context: RadioContext, recent: list[dict[str, Any]]) -> str:
        raise NotImplementedError


class RadioMemory:
    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=20)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        c = self._conn()
        c.execute("""CREATE TABLE IF NOT EXISTS radio_breaks(
          id TEXT PRIMARY KEY,
          station_id TEXT NOT NULL,
          session_id TEXT NOT NULL,
          memory_key TEXT NOT NULL,
          text TEXT NOT NULL,
          next_song_id TEXT NOT NULL,
          previous_song_id TEXT,
          generated_at REAL NOT NULL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_radio_memory ON radio_breaks(station_id,session_id,generated_at DESC)")
        c.commit()
        c.close()

    def recent(self, station_id: str, session_id: str, limit: int = 80) -> list[dict[str, Any]]:
        c = self._conn()
        rows = c.execute(
            "SELECT * FROM radio_breaks WHERE station_id=? AND session_id=? ORDER BY generated_at DESC LIMIT ?",
            (station_id, session_id, limit),
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def save(self, result: BreakResult, session_id: str):
        c = self._conn()
        c.execute(
            """INSERT OR REPLACE INTO radio_breaks
            (id,station_id,session_id,memory_key,text,next_song_id,previous_song_id,generated_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                result.id,
                result.station_id,
                session_id,
                result.memory_key,
                result.text,
                result.next_song_id,
                result.previous_song_id,
                result.generated_at,
            ),
        )
        c.commit()
        c.close()

def _norm(s: str | None) -> str:
    return " ".join((s or "").strip().split())

def _fingerprint(text: str) -> str:
    return hashlib.sha256(_norm(text).lower().encode("utf-8")).hexdigest()[:16]

def _safe_context(ctx: RadioContext) -> dict[str, str]:
    data = {
        "location": _norm(ctx.location),
        "weather": _norm(ctx.weather),
        "recent_event": _norm(ctx.recent_event),
        "player_state": _norm(ctx.player_state),
        "game_time": _norm(ctx.game_time),
    }
    combined = " ".join(data.values()).lower()
    # Very conservative lexical gate for the founder voice.
    banned_terms = {
        "election","candidate","vote","campaign","president","senator","governor","politics",
        "sex","sexual","porn","nude","nudity","escort","strip club",
        "sponsored","sponsor","advertisement","buy now","sale","discount",
        "impersonate","impression of","sounds like celebrity",
    }
    if any(term in combined for term in banned_terms):
        data["recent_event"] = ""
        data["player_state"] = ""
    return data

def _choose(rng: random.Random, options: Iterable[str], recent_text: str) -> str:
    viable = [x for x in options if _fingerprint(x) not in recent_text]
    return rng.choice(viable or list(options))

def _song_line(song: Song) -> str:
    return f"{song.title} by {song.artist}"

def validate_host_copy(text: str, ctx: RadioContext, recent: list[dict[str, Any]]) -> str:
    text = _norm(text)
    lowered = text.lower()
    forbidden = {
        "sponsored by", "brought to you by", "buy now", "discount code",
        "vote for", "election", "campaign for", "president", "senator", "governor",
        "sexually", "pornographic", "nude",
        "doing my impression of", "here's my impression of",
    }
    if any(term in lowered for term in forbidden):
        raise ValueError("founder_voice_policy_violation")
    words = text.split()
    if len(words) > 72:
        text = " ".join(words[:72]).rstrip(" ,;:") + "."
    fp = _fingerprint(text)
    if any(_fingerprint(r.get("text","")) == fp for r in recent[:80]):
        raise ValueError("recent_radio_break_repeat")
    return text


def generate_break(ctx: RadioContext, memory: RadioMemory | None = None, seed: int | None = None, adapter: BreakGeneratorAdapter | None = None) -> BreakResult:
    """Generate a fresh, non-repeating JakeAI-style DJ break.

    This uses a controlled local phrase-composition layer so it works without an
    LLM or network call. A future LLM adapter may replace the composition step,
    but must preserve the same memory/safety checks.
    """
    memory = memory or RadioMemory()
    safe = _safe_context(ctx)
    recent = memory.recent(ctx.station_id, ctx.session_id, limit=80)
    recent_joined = " ".join(_fingerprint(x["text"]) for x in recent)

    material = "|".join([
        ctx.station_id,
        ctx.session_id,
        ctx.next_song.id,
        ctx.previous_song.id if ctx.previous_song else "",
        safe["location"],
        safe["weather"],
        safe["recent_event"],
        str(time.time_ns() if seed is None else seed),
    ])
    rng = random.Random(hashlib.sha256(material.encode()).hexdigest())

    openers = [
        "You're still on KJAI 404. Against several reasonable expectations, the signal remains found.",
        "KJAI 404. We checked the transmitter. Apparently it has decided to cooperate.",
        "This is KJAI 404, where the equipment is functional and we're trying not to make a big deal out of it.",
        "KJAI 404. If you can hear me, something has gone correctly.",
        "You're listening to KJAI 404. No committee was consulted.",
    ]

    transitions = [
        "That one did exactly what it needed to do and then left before anyone could schedule a meeting about it.",
        "That track has now completed its duties with minimal paperwork.",
        "There are worse ways to spend a few minutes. Several of them involve forms.",
        "That was surprisingly organized. I don't want to encourage it.",
        "Good song. Very little unnecessary administration. Strong showing.",
    ]

    next_intros = [
        f"Next up: {_song_line(ctx.next_song)}. Let's see what kind of decisions this one leads to.",
        f"Coming in now, {_song_line(ctx.next_song)}. Use responsibly, which in this context mostly means don't drive into anything expensive.",
        f"Here's {_song_line(ctx.next_song)}. I have been advised not to over-explain it, which is excellent advice.",
        f"Up next is {_song_line(ctx.next_song)}. It knows what it did.",
        f"Moving along with {_song_line(ctx.next_song)}. No dramatic announcement required.",
    ]

    context_bits: list[str] = []
    if safe["location"]:
        context_bits += [
            f"If you're somewhere around {safe['location']}, congratulations on successfully being there.",
            f"Broadcasting to {safe['location']} and any nearby machinery with strong opinions.",
        ]
    if safe["weather"]:
        context_bits += [
            f"Current conditions: {safe['weather']}. The radio remains indoors emotionally.",
            f"Apparently the weather is {safe['weather']}. Plan accordingly, or continue doing whatever this is.",
        ]
    if safe["recent_event"]:
        context_bits += [
            f"And yes, I heard about {safe['recent_event']}. We're going to treat that as information rather than a lifestyle.",
            f"Regarding {safe['recent_event']}: noted. Filed. Mildly concerning.",
        ]
    if safe["player_state"]:
        context_bits += [
            f"If you're currently {safe['player_state']}, I respect the confidence.",
            f"For anyone {safe['player_state']} right now: this seems like a good time for music and fewer new ideas.",
        ]

    pieces = []
    if not ctx.previous_song:
        pieces.append(_choose(rng, openers, recent_joined))
    else:
        # Reference the previous song only sometimes; avoid rigid formula.
        if rng.random() < 0.72:
            prev_specific = [
                f"That was {_song_line(ctx.previous_song)}. {_choose(rng, transitions, recent_joined)}",
                f"You just heard {_song_line(ctx.previous_song)}. Nobody was injured by the transition, which is encouraging.",
                f"{_song_line(ctx.previous_song)} just wrapped up. We remain operational.",
            ]
            pieces.append(_choose(rng, prev_specific, recent_joined))
        else:
            pieces.append(_choose(rng, transitions, recent_joined))

    if context_bits and rng.random() < 0.68:
        pieces.append(_choose(rng, context_bits, recent_joined))

    pieces.append(_choose(rng, next_intros, recent_joined))

    text = " ".join(pieces)
    if adapter is not None:
        candidate = adapter.generate(ctx, recent)
        if candidate and _norm(candidate):
            text = candidate

    text = validate_host_copy(text, ctx, recent)
    memory_key = _fingerprint(text)
    break_id = hashlib.sha256(
        f"{ctx.station_id}|{ctx.session_id}|{ctx.next_song.id}|{time.time_ns()}|{text}".encode()
    ).hexdigest()[:20]

    result = BreakResult(
        id=break_id,
        station_id=ctx.station_id,
        text=text,
        style="JakeAI dry-conversational radio",
        generated_at=time.time(),
        previous_song_id=ctx.previous_song.id if ctx.previous_song else None,
        next_song_id=ctx.next_song.id,
        memory_key=memory_key,
    )
    memory.save(result, ctx.session_id)
    return result

def load_song_catalog(path: str | Path) -> list[Song]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Song(**row) for row in rows]

def station_manifest() -> dict[str, Any]:
    return {
        "station_id": "KJAI-404",
        "name": "KJAI 404",
        "tagline": "Signal Found",
        "host_voice": "JakeAI Original AI Narration",
        "voice_restrictions": sorted(VOICE_BANNED_TOPICS),
        "humor_rules": HUMOR_RULES,
        "dynamic_breaks": True,
        "repeat_memory": True,
        "commercials_in_founder_voice": False,
        "public_release": False,
    }

if __name__ == "__main__":
    songs = [
        Song("demo-1","Midnight Exit","JakeAI House Band","synth-rock",0.68,"restless"),
        Song("demo-2","Parking Lot Astronomy","JakeAI House Band","indie-electronic",0.48,"wry"),
    ]
    mem = RadioMemory("/tmp/kjai-demo.db")
    ctx = RadioContext(
        station_id="KJAI-404",
        previous_song=songs[0],
        next_song=songs[1],
        location="the east side",
        recent_event="a suspicious amount of traffic",
        session_id="demo",
    )
    print(json.dumps(asdict(generate_break(ctx, mem)), indent=2))
