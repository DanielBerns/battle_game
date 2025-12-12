Based on the project documentation, particularly `prompt_1.md` and `prompt_2.md`, a highly relevant feature to implement next is the **Tech / Upgrade System**.

Currently, the **Intel (I)** resource is defined in the economy but is underutilized (only used for building Special Forces). The design documents explicitly mention intended upgrades like "Tier 1: +10% ATK/DEF" or "Tier 2: +1 MP for Scouts", but these are not yet implemented in the `engine.py` or `schemas.py`.

### Suggested Feature: Tech Research System

**Goal:** Give players a strategic sink for their Intel resources by allowing them to research permanent upgrades.

**Changes Required:**
1.  **Schemas:** Add a `RESEARCH` order type and a structure to track unlocked upgrades in `PlayerState`.
2.  **Engine:** Implement the logic to consume Intel, track research progress (ticks remaining), and apply the passive bonuses (modifiers) during combat calculation and movement.
3.  **Client:** Update the bot to purchase upgrades when it has excess Intel.

### Prompt for New Chat

You can copy and paste the following block into a new chat to start development on this feature:

***

**Prompt:**

I want to implement the **Tech/Upgrade System** described in the game design docs, as the "Intel" resource is currently underutilized.

Please modify the server and shared code to implement the following:

1.  **Update `shared/schemas.py`**:
    * Add a new `OrderType` called `RESEARCH`.
    * Add a `ResearchOrder` model (specifying which upgrade to research).
    * Update `PlayerState` to include a list of `unlocked_upgrades` (e.g., `["INFANTRY_TIER_1", "SPEED_TIER_1"]`).

2.  **Update `server/engine.py`**:
    * Handle the `RESEARCH` order: Deduct **200 Intel** (I) and mark the upgrade as active. (For MVP, make it instant, ignoring the "10 ticks" duration for now).
    * Modify `_get_base_atk` and `_get_base_def` to check `state.you.unlocked_upgrades`. If the player has the relevant upgrade (e.g., `INFANTRY_TIER_1`), apply a **+10% multiplier** to the base stats.

3.  **Update `client/client.py`**:
    * Add simple logic to the bot: If `resources.I >= 200` and we haven't researched `INFANTRY_TIER_1` yet, submit a `RESEARCH` order.

