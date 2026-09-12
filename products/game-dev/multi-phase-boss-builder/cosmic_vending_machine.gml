/// JakeAI Multi-Phase Boss Builder Autopilot v0.2
/// Cosmic Vending Machine reference scaffold
/// Original prototype for GameMaker integration testing.

/// CREATE EVENT
max_hp = 300;
hp = max_hp;
phase = 1;
state = "idle";
state_timer = 20;
can_take_damage = false;
phase_transition_locked = false;
products_returned = 0;
objective_complete = false;
encounter_complete_fired = false;

telegraph_frames = 45;
attack_frames = 30;
recovery_frames = 50;
phase2_hp_threshold = 200;
phase3_hp_threshold = 100;
receipt_reflect_damage = 25;
required_returns = 3;

function set_state(_next_state, _duration) {
    state = _next_state;
    state_timer = max(0, _duration);
    can_take_damage = (state == "recovery" && phase < 3);
}

function begin_attack_cycle() {
    switch (phase) {
        case 1: set_state("snack_storm_telegraph", telegraph_frames); break;
        case 2: set_state("refund_denied_telegraph", telegraph_frames); break;
        case 3: set_state("return_to_sender_telegraph", telegraph_frames); break;
    }
}

function advance_phase(_next_phase) {
    if (phase_transition_locked || state == "defeated") return false;
    if (_next_phase <= phase || _next_phase > 3) return false;
    phase_transition_locked = true;
    phase = _next_phase;
    set_state("phase_transition", 90);
    return true;
}

function finish_phase_transition() {
    phase_transition_locked = false;
    set_state("idle", 20);
}

function boss_apply_damage(_amount) {
    if (!can_take_damage || phase == 3 || state == "defeated") return false;
    var _damage = max(0, _amount);
    if (_damage <= 0) return false;
    hp = max(0, hp - _damage);
    return true;
}

function register_reflected_receipt() {
    if (phase != 2 || state != "recovery") return false;
    return boss_apply_damage(receipt_reflect_damage);
}

function register_product_return() {
    if (phase != 3 || state == "defeated") return false;
    products_returned = min(products_returned + 1, required_returns);
    if (products_returned >= required_returns) {
        objective_complete = true;
        set_state("defeated", 0);
    }
    return true;
}

/// STEP EVENT
if (state == "defeated") {
    if (!encounter_complete_fired) {
        encounter_complete_fired = true;
        // Production integration: reward / completion signal here once.
    }
    exit;
}

if (!phase_transition_locked) {
    if (phase == 1 && hp <= phase2_hp_threshold) advance_phase(2);
    else if (phase == 2 && hp <= phase3_hp_threshold) advance_phase(3);
}

if (state_timer > 0) state_timer--;

switch (state) {
    case "idle":
        if (state_timer <= 0) begin_attack_cycle();
        break;
    case "phase_transition":
        if (state_timer <= 0) finish_phase_transition();
        break;
    case "snack_storm_telegraph":
        if (state_timer <= 0) set_state("snack_storm_active", attack_frames);
        break;
    case "snack_storm_active":
        if (state_timer <= 0) set_state("recovery", recovery_frames);
        break;
    case "refund_denied_telegraph":
        if (state_timer <= 0) set_state("refund_denied_active", attack_frames);
        break;
    case "refund_denied_active":
        if (state_timer <= 0) set_state("recovery", recovery_frames);
        break;
    case "return_to_sender_telegraph":
        if (state_timer <= 0) set_state("return_to_sender_active", attack_frames);
        break;
    case "return_to_sender_active":
        if (objective_complete) set_state("defeated", 0);
        else if (state_timer <= 0) set_state("recovery", recovery_frames);
        break;
    case "recovery":
        if (state_timer <= 0) set_state("idle", 15);
        break;
}
