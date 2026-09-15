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

# Fifth and sixth official test variations for each family. Frozen before gold or API evaluation.
SCIENCEWORLD_V10_CONFIRM_12 = (
    ("boil", 25),
    ("boil", 26),
    ("melt", 25),
    ("melt", 26),
    ("freeze", 25),
    ("freeze", 26),
    ("use-thermometer", 409),
    ("use-thermometer", 410),
    ("find-living-thing", 229),
    ("find-living-thing", 230),
    ("find-non-living-thing", 229),
    ("find-non-living-thing", 230),
)

# Seventh through eleventh official test variations for each family. Frozen
# before local gold validation, retrieval audit, or API evaluation.
SCIENCEWORLD_V11_LARGE_CONFIRM_30 = (
    ("boil", 27),
    ("boil", 28),
    ("boil", 29),
    ("boil", 30),
    ("boil", 31),
    ("melt", 27),
    ("melt", 28),
    ("melt", 29),
    ("melt", 30),
    ("melt", 31),
    ("freeze", 27),
    ("freeze", 28),
    ("freeze", 29),
    ("freeze", 30),
    ("freeze", 31),
    ("use-thermometer", 411),
    ("use-thermometer", 412),
    ("use-thermometer", 413),
    ("use-thermometer", 414),
    ("use-thermometer", 415),
    ("find-living-thing", 231),
    ("find-living-thing", 232),
    ("find-living-thing", 233),
    ("find-living-thing", 234),
    ("find-living-thing", 235),
    ("find-non-living-thing", 231),
    ("find-non-living-thing", 232),
    ("find-non-living-thing", 233),
    ("find-non-living-thing", 234),
    ("find-non-living-thing", 235),
)

SUITES = {
    "scienceworld-pilot-6": SCIENCEWORLD_PILOT_6,
    "scienceworld-v3-heldout-6": SCIENCEWORLD_V3_HELDOUT_6,
    "scienceworld-v4-heldout-6": SCIENCEWORLD_V4_HELDOUT_6,
    "scienceworld-v6-router-formal-12": SCIENCEWORLD_V6_ROUTER_FORMAL_12,
    "scienceworld-v10-confirm-12": SCIENCEWORLD_V10_CONFIRM_12,
    "scienceworld-v11-large-confirm-30": SCIENCEWORLD_V11_LARGE_CONFIRM_30,
}

SUITE_VARIATION_SPLITS = {
    "scienceworld-pilot-6": "train",
    "scienceworld-v3-heldout-6": "test",
    "scienceworld-v4-heldout-6": "test",
    "scienceworld-v6-router-formal-12": "test",
    "scienceworld-v10-confirm-12": "test",
    "scienceworld-v11-large-confirm-30": "test",
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
    suite_items = list(SUITES.items())
    for index, (left_name, left_cases) in enumerate(suite_items):
        for right_name, right_cases in suite_items[index + 1:]:
            if set(left_cases) & set(right_cases):
                errors.append(f"{left_name} and {right_name} must not overlap")
    return errors


assert not validate_suites(), validate_suites()
