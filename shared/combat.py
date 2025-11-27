def calculate_mitigation(total_def: int) -> float:
    """
    Implements M = DEF / (DEF + 25)
    """
    return total_def / (total_def + 25.0)

def calculate_effective_hp(current_hp: float, mitigation: float) -> float:
    """
    Implements E_hp = CurrentHP / (1 - M)
    """
    if mitigation >= 1.0: return 999999 # Invulnerable guard
    return current_hp / (1.0 - mitigation)
