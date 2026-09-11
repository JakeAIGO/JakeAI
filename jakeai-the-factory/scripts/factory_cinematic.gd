extends Node3D

@onready var camera_rig: Node3D = $CameraRig
@onready var camera: Camera3D = $CameraRig/Camera3D
@onready var status: Label = $UI/TopLeft/Status
@onready var headline: Label = $UI/TopLeft/Headline
@onready var avatar_anchor: Marker3D = $AvatarAnchor

var elapsed := 0.0
var phase := 0

func _ready() -> void:
	status.text = "WORLD BUILD ACTIVE // CHARACTER GATE ENFORCED"
	_run_intro()

func _process(delta: float) -> void:
	elapsed += delta
	# Slow cinematic orbit without any paid camera dependency.
	camera_rig.position.x = sin(elapsed * 0.18) * 2.2
	camera_rig.position.y = 2.4 + sin(elapsed * 0.31) * 0.22
	camera_rig.look_at(Vector3(0, 1.25, -0.6), Vector3.UP)

func _run_intro() -> void:
	var cues: Array[Dictionary] = [
		{"type":"call","method":"cinematic_cue","args":{"phase":0,"headline":"SYSTEMS OFFLINE","status":"$12.99 origin budget detected."}},
		{"type":"wait","seconds":1.1},
		{"type":"call","method":"cinematic_cue","args":{"phase":1,"headline":"DISCOVERY ARRAY ONLINE","status":"Opportunity Observatory connected."}},
		{"type":"wait","seconds":1.2},
		{"type":"call","method":"cinematic_cue","args":{"phase":2,"headline":"SELF-REPAIR BAY ONLINE","status":"Known failure? Change the cause before retrying."}},
		{"type":"wait","seconds":1.2},
		{"type":"call","method":"cinematic_cue","args":{"phase":3,"headline":"CHARACTER SLOT HELD","status":"Canonical JakeAI master required. Random Guy #7 denied entry."}},
		{"type":"wait","seconds":1.2},
		{"type":"call","method":"cinematic_cue","args":{"phase":4,"headline":"THE FACTORY IS READY","status":"World systems can continue while identity remains protected."}}
	]
	if has_node("/root/SceneDirector"):
		SceneDirector.play_sequence("factory_intro", cues, self)
	else:
		# Safe local fallback keeps the scene useful even before autoload wiring is validated.
		for cue in cues:
			if cue.get("type") == "wait":
				await get_tree().create_timer(float(cue.get("seconds", 0.5))).timeout
			elif cue.get("type") == "call":
				cinematic_cue(cue.get("args", {}))

func cinematic_cue(args: Dictionary) -> void:
	phase = int(args.get("phase", phase))
	headline.text = str(args.get("headline", headline.text))
	status.text = str(args.get("status", status.text))
	match phase:
		0:
			camera.fov = 62.0
		1:
			camera.fov = 58.0
		2:
			camera.fov = 54.0
		3:
			camera.fov = 50.0
		4:
			camera.fov = 56.0

func protagonist_anchor() -> Marker3D:
	return avatar_anchor
