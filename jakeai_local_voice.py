"""Shared JakeAI local voice adapter.

One local founder-voice implementation for books and radio.
- no paid TTS API
- Chatterbox Nano when supported, otherwise Turbo
- compatibility fixes for older Windows builds
- fail-closed watermark behavior for production
- optional explicit unwatermarked PRIVATE QA mode
"""
from __future__ import annotations

import hashlib
import inspect
import os
import random
import re
import types
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torchaudio as ta


@dataclass
class VoiceRuntime:
    model: object
    engine: str
    device: str
    watermarked: bool
    private_unwatermarked: bool


def lexical_tokens(text: str) -> list[str]:
    return [
        x.lower().replace("’", "'")
        for x in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+", text)
    ]


def _install_private_watermark_fallback(allow: bool) -> bool:
    import perth
    wm = getattr(perth, "PerthImplicitWatermarker", None)
    if wm is not None:
        return False
    if not allow:
        raise RuntimeError(
            "Production watermark unavailable: PerthImplicitWatermarker is missing. "
            "Upgrade the official resemble-perth package before release generation. "
            "Use --private-unwatermarked only for private QA."
        )

    class PrivateAuditionWatermarker:
        def __init__(self, *args, **kwargs):
            pass
        def apply_watermark(self, wav, sample_rate=None, **kwargs):
            return wav
        def get_watermark(self, wav, sample_rate=None, **kwargs):
            return 0.0

    perth.PerthImplicitWatermarker = PrivateAuditionWatermarker
    return True


def _patch_s3_mel(model):
    import torch.nn.functional as F

    tok = getattr(getattr(model, "s3gen", None), "tokenizer", None)
    if tok is None:
        raise RuntimeError("Could not locate Chatterbox S3 tokenizer")

    def dtype_safe_log_mel(self, audio, padding=0):
        if not torch.is_tensor(audio):
            audio = torch.from_numpy(np.asarray(audio))
        audio = audio.to(device=self.device, dtype=torch.float32)
        if padding > 0:
            audio = F.pad(audio, (0, padding))
        window = self.window.to(device=self.device, dtype=torch.float32)
        stft = torch.stft(
            audio,
            self.n_fft,
            160,
            window=window,
            return_complex=True,
        )
        magnitudes = (stft[..., :-1].abs() ** 2).to(torch.float32)
        filters = self._mel_filters.to(device=self.device, dtype=torch.float32)
        mel_spec = filters @ magnitudes
        log_spec = torch.clamp(mel_spec, min=1e-10).log10()
        log_spec = torch.maximum(log_spec, log_spec.max() - 8.0)
        return (log_spec + 4.0) / 4.0

    tok.log_mel_spectrogram = types.MethodType(dtype_safe_log_mel, tok)


def _patch_voice_encoder(model):
    ve = getattr(model, "ve", None)
    if ve is None:
        raise RuntimeError("Could not locate Chatterbox voice encoder")

    original_embeds = ve.embeds_from_mels
    original_forward = ve.forward

    def safe_embeds(self, mels, mel_lens=None, as_spk=False, batch_size=32, **kwargs):
        if isinstance(mels, list):
            mels = [np.asarray(x, dtype=np.float32) for x in mels]
        elif torch.is_tensor(mels):
            mels = mels.to(dtype=torch.float32)
        else:
            mels = np.asarray(mels, dtype=np.float32)
        return original_embeds(
            mels, mel_lens=mel_lens, as_spk=as_spk,
            batch_size=batch_size, **kwargs
        )

    def safe_forward(self, mels):
        dtype = self.lstm.weight_ih_l0.dtype
        mels = mels.to(device=self.device, dtype=dtype)
        return original_forward(mels)

    ve.embeds_from_mels = types.MethodType(safe_embeds, ve)
    ve.forward = types.MethodType(safe_forward, ve)


def _verify_synthesis_word_integrity(text: str):
    from chatterbox.tts_turbo import punc_norm
    normalized = punc_norm(text)
    a = lexical_tokens(text)
    b = lexical_tokens(normalized)
    if a != b:
        for i, pair in enumerate(zip(a, b)):
            if pair[0] != pair[1]:
                raise RuntimeError(
                    f"Chatterbox normalization changed lexical token {i}: "
                    f"{pair[0]!r} -> {pair[1]!r}"
                )
        raise RuntimeError(
            f"Chatterbox normalization changed word count: {len(a)} -> {len(b)}"
        )


def choose_device(requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_runtime(
    device: str = "auto",
    allow_private_unwatermarked: bool = False,
) -> VoiceRuntime:
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    bypass = _install_private_watermark_fallback(allow_private_unwatermarked)

    from chatterbox.tts_turbo import ChatterboxTurboTTS

    device = choose_device(device)
    sig = inspect.signature(ChatterboxTurboTTS.from_pretrained)
    if "nano" in sig.parameters:
        model = ChatterboxTurboTTS.from_pretrained(device=device, nano=True)
        engine = "Chatterbox Nano"
    else:
        model = ChatterboxTurboTTS.from_pretrained(device=device)
        engine = "Chatterbox Turbo"

    _patch_s3_mel(model)
    _patch_voice_encoder(model)

    return VoiceRuntime(
        model=model,
        engine=engine,
        device=device,
        watermarked=not bypass,
        private_unwatermarked=bypass,
    )


def deterministic_seed(text_bytes: bytes, namespace: str = "jakeai") -> int:
    h = hashlib.sha256(namespace.encode() + b"\0" + text_bytes).digest()
    return int.from_bytes(h[:4], "big")


def synthesize(
    runtime: VoiceRuntime,
    text: str,
    reference_wav: str | Path,
    *,
    namespace: str = "jakeai",
    verify_words: bool = True,
):
    if verify_words:
        _verify_synthesis_word_integrity(text)

    seed = deterministic_seed(text.encode("utf-8"), namespace)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    wav = runtime.model.generate(
        text,
        audio_prompt_path=str(Path(reference_wav).resolve()),
    )
    if not torch.is_tensor(wav):
        wav = torch.as_tensor(wav)
    return wav.to(torch.float32), runtime.model.sr, seed


def normalize_audio(wav: torch.Tensor, target_peak_db: float = -3.0) -> tuple[torch.Tensor, dict]:
    wav = wav.to(torch.float32)
    if not torch.isfinite(wav).all():
        raise RuntimeError("Generated audio contains NaN or infinity")
    peak = float(wav.abs().max().item()) if wav.numel() else 0.0
    if peak <= 0:
        raise RuntimeError("Generated audio is silent")
    target = float(10 ** (target_peak_db / 20.0))
    gain = min(target / peak, 10 ** (6.0 / 20.0))
    out = wav * gain
    rms = float(torch.sqrt(torch.mean(out ** 2)).item())
    return out, {
        "input_peak": peak,
        "gain": gain,
        "output_peak": float(out.abs().max().item()),
        "output_rms": rms,
        "target_peak_dbfs": target_peak_db,
    }


def save_wav(path: str | Path, wav: torch.Tensor, sample_rate: int):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(path), wav.cpu(), sample_rate)
    if not path.exists() or path.stat().st_size < 1024:
        raise RuntimeError(f"Audio file was not written correctly: {path}")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
