extends Node

signal credit_pressed
signal start_pressed
signal operator_pressed

const ACTION_KEYS := {
    "cabinet_credit": KEY_F1,
    "cabinet_start": KEY_ENTER,
    "cabinet_operator": KEY_F2,
    "move_left": KEY_LEFT,
    "move_right": KEY_RIGHT,
    "move_up": KEY_UP,
    "move_down": KEY_DOWN,
    "seismic_charge": KEY_J,
    "shock_pulse": KEY_K,
    "reactive_shield": KEY_L,
    "drill_dash": KEY_I
}

func _ready() -> void:
    _ensure_default_actions()

func _process(_delta: float) -> void:
    if Input.is_action_just_pressed("cabinet_credit"):
        ArcadeRuntime.add_credit(1)
        credit_pressed.emit()
    if Input.is_action_just_pressed("cabinet_start"):
        if ArcadeRuntime.request_start():
            start_pressed.emit()
    if Input.is_action_just_pressed("cabinet_operator"):
        ArcadeRuntime.set_operator_mode(not ArcadeRuntime.operator_mode)
        operator_pressed.emit()

func _ensure_default_actions() -> void:
    for action in ACTION_KEYS.keys():
        if not InputMap.has_action(action):
            InputMap.add_action(action)
        if InputMap.action_get_events(action).is_empty():
            var event := InputEventKey.new()
            event.physical_keycode = ACTION_KEYS[action]
            InputMap.action_add_event(action, event)
