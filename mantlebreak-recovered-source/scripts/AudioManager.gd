extends Node

const SOUNDS := {
    "dig": preload("res://assets/audio/dig.wav"),
    "ore": preload("res://assets/audio/ore.wav"),
    "pulse": preload("res://assets/audio/pulse.wav"),
    "charge": preload("res://assets/audio/charge.wav"),
    "hurt": preload("res://assets/audio/hurt.wav"),
    "boss_warning": preload("res://assets/audio/boss_warning.wav"),
    "extract": preload("res://assets/audio/extract.wav")
}

var players: Array[AudioStreamPlayer] = []

func _ready() -> void:
    for i in 8:
        var p := AudioStreamPlayer.new()
        p.bus = "Master"
        add_child(p)
        players.append(p)

func play(id: String, pitch := 1.0) -> void:
    if not SOUNDS.has(id):
        return
    for p in players:
        if not p.playing:
            p.stream = SOUNDS[id]
            p.pitch_scale = pitch
            p.volume_db = linear_to_db(clamp(Settings.master_volume,0.001,1.0))
            p.play()
            return
