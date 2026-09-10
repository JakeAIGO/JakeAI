from pathlib import Path

ROOT = Path('deep-shift-visual')

def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

def replace(rel, old, new):
    p = ROOT / rel
    s = p.read_text()
    if old not in s:
        raise SystemExit(f'PASS12 PATCH MISS: {rel}: {old[:80]!r}')
    p.write_text(s.replace(old, new, 1))

visual = r'''extends Node2D

@export_enum("player","enemy","boss","ore","rock","hazard","beacon") var kind := "player"
var t := 0.0

func _ready() -> void:
    set_process(true)
    queue_redraw()

func _process(delta: float) -> void:
    t += delta
    if kind in ["ore","hazard","beacon","boss"]:
        queue_redraw()

func _draw() -> void:
    match kind:
        "player": _draw_player()
        "enemy": _draw_enemy()
        "boss": _draw_boss()
        "ore": _draw_ore()
        "rock": _draw_rock()
        "hazard": _draw_hazard()
        "beacon": _draw_beacon()

func _draw_player() -> void:
    # shadow + tracks
    draw_ellipse(Vector2(0, 10), Vector2(25, 10), Color(0,0,0,0.32))
    draw_rect(Rect2(-20,-13,30,7), Color("17212a"), true)
    draw_rect(Rect2(-20,8,30,7), Color("17212a"), true)
    for x in [-17,-8,1]:
        draw_circle(Vector2(x,-9), 3.2, Color("59636b")); draw_circle(Vector2(x,11),3.2,Color("59636b"))
    # armored hull
    var hull := PackedVector2Array([Vector2(-17,-10),Vector2(8,-10),Vector2(16,-4),Vector2(16,5),Vector2(7,10),Vector2(-17,10)])
    draw_colored_polygon(hull, Color("d58a24"))
    draw_polyline(PackedVector2Array([Vector2(-17,-10),Vector2(8,-10),Vector2(16,-4),Vector2(16,5),Vector2(7,10),Vector2(-17,10),Vector2(-17,-10)]), Color("ffd36a"), 2.0)
    # cab, core and forward drill
    draw_colored_polygon(PackedVector2Array([Vector2(-9,-16),Vector2(5,-16),Vector2(9,-9),Vector2(-12,-9)]), Color("243c4a"))
    draw_rect(Rect2(-7,-14,10,4), Color("70ddff"), true)
    draw_circle(Vector2(-15,0), 4.5, Color("34d4ff")); draw_circle(Vector2(-15,0),2.2,Color("d9fbff"))
    var drill := PackedVector2Array([Vector2(16,-7),Vector2(30,0),Vector2(16,7)])
    draw_colored_polygon(drill, Color("a9b5bc")); draw_polyline(PackedVector2Array([Vector2(18,-5),Vector2(25,0),Vector2(18,5)]),Color("e9f1f5"),1.5)
    draw_line(Vector2(20,-4),Vector2(20,4),Color("5c6870"),1.5)

func _draw_enemy() -> void:
    var pulse := 1.0 + sin(t*5.0)*0.05
    draw_circle(Vector2(0,5),16*pulse,Color(0,0,0,0.25))
    var body := PackedVector2Array([Vector2(-14,1),Vector2(-10,-10),Vector2(-2,-15),Vector2(9,-11),Vector2(15,-2),Vector2(11,10),Vector2(0,14),Vector2(-11,10)])
    draw_colored_polygon(body,Color("7f2938"))
    draw_polyline(PackedVector2Array([Vector2(-14,1),Vector2(-10,-10),Vector2(-2,-15),Vector2(9,-11),Vector2(15,-2),Vector2(11,10),Vector2(0,14),Vector2(-11,10)]),Color("d95555"),2)
    for a in [-2.4,-0.8,0.8,2.4]:
        var d := Vector2(cos(a),sin(a)); draw_line(d*10,d*20,Color("52202d"),3)
    draw_circle(Vector2(4,-2),4,Color("ff3b31")); draw_circle(Vector2(5,-3),1.5,Color("ffd0a8"))

func _draw_boss() -> void:
    var pulse := 0.5 + 0.5*sin(t*3.0)
    draw_circle(Vector2.ZERO,40,Color(0.02,0.0,0.0,0.35))
    for i in 8:
        var a := TAU*float(i)/8.0 + t*0.08
        var d := Vector2(cos(a),sin(a))
        draw_colored_polygon(PackedVector2Array([d*24, d.rotated(-0.16)*39, d.rotated(0.16)*39]),Color("411f27"))
        draw_line(d*21,d*37,Color("b54a2f"),2)
    draw_circle(Vector2.ZERO,27,Color("321e25")); draw_arc(Vector2.ZERO,27,0,TAU,48,Color("a54f3c"),3)
    draw_circle(Vector2.ZERO,12+2*pulse,Color("ff5a23")); draw_circle(Vector2.ZERO,6+2*pulse,Color("ffd15a"))
    draw_arc(Vector2.ZERO,18+t%1.0*8,0,TAU,40,Color(1,0.25,0.08,0.35*(1.0-(t%1.0))),2)

func _draw_ore() -> void:
    var glow := 0.75 + 0.25*sin(t*6.0)
    draw_circle(Vector2.ZERO,20,Color(0.1,0.75,1.0,0.08*glow))
    var pts := PackedVector2Array([Vector2(0,-16),Vector2(9,-5),Vector2(7,12),Vector2(-6,15),Vector2(-12,-2)])
    draw_colored_polygon(pts,Color("23bde8")); draw_polyline(PackedVector2Array([Vector2(0,-16),Vector2(9,-5),Vector2(7,12),Vector2(-6,15),Vector2(-12,-2),Vector2(0,-16)]),Color("baf6ff"),2)
    draw_line(Vector2(-2,-11),Vector2(2,10),Color("e7ffff"),1.5)
    for i in 3:
        var a := t*0.8 + i*2.1; var p := Vector2(cos(a),sin(a))*19
        draw_circle(p,1.6,Color("eaffff"))

func _draw_rock() -> void:
    var pts := PackedVector2Array([Vector2(-18,5),Vector2(-12,-12),Vector2(2,-19),Vector2(16,-9),Vector2(19,7),Vector2(8,18),Vector2(-11,15)])
    draw_colored_polygon(pts,Color("4a4d52")); draw_polyline(PackedVector2Array([Vector2(-18,5),Vector2(-12,-12),Vector2(2,-19),Vector2(16,-9),Vector2(19,7),Vector2(8,18),Vector2(-11,15),Vector2(-18,5)]),Color("7e858a"),2)
    draw_line(Vector2(-9,-7),Vector2(3,1),Color("303237"),2); draw_line(Vector2(3,1),Vector2(10,10),Color("303237"),2)

func _draw_hazard() -> void:
    var p := 0.55 + 0.45*sin(t*7.0)
    draw_circle(Vector2.ZERO,20,Color(0.8,0.18,0.65,0.12*p))
    draw_colored_polygon(PackedVector2Array([Vector2(0,-17),Vector2(15,11),Vector2(-15,11)]),Color("ad3f83"))
    draw_polyline(PackedVector2Array([Vector2(0,-17),Vector2(15,11),Vector2(-15,11),Vector2(0,-17)]),Color("ff9ada"),2)
    draw_circle(Vector2(0,4),3+p*2,Color("ffd2ef"))

func _draw_beacon() -> void:
    var p := 0.5 + 0.5*sin(t*4.0)
    draw_rect(Rect2(-15,-25,30,50),Color("173b36"),true)
    draw_rect(Rect2(-11,-21,22,42),Color("245d4d"),true)
    draw_circle(Vector2(0,-10),5,Color("7dffb0"))
    draw_line(Vector2(0,-28),Vector2(0,-42),Color("94ffd0"),2)
    draw_arc(Vector2(0,-38),7+p*4,PI,TAU,24,Color(0.45,1.0,0.75,0.7),2)
    draw_arc(Vector2.ZERO,22+p*5,0,TAU,36,Color(0.35,1.0,0.65,0.3),2)

func draw_ellipse(center: Vector2, radii: Vector2, color: Color) -> void:
    var pts := PackedVector2Array()
    for i in 24:
        var a := TAU*float(i)/24.0
        pts.append(center + Vector2(cos(a)*radii.x,sin(a)*radii.y))
    draw_colored_polygon(pts,color)
'''
write('scripts/VisualArt.gd', visual)

