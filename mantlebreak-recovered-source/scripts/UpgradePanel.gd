extends Control

signal upgrade_selected(id: String)

var current_choices: Array[Dictionary] = []

func show_choices(choices: Array[Dictionary]) -> void:
    current_choices = choices
    show()
    for i in 3:
        var button: Button = get_node("Panel/VBox/Choices/Choice%d" % (i + 1))
        if i < choices.size():
            var choice := choices[i]
            button.text = "%s\n%s" % [choice.name, choice.description]
            button.disabled = false
            button.set_meta("upgrade_id", choice.id)
        else:
            button.text = "Unavailable"
            button.disabled = true

func _ready() -> void:
    hide()
    for i in 3:
        var button: Button = get_node("Panel/VBox/Choices/Choice%d" % (i + 1))
        button.pressed.connect(_on_choice_pressed.bind(button))

func _on_choice_pressed(button: Button) -> void:
    var id := str(button.get_meta("upgrade_id", ""))
    if id.is_empty():
        return
    hide()
    upgrade_selected.emit(id)
