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

# Second official test variation for each task family. Frozen before Oracle v3 was written.
SCIENCEWORLD_V4_HELDOUT_6 = (
    ("boil", 22),
    ("melt", 22),
    ("freeze", 22),
    ("use-thermometer", 406),
    ("find-living-thing", 226),
    ("find-non-living-thing", 226),
)

# Third and fourth official test variations for each family. Frozen before API evaluation.
SCIENCEWORLD_V6_ROUTER_FORMAL_12 = (
    ("boil", 23),
    ("boil", 24),
    ("melt", 23),
    ("melt", 24),
    ("freeze", 23),
    ("freeze", 24),
    ("use-thermometer", 407),
    ("use-thermometer", 408),
    ("find-living-thing", 227),
    ("find-living-thing", 228),
    ("find-non-living-thing", 227),
    ("find-non-living-thing", 228),
)

SUITES = {
    "scienceworld-pilot-6": SCIENCEWORLD_PILOT_6,
    "scienceworld-v3-heldout-6": SCIENCEWORLD_V3_HELDOUT_6,
    "scienceworld-v4-heldout-6": SCIENCEWORLD_V4_HELDOUT_6,
    "scienceworld-v6-router-formal-12": SCIENCEWORLD_V6_ROUTER_FORMAL_12,
}

SUITE_VARIATION_SPLITS = {
    "scienceworld-pilot-6": "train",
    "scienceworld-v3-heldout-6": "test",
    "scienceworld-v4-heldout-6": "test",
    "scienceworld-v6-router-formal-12": "test",
}


def validate_suites() -> list:
    errors = []
    for name, cases in SUITES.items():
        if len(cases) != len(set(cases)):
            errors.append(f"{name}: task/variation pairs must be unique")
        if {task for task, _ in cases} != set(GOLD_SKILLS):
            errors.append(f"{name}: task families do not match the frozen Skill labels")
        counts = [sum(task == expected for task, _ in cases) for expected in GOLD_SKILLS]
        if len(set(counts)) != 1:
            errors.append(f"{name}: every task family must have the same number of cases")
    if set(SCIENCEWORLD_PILOT_6) & set(SCIENCEWORLD_V3_HELDOUT_6):
        errors.append("pilot and held-out cases must not overlap")
    if set(SCIENCEWORLD_V3_HELDOUT_6) & set(SCIENCEWORLD_V4_HELDOUT_6):
        errors.append("successive held-out suites must not overlap")
    earlier = set(SCIENCEWORLD_PILOT_6) | set(SCIENCEWORLD_V3_HELDOUT_6) | set(SCIENCEWORLD_V4_HELDOUT_6)
    if earlier & set(SCIENCEWORLD_V6_ROUTER_FORMAL_12):
        errors.append("the formal Router suite must not reuse earlier cases")
    return errors


assert not validate_suites(), validate_suites()
