from pathlib import Path
ROOT = Path('deep-shift-mobile')

def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

def replace(rel, old, new):
    p=ROOT/rel
    s=p.read_text()
    if old not in s:
        raise SystemExit(f'PASS13 PATCH MISS: {rel}: {old[:80]!r}')
    p.write_text(s.replace(old,new,1))

mobile = r'''extends CanvasLayer

var held := {}

func _ready() -> void:
    layer = 20
    if not OS.has_feature("web") and not OS.has_feature("mobile"):
        visible = false
        return
    _build_ui()

func _build_ui() -> void:
    var root := Control.new()
    root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    root.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(root)

    var hint := Label.new()
    hint.text = "TOUCH: MOVE • DIG • ABILITIES"
    hint.position = Vector2(16, 74)
    hint.add_theme_font_size_override("font_size", 16)
    hint.modulate = Color(0.75,0.94,1.0,0.85)
    root.add_child(hint)

    _add_hold(root, "move_left", "◀", Vector2(24, 500), Vector2(74,74))
    _add_hold(root, "move_right", "▶", Vector2(176, 500), Vector2(74,74))
    _add_hold(root, "move_up", "▲", Vector2(100, 424), Vector2(74,74))
    _add_hold(root, "move_down", "▼", Vector2(100, 576), Vector2(74,74))

    _add_tap(root, "charge", "CHARGE", Vector2(880, 500), Vector2(110,62))
    _add_tap(root, "pulse", "PULSE", Vector2(1000, 426), Vector2(110,62))
    _add_tap(root, "dash", "DASH", Vector2(1000, 574), Vector2(110,62))
    _add_tap(root, "shield", "SHIELD", Vector2(1120, 500), Vector2(110,62))

func _style_button(b: Button) -> void:
    b.add_theme_font_size_override("font_size", 18)
    b.modulate = Color(0.86,0.96,1.0,0.92)
    b.mouse_filter = Control.MOUSE_FILTER_STOP

func _add_hold(root: Control, action: String, label: String, pos: Vector2, size: Vector2) -> void:
    var b := Button.new()
    b.text = label
    b.position = pos
    b.size = size
    _style_button(b)
    root.add_child(b)
    b.button_down.connect(func(): Input.action_press(action); held[action]=true)
    b.button_up.connect(func(): Input.action_release(action); held.erase(action))

func _add_tap(root: Control, action: String, label: String, pos: Vector2, size: Vector2) -> void:
    var b := Button.new()
    b.text = label
    b.position = pos
    b.size = size
    _style_button(b)
    root.add_child(b)
    b.pressed.connect(func():
        Input.action_press(action)
        await get_tree().process_frame
        Input.action_release(action)
    )

func _exit_tree() -> void:
    for action in held.keys():
        Input.action_release(action)
'''
write('scripts/MobileControls.gd', mobile)

scene = ROOT/'scenes/Game.tscn'
s=scene.read_text()
if 'MobileControls.gd' not in s:
    s=s.replace('[ext_resource path="res://scripts/Game.gd" type="Script" id="1"]', '[ext_resource path="res://scripts/Game.gd" type="Script" id="1"]\n[ext_resource path="res://scripts/MobileControls.gd" type="Script" id="97"]',1)
    s += '\n[node name="MobileControls" type="CanvasLayer" parent="."]\nscript = ExtResource("97")\n'
scene.write_text(s)

# Web/mobile-friendly stretch and viewport.
proj=ROOT/'project.godot'
s=proj.read_text()
if '[display]' not in s and '[display/window]' not in s:
    s += '\n[display]\n\n'
if 'window/stretch/mode' not in s:
    s += '\n[display/window]\nsize/viewport_width=1280\nsize/viewport_height=720\nsize/window_width_override=1280\nsize/window_height_override=720\nstretch/mode="canvas_items"\nhandheld/orientation=1\n'
proj.write_text(s)

print('DEEP_SHIFT_PASS13_MOBILE_WEB_LAYER: PASS')