backdrop = r'''extends Node2D
var sector := 0
var sector_names := ["RUST VEINS","CRYSTAL FAULT","MAGMA SHELF","ANCIENT WORKS","CORE NEST"]
func set_sector(v:int)->void: sector=v; queue_redraw()
func _ready()->void: z_index=-50; queue_redraw()
func _draw()->void:
    var palettes = [Color("10161b"),Color("0b1320"),Color("1b1010"),Color("0e1416"),Color("180b10")]
    var accents = [Color("9b5928"),Color("266c91"),Color("d24a22"),Color("47736d"),Color("ba3225")]
    var base:Color=palettes[clamp(sector,0,4)]; var accent:Color=accents[clamp(sector,0,4)]
    draw_rect(Rect2(0,0,1152,624),base,true)
    for y in range(28,624,52):
        var wobble := sin(float(y)*0.07+sector)*12.0
        draw_line(Vector2(0,y+wobble),Vector2(1152,y-wobble),Color(accent,0.12),2)
    for i in 22:
        var x := float((i*137 + sector*83)%1152); var y := float((i*83+sector*57)%624)
        draw_circle(Vector2(x,y),float(2+(i%3)),Color(accent,0.20))
    if sector==1:
        for i in 12:
            var x:=float(40+i*94); draw_colored_polygon(PackedVector2Array([Vector2(x,590),Vector2(x+10,540-(i%3)*18),Vector2(x+22,590)]),Color(0.2,0.72,1.0,0.22))
    elif sector==2 or sector==4:
        for i in 9:
            var x:=float(25+i*135); draw_line(Vector2(x,624),Vector2(x+50,550-(i%2)*35),Color(1.0,0.25,0.05,0.22),5)
    elif sector==3:
        for i in 7:
            var x:=float(i*180); draw_rect(Rect2(x,520-(i%2)*40,120,10),Color(0.3,0.5,0.48,0.18),true)
'''
write('scripts/SectorBackdrop.gd', backdrop)

