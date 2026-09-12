extends Node

const SOUND_PATHS := {
    "dig": "res://assets/audio/dig.wav",
    "ore": "res://assets/audio/ore.wav",
    "pulse": "res://assets/audio/pulse.wav",
    "charge": "res://assets/audio/charge.wav",
    "hurt": "res://assets/audio/hurt.wav",
    "boss_warning": "res://assets/audio/boss_warning.wav",
    "extract": "res://assets/audio/extract.wav"
}

var players: Array[AudioStreamPlayer] = []
var sounds: Dictionary = {}

func _ready() -> void:
    for id in SOUND_PATHS.keys():
        var path: String = String(SOUND_PATHS[id])
        if ResourceLoader.exists(path):
            sounds[id] = load(path)
    for _i in 8:
        var p := AudioStreamPlayer.new()
        p.bus = "Master"
        add_child(p)
        players.append(p)

func play(id: String, pitch: float = 1.0) -> void:
    if not sounds.has(id):
        return
    for p in players:
        if not p.playing:
            p.stream = sounds[id]
            p.pitch_scale = pitch
            p.volume_db = linear_to_db(clamp(float(Settings.master_volume), 0.001, 1.0))
            p.play()
            return
