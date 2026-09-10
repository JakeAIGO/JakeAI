extends Node2D

signal cell_dug(cell: Vector2i)
signal terrain_ready

@export var cell_size := 48
@export var columns := 24
@export var rows := 13

var solid_cells: Dictionary = {}
var cell_nodes: Dictionary = {}

func build_from_seed(seed_value: int, spawn_world: Vector2, exit_world: Vector2) -> void:
    clear()
    var rng := RandomNumberGenerator.new()
    rng.seed = seed_value
    for y in rows:
        for x in columns:
            _set_solid(Vector2i(x, y), true)
    var current := Vector2i(2, 3)
    var end := world_to_cell(exit_world)
    _set_solid(current, false)
    var safety := 0
    while current != end and safety < 500:
        safety += 1
        var dx := sign(end.x - current.x)
        var dy := sign(end.y - current.y)
        if rng.randf() < 0.55 and dx != 0:
            current.x += dx
        elif dy != 0:
            current.y += dy
        elif dx != 0:
            current.x += dx
        _set_solid(current, false)
        if rng.randf() < 0.28:
            var branch := current + Vector2i(rng.randi_range(-1,1), rng.randi_range(-1,1))
            if _in_bounds(branch):
                _set_solid(branch, false)
    var start := world_to_cell(spawn_world)
    for yy in range(start.y - 1, start.y + 2):
        for xx in range(start.x - 1, start.x + 2):
            var c := Vector2i(xx, yy)
            if _in_bounds(c):
                _set_solid(c, false)
    for i in 55:
        var c := Vector2i(rng.randi_range(1, columns - 2), rng.randi_range(1, rows - 2))
        _set_solid(c, false)
    terrain_ready.emit()

func clear() -> void:
    solid_cells.clear()
    for n in cell_nodes.values():
        if is_instance_valid(n):
            n.queue_free()
    cell_nodes.clear()

func world_to_cell(pos: Vector2) -> Vector2i:
    return Vector2i(floor(pos.x / cell_size), floor(pos.y / cell_size))

func cell_to_world(cell: Vector2i) -> Vector2:
    return Vector2(cell.x * cell_size + cell_size * 0.5, cell.y * cell_size + cell_size * 0.5)

func is_solid_world(pos: Vector2) -> bool:
    return is_solid_cell(world_to_cell(pos))

func is_solid_cell(cell: Vector2i) -> bool:
    return bool(solid_cells.get(cell, false))

func dig_world(pos: Vector2) -> bool:
    return dig_cell(world_to_cell(pos))

func dig_cell(cell: Vector2i) -> bool:
    if not _in_bounds(cell) or not is_solid_cell(cell):
        return false
    _set_solid(cell, false)
    cell_dug.emit(cell)
    return true

func dig_radius(center_world: Vector2, radius_cells: int) -> int:
    var center := world_to_cell(center_world)
    var removed := 0
    for y in range(center.y - radius_cells, center.y + radius_cells + 1):
        for x in range(center.x - radius_cells, center.x + radius_cells + 1):
            var c := Vector2i(x,y)
            if center.distance_to(c) <= radius_cells + 0.4 and dig_cell(c):
                removed += 1
    return removed

func _set_solid(cell: Vector2i, value: bool) -> void:
    if not _in_bounds(cell):
        return
    solid_cells[cell] = value
    if value:
        if not cell_nodes.has(cell):
            var body := StaticBody2D.new()
            body.position = cell_to_world(cell)
            var shape := CollisionShape2D.new()
            var rect := RectangleShape2D.new()
            rect.size = Vector2(cell_size, cell_size)
            shape.shape = rect
            body.add_child(shape)
            add_child(body)
            cell_nodes[cell] = body
    elif cell_nodes.has(cell):
        var n = cell_nodes[cell]
        if is_instance_valid(n):
            n.queue_free()
        cell_nodes.erase(cell)

func _in_bounds(cell: Vector2i) -> bool:
    return cell.x >= 0 and cell.y >= 0 and cell.x < columns and cell.y < rows

func get_open_neighbors(cell: Vector2i) -> Array[Vector2i]:
    var result: Array[Vector2i] = []
    for d in [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]:
        var n := cell + d
        if _in_bounds(n) and not is_solid_cell(n):
            result.append(n)
    return result

func find_path_world(from_world: Vector2, to_world: Vector2, max_nodes := 600) -> Array[Vector2]:
    var start := world_to_cell(from_world)
    var goal := world_to_cell(to_world)
    if start == goal:
        return [cell_to_world(goal)]
    var frontier: Array[Vector2i] = [start]
    var came_from: Dictionary = {start: start}
    var index := 0
    while index < frontier.size() and frontier.size() <= max_nodes:
        var current: Vector2i = frontier[index]
        index += 1
        if current == goal:
            break
        for next in get_open_neighbors(current):
            if not came_from.has(next):
                came_from[next] = current
                frontier.append(next)
    if not came_from.has(goal):
        return []
    var cells: Array[Vector2i] = []
    var cur := goal
    while cur != start:
        cells.push_front(cur)
        cur = came_from[cur]
    var result: Array[Vector2] = []
    for c in cells:
        result.append(cell_to_world(c))
    return result

func has_support_below(world_pos: Vector2) -> bool:
    var c := world_to_cell(world_pos)
    var below := c + Vector2i.DOWN
    if not _in_bounds(below):
        return true
    return is_solid_cell(below)