# Scene visuals: hide old primitive polygons and add custom drawing nodes.
for scene, kind in [('Player.tscn','player'),('Enemy.tscn','enemy'),('Boss.tscn','boss'),('Ore.tscn','ore'),('Rock.tscn','rock'),('Hazard.tscn','hazard'),('ExtractionBeacon.tscn','beacon')]:
    rel='scenes/'+scene
    s=(ROOT/rel).read_text()
    if 'VisualArt.gd' not in s:
        s=s.replace('[ext_resource path="res://scripts/', '[ext_resource path="res://scripts/VisualArt.gd" type="Script" id="99"]\n[ext_resource path="res://scripts/',1)
        s=s.replace('[node name="Body" type="Polygon2D" parent="."]','[node name="Body" type="Polygon2D" parent="."]\nvisible = false',1)
        marker='[node name="CollisionShape2D"'
        insert='[node name="Visual" type="Node2D" parent="."]\nscript = ExtResource("99")\nkind = "%s"\n\n' % kind
        s=s.replace(marker,insert+marker,1)
        (ROOT/rel).write_text(s)

# Backdrop in gameplay world.
game_scene=ROOT/'scenes/Game.tscn'; s=game_scene.read_text()
s=s.replace('[ext_resource path="res://scripts/Game.gd" type="Script" id="1"]','[ext_resource path="res://scripts/Game.gd" type="Script" id="1"]\n[ext_resource path="res://scripts/SectorBackdrop.gd" type="Script" id="98"]',1)
s=s.replace('[node name="World" type="Node2D" parent="."]','[node name="World" type="Node2D" parent="."]\n\n[node name="Backdrop" type="Node2D" parent="World"]\nscript = ExtResource("98")',1)
game_scene.write_text(s)
replace('scripts/Game.gd','    sector_index = index\n    waiting_for_upgrade = false\n','    sector_index = index\n    waiting_for_upgrade = false\n    if has_node("World/Backdrop"):\n        $World/Backdrop.set_sector(index)\n')

# Upgrade terrain from flat squares to layered stone tiles with deterministic insets/cracks.
replace('scripts/TerrainManager.gd','            poly.color = Color(tone + 0.12, tone + 0.04, tone, 1.0)\n            body.add_child(poly)\n','            poly.color = Color(tone + 0.12, tone + 0.04, tone, 1.0)\n            body.add_child(poly)\n            var inset := Polygon2D.new()\n            inset.polygon = PackedVector2Array([Vector2(-h+3,-h+3),Vector2(h-4,-h+2),Vector2(h-2,h-4),Vector2(-h+4,h-2)])\n            inset.color = Color(tone + 0.06, tone + 0.015, tone * 0.82, 1.0)\n            body.add_child(inset)\n            var seam := Line2D.new()\n            seam.width = 1.3\n            seam.default_color = Color(0.08,0.06,0.05,0.45)\n            var sx := float(((cell.x * 13 + cell.y * 5) % 11) - 5)\n            seam.points = PackedVector2Array([Vector2(-h+5,sx),Vector2(-4,sx-5),Vector2(5,sx+3),Vector2(h-5,sx-2)])\n            body.add_child(seam)\n')

# HUD panel gets a darker translucent instrument look.
gs=game_scene.read_text()
gs=gs.replace('[node name="Panel" type="PanelContainer" parent="HUD"]','[node name="Panel" type="PanelContainer" parent="HUD"]\nmodulate = Color(0.82, 0.94, 1, 0.93)',1)
game_scene.write_text(gs)

print('DEEP_SHIFT_PASS12_VISUAL_LAYER: PASS')
