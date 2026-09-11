"""Frozen ScienceWorld task/variation pairs."""

from scienceworld_skills import GOLD_SKILLS


SCIENCEWORLD_PILOT_6 = tuple((task_name, 0) for task_name in GOLD_SKILLS)

# First official test variation for each task family. Frozen before API evaluation.
SCIENCEWORLD_V3_HELDOUT_6 = (
    ("boil", 21),
    ("melt", 21),
    ("freeze", 21),
    ("use-thermometer", 405),
    ("find-living-thing", 225),
    ("find-non-living-thing", 225),
)

SUITES = {
    "scienceworld-pilot-6": SCIENCEWORLD_PILOT_6,
    "scienceworld-v3-heldout-6": SCIENCEWORLD_V3_HELDOUT_6,
}

SUITE_VARIATION_SPLITS = {
    "scienceworld-pilot-6": "train",
    "scienceworld-v3-heldout-6": "test",
}


def validate_suites() -> list:
    errors = []
    for name, cases in SUITES.items():
        if len(cases) != 6 or len(set(cases)) != 6:
            errors.append(f"{name}: expected six unique cases")
        if {task for task, _ in cases} != set(GOLD_SKILLS):
            errors.append(f"{name}: task families do not match the frozen Skill labels")
    if set(SCIENCEWORLD_PILOT_6) & set(SCIENCEWORLD_V3_HELDOUT_6):
        errors.append("pilot and held-out cases must not overlap")
    return errors


assert not validate_suites(), validate_suites()
