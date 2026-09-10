extends CanvasLayer

const BUTTON_SIZE := Vector2(92, 92)

func _ready() -> void:
    if not OS.has_feature("android") and not DisplayServer.is_touchscreen_available():
        return
    layer = 100
    var root := Control.new()
    root.name = "MobileControls"
    root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    root.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(root)

    _add_button(root, "←", "move_left", Vector2(28, 590))
    _add_button(root, "→", "move_right", Vector2(220, 590))
    _add_button(root, "↑", "move_up", Vector2(124, 494))
    _add_button(root, "↓", "move_down", Vector2(124, 590))

    _add_button(root, "CHARGE", "seismic_charge", Vector2(824, 590), Vector2(108, 92))
    _add_button(root, "PULSE", "shock_pulse", Vector2(938, 494), Vector2(108, 92))
    _add_button(root, "DASH", "drill_dash", Vector2(1052, 590), Vector2(92, 92))
    _add_button(root, "SHIELD", "reactive_shield", Vector2(1150, 494), Vector2(108, 92))

func _add_button(parent: Control, label: String, action: StringName, pos: Vector2, size := BUTTON_SIZE) -> void:
    if not InputMap.has_action(action):
        InputMap.add_action(action)
    var button := Button.new()
    button.text = label
    button.position = pos
    button.size = size
    button.focus_mode = Control.FOCUS_NONE
    button.modulate = Color(1.0, 1.0, 1.0, 0.72)
    button.mouse_filter = Control.MOUSE_FILTER_STOP
    button.button_down.connect(_press_action.bind(action))
    button.button_up.connect(_release_action.bind(action))
    button.tree_exiting.connect(_release_action.bind(action))
    parent.add_child(button)

func _press_action(action: StringName) -> void:
    Input.action_press(action)

func _release_action(action: StringName) -> void:
    Input.action_release(action)
