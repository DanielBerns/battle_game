def resolve_movement(units, orders):
    # 1. Sort orders by Initiative: (MP * 1000) + Unit_ID_Int
    orders.sort(key=lambda x: calculate_initiative(x.unit))

    moves = {} # Target_Hex -> [Unit]

    # 2. Phase A: Conflict & Bounce
    for order in orders:
        target = order.dest
        if target in moves:
            # Conflict: Higher initiative wins, lower bounces
            winner = moves[target][0]
            bouncer = order.unit
            # ... apply bounce logic ...
        else:
            moves[target] = [order.unit]

    # 3. Phase B: Head-to-Head Collision
    # If A moves to B's old hex, and B moves to A's old hex -> Stop & Fight

    # 4. Phase C: Chain Dependency
    # Recursive check if target hex is occupied by a unit that failed to move
