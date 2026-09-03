"""Manual oracle labels, frozen by ALFWorld task family rather than model output."""

from pathlib import Path
from typing import Tuple

from alfworld_skills import SKILLS


_FAMILY_LABELS = {
    "pick_heat_then_place_in_recep": ("task-goal-parse", "execute-heat-place", "action-syntax-recovery"),
    "pick_cool_then_place_in_recep": ("task-goal-parse", "execute-cool-place", "action-syntax-recovery"),
    "pick_clean_then_place_in_recep": ("task-goal-parse", "execute-clean-place", "action-syntax-recovery"),
    "pick_two_obj_and_place": ("task-goal-parse", "two-object-placement", "action-syntax-recovery"),
    "look_at_obj": ("task-goal-parse", "light-inspection-sequence", "observation-memory"),
    "pick_and_place_simple": ("task-goal-parse", "simple-pick-place", "action-syntax-recovery"),
}


def gold_skills_for_game(game_file: str) -> Tuple[str, ...]:
    family = Path(game_file).parents[1].name
    for prefix, labels in _FAMILY_LABELS.items():
        if family.startswith(prefix):
            return labels
    raise ValueError(f"no manual oracle labels for ALFWorld game family: {family}")


assert all(name in SKILLS for labels in _FAMILY_LABELS.values() for name in labels)
