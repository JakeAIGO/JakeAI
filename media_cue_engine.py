"""JakeAI shared media cue engine.

One manifest format drives time-based media for games, radio-like experiences,
trailers, documentaries and other JakeAI productions.

It does not generate media itself. It resolves deterministic cues against the
JakeAI Media Gateway while preserving provider-independence, provenance and
release gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


CueKind = Literal["music","ambient","sfx","voice","transition","mix_state","marker"]
Consumer = Literal["game","documentary","trailer","radio","book","generic"]


class MediaCue(BaseModel):
    id: str
    kind: CueKind
    start_seconds: float = Field(ge=0)
    end_seconds: Optional[float] = Field(default=None, ge=0)
    asset_id: Optional[str] = None
    generator: Optional[str] = None
    prompt: Optional[str] = None
    intensity: float = Field(default=0.5, ge=0, le=1)
    gain_db: float = Field(default=0.0, ge=-48, le=18)
    duck_under_voice_db: float = Field(default=0.0, ge=-30, le=0)
    tags: list[str] = Field(default_factory=list)
    provenance_required: bool = True
    public_release_allowed: bool = False
    notes: str = ""

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_seconds is not None and self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be >= start_seconds")
        if self.kind in {"music","ambient","sfx","voice","transition"}:
            if not any([self.asset_id, self.generator, self.prompt]):
                raise ValueError(f"{self.kind} cue requires asset_id, generator, or prompt")
        return self


class MediaProgram(BaseModel):
    program_id: str
    title: str
    consumer: Consumer
    duration_seconds: Optional[float] = Field(default=None, gt=0)
    private: bool = True
    founder_voice_allowed: bool = False
    founder_voice_role: Optional[str] = None
    cues: list[MediaCue]
    release_state: str = "PRIVATE_DEVELOPMENT"

    @model_validator(mode="after")
    def validate_program(self):
        ids=[c.id for c in self.cues]
        if len(ids) != len(set(ids)):
            raise ValueError("cue ids must be unique")
        if self.duration_seconds is not None:
            for cue in self.cues:
                if cue.start_seconds > self.duration_seconds:
                    raise ValueError(f"cue {cue.id} starts after program duration")
                if cue.end_seconds is not None and cue.end_seconds > self.duration_seconds + 0.05:
                    raise ValueError(f"cue {cue.id} ends after program duration")
        return self


def ordered_cues(program: MediaProgram) -> list[MediaCue]:
    return sorted(program.cues, key=lambda x: (x.start_seconds, x.id))


def active_cues(program: MediaProgram, at_seconds: float) -> list[MediaCue]:
    out=[]
    for cue in ordered_cues(program):
        if cue.start_seconds > at_seconds:
            continue
        if cue.end_seconds is not None and at_seconds >= cue.end_seconds:
            continue
        out.append(cue)
    return out


def cue_window(program: MediaProgram, start_seconds: float, end_seconds: float) -> list[MediaCue]:
    if end_seconds < start_seconds:
        raise ValueError("end_seconds must be >= start_seconds")
    out=[]
    for cue in ordered_cues(program):
        cue_end=cue.end_seconds if cue.end_seconds is not None else cue.start_seconds
        if cue_end < start_seconds:
            continue
        if cue.start_seconds > end_seconds:
            continue
        out.append(cue)
    return out


def public_release_blockers(program: MediaProgram) -> list[str]:
    blockers=[]
    if program.private:
        blockers.append("program_is_private")
    if program.release_state not in {"APPROVED","PUBLIC_RELEASE_APPROVED"}:
        blockers.append("human_release_not_approved")
    for cue in program.cues:
        if cue.provenance_required and not cue.public_release_allowed:
            blockers.append(f"cue_not_release_cleared:{cue.id}")
    return sorted(set(blockers))
