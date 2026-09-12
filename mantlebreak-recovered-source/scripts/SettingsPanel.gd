extends Control

func _ready() -> void:
    $Panel/VBox/Master.value = Settings.master_volume * 100.0
    $Panel/VBox/Shake.button_pressed = Settings.screen_shake
    $Panel/VBox/ReduceMotion.button_pressed = Settings.reduce_motion
    $Panel/VBox/Flash.value = Settings.flash_intensity * 100.0

func _on_master_value_changed(value: float) -> void:
    Settings.master_volume = value / 100.0
    Settings.save_settings()

func _on_shake_toggled(value: bool) -> void:
    Settings.screen_shake = value
    Settings.save_settings()

func _on_reduce_motion_toggled(value: bool) -> void:
    Settings.reduce_motion = value
    Settings.save_settings()

func _on_flash_value_changed(value: float) -> void:
    Settings.flash_intensity = value / 100.0
    Settings.save_settings()
