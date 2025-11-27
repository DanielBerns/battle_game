import math
import random


# CONFIGURATION
INFANTRY = 5
TANKS = 2
TICKS = 100
DEFENSE_CONSTANT = 25  # Lower = Armor is stronger
RNG_ENABLED = False     # Set False for pure deterministic testing

class Unit:
    def __init__(self, name, hp, atk, def_stat):
        self.name = name
        self.max_hp = hp
        self.current_hp = hp
        self.atk = atk
        self.def_stat = def_stat

    @property
    def is_alive(self):
        return self.current_hp > 0

def simulate_round(attackers, defenders, terrain_def_bonus=0):
    # 1. Calculate Total Attack Output (Raw Damage Pool)
    total_raw_damage = 0
    for u in attackers:
        if u.is_alive:
            # Wounded units deal reduced damage
            efficiency = u.current_hp / u.max_hp
            total_raw_damage += u.atk * efficiency

    if RNG_ENABLED:
        total_raw_damage *= random.uniform(0.95, 1.05)

    print(f"  > Incoming Raw Damage Pool: {total_raw_damage:.1f}")

    # 2. Distribute Damage to Defenders (Lowest HP first focus fire)
    # Sort by current HP ascending
    defenders.sort(key=lambda x: x.current_hp)

    remaining_raw_damage = total_raw_damage

    for target in defenders:
        if not target.is_alive: continue
        if remaining_raw_damage <= 0: break

        # Calculate Mitigation for this specific unit
        # Formula: Def / (Def + Constant)
        effective_def = target.def_stat + terrain_def_bonus
        mitigation_pct = effective_def / (effective_def + DEFENSE_CONSTANT)

        # Calculate Effective HP (How much raw damage to kill it?)
        # EHP = HP / (1 - Mitigation)
        damage_taker_mult = 1 - mitigation_pct
        effective_hp = target.current_hp / damage_taker_mult

        if remaining_raw_damage >= effective_hp:
            # FATAL BLOW
            print(f"    - {target.name} (HP: {target.current_hp:.1f}) KILLED! (Absorbed {effective_hp:.1f} raw)")
            remaining_raw_damage -= effective_hp
            target.current_hp = 0
        else:
            # SURVIVED
            actual_damage = remaining_raw_damage * damage_taker_mult
            target.current_hp -= actual_damage
            print(f"    - {target.name} takes {actual_damage:.1f} dmg (Remaining HP: {target.current_hp:.1f})")
            remaining_raw_damage = 0

# --- SCENARIO SETUP ---
# Stats from your Spec
# Light Inf: HP 60, ATK 10, DEF 6
# Armored:   HP 120, ATK 20, DEF 16

team_a = [Unit("Infantry_A1", 60, 10, 6) for _ in range(INFANTRY)] # Infantry (Cost: 200M)
team_b = [Unit("Tank_B1", 120, 20, 16) for _ in range(TANKS)] # Tank (Cost: 120M + 40F)

print(f"--- BATTLE START: {len(team_a)} Infantry vs {len(team_b)} Tank ---")

for r in range(1, TICKS): # Max 3 rounds per tick
    if not any(u.is_alive for u in team_a) or not any(u.is_alive for u in team_b):
        break
    print(f"\n[Round {r}]")

    # Simultaneous Combat
    # We calculate state changes but apply them after logic to avoid index issues
    # (In real engine, calculate both sides' output first, then apply)

    print("Team A Attacks -> Team B:")
    simulate_round(team_a, team_b)

    print("Team B Attacks -> Team A:")
    simulate_round(team_b, team_a)

print("\n--- RESULT ---")
alive_a = len([u for u in team_a if u.is_alive])
alive_b = len([u for u in team_b if u.is_alive])
print(f"Infantry Alive: {alive_a}")
print(f"Tanks Alive:    {alive_b}")
if alive_b > 0:
    print(f"Tank HP: {team_b[0].current_hp:.1f}")
