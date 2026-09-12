extends Node

const RUNS := 250
var rng := RandomNumberGenerator.new()

func simulate(seed_value: int) -> Dictionary:
    rng.seed = seed_value
    var energy := 115
    var armor := 0
    var score := 0
    var sector := 0
    var abilities := {"pulse":0,"dash":0,"charge":0,"shield":0}
    var death_reason := ""
    for s in 5:
        sector = s
        var required_ore := 0 if s == 4 else 5 + s
        var collected := 0
        var turns := 0
        while (collected < required_ore or (s == 4 and turns < 18)) and turns < 90:
            turns += 1
            energy -= rng.randi_range(0,2)
            if rng.randf() < 0.16:
                collected += 1
                energy = min(115,energy+12)
                score += 100
            if rng.randf() < 0.06:
                var pick := rng.randi_range(0,3)
                var keys := ["pulse","dash","charge","shield"]
                abilities[keys[pick]] += 1
                energy -= [10,8,0,14][pick]
                if pick == 3:
                    armor += 1
            if rng.randf() < 0.012 + s*0.004:
                if armor > 0: armor -= 1
                else:
                    death_reason = "enemy_or_hazard"
                    return _result(false,sector,score,energy,turns,abilities,death_reason)
            if energy <= 0:
                death_reason = "energy_depletion"
                return _result(false,sector,score,energy,turns,abilities,death_reason)
        score += 500
    return _result(true,sector,score,energy,0,abilities,"")

func _result(success: bool, sector: int, score: int, energy: int, turns: int, abilities: Dictionary, reason: String) -> Dictionary:
    return {"success":success,"sector":sector,"score":score,"energy":energy,
        "turns":turns,"abilities":abilities,"death_reason":reason}

func batch() -> Dictionary:
    var wins := 0
    var deaths := {}
    var score_sum := 0
    var ability_totals := {"pulse":0,"dash":0,"charge":0,"shield":0}
    var worst_seeds: Array = []
    for i in RUNS:
        var seed := 100000+i
        var r := simulate(seed)
        if r.success: wins += 1
        else:
            deaths[r.death_reason] = int(deaths.get(r.death_reason,0))+1
            if worst_seeds.size() < 20:
                worst_seeds.append({"seed":seed,"sector":r.sector,"reason":r.death_reason})
        score_sum += r.score
        for k in ability_totals:
            ability_totals[k] += r.abilities[k]
    return {"runs":RUNS,"wins":wins,"win_rate":float(wins)/RUNS,
        "average_score":float(score_sum)/RUNS,"deaths":deaths,
        "ability_usage":ability_totals,"sample_failure_seeds":worst_seeds}
