/// JakeAI Multi-Phase Boss Builder Autopilot v0.1
/// Cosmic Vending Machine reference scaffold
/// Original prototype for GameMaker integration testing.

/// ----------------------------
/// CREATE EVENT
/// ----------------------------

max_hp = 300;
hp = max_hp;
phase = 1;
state = "idle";
state_timer = 0;
attack_index = 0;
can_take_damage = true;
phase_transition_locked = false;
products_returned = 0;
objective_complete = false;

// Centralized tuning values
telegraph_frames = 45;
attack_frames = 30;
recovery_frames = 50;
phase2_hp_threshold = 200;
phase3_hp_threshold = 100;
receipt_reflect_damage = 25;
required_returns = 3;

function set_state(_next_state, _duration) {
    state = _next_state;
    state_timer = _duration;
}

function begin_attack_cycle() {
    switch (phase) {
        case 1:
            set_state("snack_storm_telegraph", telegraph_frames);
            break;
        case 2:
            set_state("refund_denied_telegraph", telegraph_frames);
            break;
        case 3:
            set_state("return_to_sender_telegraph", telegraph_frames);
            break;
    }
}

function advance_phase(_next_phase) {
    if (phase_transition_locked) return;
    phase_transition_locked = true;
    phase = _next_phase;
    can_take_damage = false;
    set_state("phase_transition", 90);
}

function finish_phase_transition() {
    phase_transition_locked = false;
    can_take_damage = (phase < 3);
    set_state("idle", 20);
}

function register_reflected_receipt() {
    if (phase != 2) return;
    if (!can_take_damage) return;
    hp -= receipt_reflect_damage;
}

function register_product_return() {
    if (phase != 3) return;
    products_returned = min(products_returned + 1, required_returns);
    if (products_returned >= required_returns) {
        objective_complete = true;
        set_state("defeated", 0);
    }
}

/// ----------------------------
/// STEP EVENT
/// ----------------------------

if (state == "defeated") {
    // Trigger reward / encounter completion exactly once in production integration.
    exit;
}

if (phase == 1 && hp <= phase2_hp_threshold) {
    advance_phase(2);
}

if (phase == 2 && hp <= phase3_hp_threshold) {
    advance_phase(3);
}

if (state_timer > 0) {
    state_timer--;
}

switch (state) {
    case "idle":
        if (state_timer <= 0) begin_attack_cycle();
        break;

    case "phase_transition":
        if (state_timer <= 0) finish_phase_transition();
        break;

    case "snack_storm_telegraph":
        // Spawn visible warning markers for falling product hazards.
        if (state_timer <= 0) set_state("snack_storm_active", attack_frames);
        break;

    case "snack_storm_active":
        // Spawn falling hazards here.
        if (state_timer <= 0) set_state("recovery", recovery_frames);
        break;

    case "refund_denied_telegraph":
        // Cue conveyor direction and receipt-emitter timing.
        if (state_timer <= 0) set_state("refund_denied_active", attack_frames);
        break;

    case "refund_denied_active":
        // Activate conveyors and spawn reflectable receipt projectiles.
        if (state_timer <= 0) set_state("recovery", recovery_frames);
        break;

    case "return_to_sender_telegraph":
        // Highlight mismatched products and matching destination slots.
        if (state_timer <= 0) set_state("return_to_sender_active", attack_frames);
        break;

    case "return_to_sender_active":
        // Maintain survival hazards while objective items remain active.
        if (objective_complete) {
            set_state("defeated", 0);
        } else if (state_timer <= 0) {
            set_state("recovery", recovery_frames);
        }
        break;

    case "recovery":
        if (state_timer <= 0) set_state("idle", 15);
        break;
}

/// ----------------------------
/// DAMAGE ENTRY POINT
/// ----------------------------
/// Call from the collision/projectile system.

function boss_apply_damage(_amount) {
    if (!can_take_damage) return false;
    if (phase == 3) return false; // Phase 3 is objective-driven, not HP-driven.

    hp = max(0, hp - max(0, _amount));
    return true;
}
