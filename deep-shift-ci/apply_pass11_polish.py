from pathlib import Path

ROOT = Path("deep-shift-playtest")


def replace(path: str, old: str, new: str) -> None:
    p = ROOT / path
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"PASS11 PATCH MISS: {path}: {old[:80]!r}")
    p.write_text(s.replace(old, new, 1))

# HUD: distinguish ore objective from credits and add a persistent hint line.
replace(
    "scripts/HUD.gd",
    '    $Panel/HBox/Ore.text = "Credits %d" % int(GameState.run.credits)\n',
    '    var game := get_parent()\n    var ore_now := int(game.get("ore_collected")) if game != null else 0\n    var requirement := 0\n    if game != null and not game.get("sector_data").is_empty():\n        var sector_index := int(game.get("sector_index"))\n        requirement = 0 if sector_index == 4 else int(min(int(game.get("sector_data").ore_count), 5 + sector_index))\n    $Panel/HBox/Ore.text = "ORE %d/%d" % [ore_now, requirement]\n    $Panel/HBox/Credits.text = "CREDITS %d" % int(GameState.run.credits)\n'
)
replace(
    "scripts/HUD.gd",
    'func set_status(text: String) -> void:\n    $Status.text = text\n',
    'func set_status(text: String) -> void:\n    $Status.text = text\n\nfunc set_hint(text: String) -> void:\n    $Hint.text = text\n'
)

# Add Credits and Hint labels to the gameplay scene.
replace(
    "scenes/Game.tscn",
    '[node name="Energy" type="Label" parent="HUD/Panel/HBox"]\n',
    '[node name="Credits" type="Label" parent="HUD/Panel/HBox"]\nlayout_mode = 2\ntext = "CREDITS 0"\n\n[node name="Energy" type="Label" parent="HUD/Panel/HBox"]\n'
)
replace(
    "scenes/Game.tscn",
    'text = "Begin the expedition."\n\n[node name="UpgradePanel" parent="." instance=ExtResource("10")]\n',
    'text = "Begin the expedition."\n\n[node name="Hint" type="Label" parent="HUD"]\noffset_left = 16.0\noffset_top = 136.0\noffset_right = 1230.0\noffset_bottom = 172.0\ntext = "MOVE: WASD/ARROWS  •  DIG: MOVE THROUGH SOIL  •  B CHARGE  •  SPACE PULSE  •  SHIFT DASH  •  Q SHIELD  •  ESC/START PAUSE"\ntheme_override_font_sizes/font_size = 13\n\n[node name="UpgradePanel" parent="." instance=ExtResource("10")]\n'
)

# Game-facing onboarding and state explanations.
replace(
    "scripts/Game.gd",
    '    hud.set_status("%s  •  Secure ore, survive, reach extraction." % sector_data.get("briefing", "Begin the expedition."))\n    hud.refresh()\n',
    '    hud.set_status("%s  •  Secure ore, survive, reach extraction." % sector_data.get("briefing", "Begin the expedition."))\n    if index == 0:\n        hud.set_hint("MOVE: WASD/ARROWS • DIG BY MOVING THROUGH SOIL • B CHARGE • SPACE PULSE • SHIFT DASH • Q SHIELD • ESC/START PAUSE")\n    elif index == 4:\n        hud.set_hint("FINAL SECTOR: DESTROY THE CORE WARDEN, THEN REACH EXTRACTION.")\n    else:\n        hud.set_hint("OBJECTIVE: SECURE REQUIRED ORE, SURVIVE, THEN REACH EXTRACTION.")\n    hud.refresh()\n'
)
replace(
    "scripts/Game.gd",
    'func _on_player_energy_changed(value: int) -> void:\n    GameState.run.energy = value\n    hud.refresh()\n',
    'func _on_player_energy_changed(value: int) -> void:\n    GameState.run.energy = value\n    if value <= 0:\n        hud.set_status("POWER DEPLETED — emergency recharge engaged. Movement reduced temporarily.")\n        hud.set_hint("LOW POWER: KEEP MOVING. EMERGENCY SYSTEM RESTORES A SMALL ENERGY RESERVE.")\n    hud.refresh()\n'
)
replace(
    "scripts/Game.gd",
    'func _on_boss_defeated() -> void:\n    boss_alive = false\n',
    'func _on_boss_defeated() -> void:\n    boss_alive = false\n    hud.set_hint("CORE WARDEN DESTROYED • EXTRACTION UNLOCKED • REACH THE BEACON.")\n'
)
replace(
    "scripts/Game.gd",
    '    if sector_index == 4 and boss_alive:\n        hud.set_status("Core Warden still active.")\n        return\n',
    '    if sector_index == 4 and boss_alive:\n        hud.set_status("EXTRACTION LOCKED — Core Warden still active.")\n        hud.set_hint("DESTROY THE CORE WARDEN BEFORE EXTRACTION CAN OPEN.")\n        return\n'
)
replace(
    "scripts/Game.gd",
    '    if ore_collected < requirement:\n        hud.set_status("Extraction locked — need %d more ore." % (requirement - ore_collected))\n        return\n',
    '    if ore_collected < requirement:\n        hud.set_status("EXTRACTION LOCKED — need %d more ore." % (requirement - ore_collected))\n        hud.set_hint("ORE IS THE SECTOR OBJECTIVE. CREDITS ARE YOUR RUN ECONOMY.")\n        return\n'
)
replace(
    "scripts/Game.gd",
    '    hud.set_status("Sector cleared. Choose an upgrade.")\n    upgrade_panel.show_choices(sector_generator.draft_upgrades(3))\n',
    '    hud.set_status("SECTOR CLEARED — choose one upgrade.")\n    hud.set_hint("GAMEPLAY PAUSED WHILE YOU CHOOSE AN UPGRADE.")\n    upgrade_panel.show_choices(sector_generator.draft_upgrades(3))\n'
)

# Menu hint: make controller availability visible before starting.
replace(
    "scenes/Main.tscn",
    'text = "WASD / ARROWS • B CHARGE • SPACE PULSE • SHIFT DASH • Q SHIELD"\n',
    'text = "KEYBOARD: WASD/ARROWS • B CHARGE • SPACE PULSE • SHIFT DASH • Q SHIELD • ESC PAUSE   |   CONTROLLER SUPPORTED • START PAUSE"\n'
)

# Upgrade screen explicitly tells the tester the game is paused.
replace(
    "scenes/UpgradePanel.tscn",
    'text = "SECTOR CLEARED — CHOOSE ONE UPGRADE"\n',
    'text = "SECTOR CLEARED — GAMEPLAY PAUSED — CHOOSE ONE UPGRADE"\n'
)

print("DEEP_SHIFT_PASS11_POLISH_LAYER: PASS")
