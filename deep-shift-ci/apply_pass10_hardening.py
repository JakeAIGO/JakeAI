from pathlib import Path

ROOT = Path("deep-shift-hardened")


def replace(path: str, old: str, new: str) -> None:
    p = ROOT / path
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"PASS10 PATCH MISS: {path}: {old[:70]!r}")
    p.write_text(s.replace(old, new, 1))

# Player: emergency recovery, limp movement, and hit invulnerability window.
replace("scripts/Player.gd", "var abilities: Node\n", "var abilities: Node\nvar damage_cooldown := 0.0\nvar emergency_recharge_accum := 0.0\n")
replace("scripts/Player.gd", "func _physics_process(delta: float) -> void:\n    var input := Input.get_vector(\"move_left\", \"move_right\", \"move_up\", \"move_down\")\n", "func _physics_process(delta: float) -> void:\n    damage_cooldown = max(0.0, damage_cooldown - delta)\n    if energy <= 0:\n        emergency_recharge_accum += delta\n        if emergency_recharge_accum >= 0.5:\n            emergency_recharge_accum = 0.0\n            energy = min(12, energy + 1)\n            energy_changed.emit(energy)\n    else:\n        emergency_recharge_accum = 0.0\n\n    var input := Input.get_vector(\"move_left\", \"move_right\", \"move_up\", \"move_down\")\n")
replace("scripts/Player.gd", "        velocity = facing * move_speed\n", "        var speed_mult := 0.45 if energy <= 0 else 1.0\n        velocity = facing * move_speed * speed_mult\n")
replace("scripts/Player.gd", "func take_damage(_amount := 1) -> void:\n    if armor > 0:\n", "func take_damage(_amount := 1) -> void:\n    if damage_cooldown > 0.0:\n        return\n    damage_cooldown = 0.75\n    if armor > 0:\n")

# Enemy: contact damage is evaluated before any pathfinding early-return.
replace("scripts/Enemy.gd", "var repath_timer := 0.0\n", "var repath_timer := 0.0\nvar contact_timer := 0.0\n")
replace("scripts/Enemy.gd", "func _physics_process(delta: float) -> void:\n    if not is_instance_valid(target) or terrain == null:\n        velocity = Vector2.ZERO\n        return\n\n    repath_timer -= delta\n", "func _physics_process(delta: float) -> void:\n    contact_timer = max(0.0, contact_timer - delta)\n    if not is_instance_valid(target) or terrain == null:\n        velocity = Vector2.ZERO\n        return\n    if global_position.distance_to(target.global_position) <= 30.0 and contact_timer <= 0.0:\n        if target.has_method(\"take_damage\"):\n            target.take_damage(1)\n            contact_timer = 0.9\n\n    repath_timer -= delta\n")

# Game: freeze the player while choosing an upgrade.
replace("scripts/Game.gd", "    waiting_for_upgrade = true\n    hud.set_status(\"Sector cleared. Choose an upgrade.\")\n", "    waiting_for_upgrade = true\n    if is_instance_valid(player):\n        player.set_physics_process(false)\n        player.velocity = Vector2.ZERO\n    hud.set_status(\"Sector cleared. Choose an upgrade.\")\n")

# Boss: open each telegraphed hazard cell before spawning the ring.
replace("scripts/BossController.gd", "        var offset := Vector2.RIGHT.rotated(deg_to_rad(angle_deg)) * radius\n        h.global_position = global_position + offset\n        hazard_parent.add_child(h)\n", "        var offset := Vector2.RIGHT.rotated(deg_to_rad(angle_deg)) * radius\n        var spawn_pos := global_position + offset\n        if terrain != null:\n            terrain.dig_world(spawn_pos)\n        h.global_position = spawn_pos\n        hazard_parent.add_child(h)\n")

# Sector generator: deterministic upgrade draft tied to run/sector seed.
replace("scripts/SectorGenerator.gd", "func draft_upgrades(count := 3) -> Array[Dictionary]:\n    var choices: Array[Dictionary] = []\n    var indexes := range(UPGRADES.size())\n    indexes.shuffle()\n    for i in min(count, indexes.size()):\n        choices.append(UPGRADES[indexes[i]].duplicate(true))\n    return choices\n", "func draft_upgrades(count := 3) -> Array[Dictionary]:\n    var choices: Array[Dictionary] = []\n    var indexes: Array[int] = []\n    for i in UPGRADES.size():\n        indexes.append(i)\n    var draft_rng := RandomNumberGenerator.new()\n    draft_rng.seed = int((sector_seed(int(GameState.run.sector)) + 7919) & 0x7fffffff)\n    for i in range(indexes.size() - 1, 0, -1):\n        var j := draft_rng.randi_range(0, i)\n        var tmp := indexes[i]\n        indexes[i] = indexes[j]\n        indexes[j] = tmp\n    for i in min(count, indexes.size()):\n        choices.append(UPGRADES[indexes[i]].duplicate(true))\n    return choices\n")

# Controller: Start button pauses too.
p = ROOT / "project.godot"
s = p.read_text()
old = '"events": [Object(InputEventKey,"physical_keycode":4194305)]\n}'
new = '"events": [Object(InputEventKey,"physical_keycode":4194305), Object(InputEventJoypadButton,"button_index":6)]\n}'
if old not in s:
    raise SystemExit("PASS10 PATCH MISS: pause mapping")
p.write_text(s.replace(old, new, 1))

print("DEEP_SHIFT_PASS10_PATCH_LAYER: PASS")
