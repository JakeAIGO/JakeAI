/// JakeAI Boss Builder proof case 02
/// The Abyssal Bellkeeper — generated GameMaker scaffold

// CREATE EVENT
max_hp = 420;
hp = max_hp;
phase = 1;
state = "intro";
state_timer = 60;
transition_locked = false;
can_take_damage = false;
sonar_reveal = false;
weak_point_exposed = false;
bells_broken = 0;
seals_broken = 0;
encounter_complete_fired = false;

phase2_hp = 310;
phase3_hp = 205;
phase4_hp = 100;
telegraph_frames = 50;
attack_frames = 34;
recovery_frames = 55;
sonar_frames = 90;
seal_recycle_frames = 150;
final_exposure_frames = 120;

function bell_set_state(_state, _frames) {
    state = _state;
    state_timer = max(0, _frames);
    can_take_damage = (state == "recovery" || state == "final_exposure");
}

function bell_advance_phase(_next) {
    if (transition_locked || _next <= phase || _next > 4) return false;
    transition_locked = true;
    phase = _next;
    weak_point_exposed = false;
    sonar_reveal = false;
    bell_set_state("phase_transition", 90);
    return true;
}

function bell_finish_transition() {
    transition_locked = false;
    bell_set_state("telegraph", telegraph_frames);
}

function bell_apply_damage(_amount) {
    if (!can_take_damage || state == "defeated") return false;
    if (phase == 4 && state != "final_exposure") return false;
    var _dmg = max(0, _amount);
    if (_dmg <= 0) return false;
    hp = max(0, hp - _dmg);
    if (phase == 4 && seals_broken >= 3 && hp <= 0) bell_set_state("defeated", 0);
    return true;
}

function bell_use_sonar() {
    if (state == "defeated") return false;
    sonar_reveal = true;
    weak_point_exposed = true;
    return true;
}

function bell_interrupt_with_chain() {
    if (phase < 2 || state != "active_attack") return false;
    bells_broken += 1;
    weak_point_exposed = true;
    bell_set_state("recovery", recovery_frames + 20);
    return true;
}

function bell_break_seal() {
    if (phase != 4 || seals_broken >= 3) return false;
    seals_broken += 1;
    if (seals_broken >= 3) bell_set_state("final_exposure", final_exposure_frames);
    else bell_set_state("seal_recycle", seal_recycle_frames);
    return true;
}

// STEP EVENT
if (state == "defeated") {
    if (!encounter_complete_fired) {
        encounter_complete_fired = true;
        // Emit reward / completion once in production integration.
    }
    exit;
}

if (phase == 1 && hp <= phase2_hp) bell_advance_phase(2);
if (phase == 2 && hp <= phase3_hp && bells_broken >= 1) bell_advance_phase(3);
if (phase == 3 && hp <= phase4_hp) bell_advance_phase(4);

if (state_timer > 0) state_timer--;

switch (state) {
    case "intro":
        if (state_timer <= 0) bell_set_state("telegraph", telegraph_frames);
        break;
    case "phase_transition":
        if (state_timer <= 0) bell_finish_transition();
        break;
    case "telegraph":
        if (state_timer <= 0) bell_set_state("active_attack", attack_frames);
        break;
    case "active_attack":
        if (state_timer <= 0) {
            if (weak_point_exposed && phase < 4) bell_set_state("recovery", recovery_frames);
            else bell_set_state("telegraph", telegraph_frames);
        }
        break;
    case "recovery":
        if (state_timer <= 0) {
            weak_point_exposed = false;
            sonar_reveal = false;
            bell_set_state("telegraph", telegraph_frames);
        }
        break;
    case "seal_recycle":
        if (state_timer <= 0) bell_set_state("telegraph", telegraph_frames);
        break;
    case "final_exposure":
        if (state_timer <= 0 && hp > 0) bell_set_state("telegraph", telegraph_frames);
        break;
}
