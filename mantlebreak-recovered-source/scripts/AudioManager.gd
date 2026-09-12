extends Node

# JakeAI Arcade Audio Engine v0.1
# Procedural, runtime-generated SFX. No external WAV assets required.

const MIX_RATE: float = 44100.0
const BUFFER_LENGTH: float = 0.5

var player: AudioStreamPlayer
var generator: AudioStreamGenerator
var playback: AudioStreamGeneratorPlayback
var rng_state: int = 123456789

func _ready() -> void:
    generator = AudioStreamGenerator.new()
    generator.mix_rate = MIX_RATE
    generator.buffer_length = BUFFER_LENGTH
    player = AudioStreamPlayer.new()
    player.stream = generator
    player.bus = "Master"
    add_child(player)
    player.play()
    playback = player.get_stream_playback() as AudioStreamGeneratorPlayback

func play(id: String, pitch: float = 1.0) -> void:
    if playback == null:
        return
    var spec: Dictionary = _spec(id)
    var duration: float = float(spec.get("duration", 0.12))
    var f0: float = float(spec.get("f0", 220.0)) * pitch
    var f1: float = float(spec.get("f1", f0)) * pitch
    var amp: float = float(spec.get("amp", 0.25)) * _master_volume()
    var shape: String = String(spec.get("shape", "sine"))
    var count: int = int(MIX_RATE * duration)
    var frames := PackedVector2Array()
    frames.resize(count)
    for i in range(count):
        var t: float = float(i) / MIX_RATE
        var phase: float = float(i) / float(max(1, count - 1))
        var freq: float = lerpf(f0, f1, phase)
        var env: float = pow(1.0 - phase, 1.7)
        var sample: float = _wave(shape, freq, t) * amp * env
        frames[i] = Vector2(sample, sample)
    playback.clear_buffer()
    playback.push_buffer(frames)

func _master_volume() -> float:
    if ArcadeRuntime != null:
        return clamp(float(ArcadeRuntime.master_volume), 0.0, 1.0)
    return 0.85

func _wave(shape: String, freq: float, t: float) -> float:
    var sine_value: float = sin(TAU * freq * t)
    match shape:
        "square":
            return 1.0 if sine_value >= 0.0 else -1.0
        "triangle":
            return asin(sine_value) * (2.0 / PI)
        "crunch":
            rng_state = int((1103515245 * rng_state + 12345) & 0x7fffffff)
            var noise: float = (float(rng_state) / 1073741823.5) - 1.0
            return clamp(sine_value * 0.65 + noise * 0.35, -1.0, 1.0)
        "rumble":
            var low: float = sin(TAU * (freq * 0.5) * t)
            return clamp(sine_value * 0.55 + low * 0.45, -1.0, 1.0)
        _:
            return sine_value

func _spec(id: String) -> Dictionary:
    match id:
        "dig":
            return {"duration":0.07,"f0":95.0,"f1":55.0,"amp":0.30,"shape":"crunch"}
        "ore":
            return {"duration":0.16,"f0":620.0,"f1":980.0,"amp":0.22,"shape":"sine"}
        "pulse":
            return {"duration":0.18,"f0":260.0,"f1":95.0,"amp":0.25,"shape":"triangle"}
        "charge":
            return {"duration":0.22,"f0":80.0,"f1":42.0,"amp":0.32,"shape":"crunch"}
        "hurt":
            return {"duration":0.12,"f0":125.0,"f1":65.0,"amp":0.32,"shape":"square"}
        "boss_warning":
            return {"duration":0.30,"f0":72.0,"f1":48.0,"amp":0.30,"shape":"square"}
        "extract":
            return {"duration":0.34,"f0":330.0,"f1":880.0,"amp":0.23,"shape":"sine"}
        "boost":
            return {"duration":0.14,"f0":140.0,"f1":520.0,"amp":0.26,"shape":"rumble"}
        "shield":
            return {"duration":0.20,"f0":180.0,"f1":260.0,"amp":0.20,"shape":"triangle"}
        _:
            return {"duration":0.10,"f0":220.0,"f1":180.0,"amp":0.20,"shape":"sine"}
