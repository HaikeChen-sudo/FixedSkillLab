"""Frozen ScienceWorld task/variation pairs."""

from scienceworld_skills import GOLD_SKILLS, V4_GOLD_SKILLS


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

# First three unused official test variations for each family. This balanced
# replacement was frozen after v11 failed preflight and before any API run.
SCIENCEWORLD_V11B_CONFIRM_18 = (
    ("boil", 27),
    ("boil", 28),
    ("boil", 29),
    ("melt", 27),
    ("melt", 28),
    ("melt", 29),
    ("freeze", 27),
    ("freeze", 28),
    ("freeze", 29),
    ("use-thermometer", 411),
    ("use-thermometer", 412),
    ("use-thermometer", 413),
    ("find-living-thing", 231),
    ("find-living-thing", 232),
    ("find-living-thing", 233),
    ("find-non-living-thing", 231),
    ("find-non-living-thing", 232),
    ("find-non-living-thing", 233),
)

# Mechanism pilot deliberately reuses one v11b case per family. It tests prompt
# content controls and is not an independent held-out confirmation.
SCIENCEWORLD_V12_MECHANISM_PILOT_6 = (
    ("boil", 27),
    ("melt", 27),
    ("freeze", 27),
    ("use-thermometer", 411),
    ("find-living-thing", 231),
    ("find-non-living-thing", 231),
)

# v13 keeps the same six cases so only the Skill selection/rendering protocol
# changes relative to the v12 mechanism pilot.
SCIENCEWORLD_V13_ORACLE_MECHANISM_PILOT_6 = SCIENCEWORLD_V12_MECHANISM_PILOT_6

# Post-pilot targeted confirmation. These cases were selected because the v13
# pilot localized the Procedure signal to state-change tasks.
SCIENCEWORLD_V13B_ORACLE_MECHANISM_6 = (
    ("boil", 27),
    ("boil", 28),
    ("boil", 29),
    ("freeze", 27),
    ("freeze", 28),
    ("freeze", 29),
)

# T1 is a mechanism pilot, not an independent held-out confirmation. It reuses
# the twelve v10 cases whose local Gold paths were already validated.
SCIENCEWORLD_T1_T_SHAPED_PILOT_12 = SCIENCEWORLD_V10_CONFIRM_12

# T2 deliberately reuses the two T1 cases that separated the horizontal and
# vertical layers. It is a development diagnostic, not held-out evidence.
SCIENCEWORLD_T2_CONTROLLER_DEV_2 = (
    ("melt", 25),
    ("freeze", 26),
)

# T3 is the final development iteration on the same diagnosed cases. Reusing
# them keeps controller tuning separate from any later held-out confirmation.
SCIENCEWORLD_T3_STATE_AWARE_DEV_2 = SCIENCEWORLD_T2_CONTROLLER_DEV_2

# Development cases only. The v14 test suite stays outside the runner until final freeze.
SCIENCEWORLD_V14_DEV_4 = (
    ("power-component", 10),
    ("grow-plant", 62),
    ("chemistry-mix", 16),
    ("inclined-plane-determine-angle", 84),
)

# New dev variations, selected by the next official index before seeing their task text.
SCIENCEWORLD_V14C_DEV_CHECK_4 = (
    ("power-component", 11),
    ("grow-plant", 63),
    ("chemistry-mix", 17),
    ("inclined-plane-determine-angle", 85),
)

SUITES = {
    "scienceworld-pilot-6": SCIENCEWORLD_PILOT_6,
    "scienceworld-v3-heldout-6": SCIENCEWORLD_V3_HELDOUT_6,
    "scienceworld-v4-heldout-6": SCIENCEWORLD_V4_HELDOUT_6,
    "scienceworld-v6-router-formal-12": SCIENCEWORLD_V6_ROUTER_FORMAL_12,
    "scienceworld-v10-confirm-12": SCIENCEWORLD_V10_CONFIRM_12,
    "scienceworld-v11b-confirm-18": SCIENCEWORLD_V11B_CONFIRM_18,
    "scienceworld-v12-mechanism-pilot-6": SCIENCEWORLD_V12_MECHANISM_PILOT_6,
    "scienceworld-v13-oracle-mechanism-pilot-6": SCIENCEWORLD_V13_ORACLE_MECHANISM_PILOT_6,
    "scienceworld-v13b-oracle-mechanism-6": SCIENCEWORLD_V13B_ORACLE_MECHANISM_6,
    "scienceworld-t1-t-shaped-pilot-12": SCIENCEWORLD_T1_T_SHAPED_PILOT_12,
    "scienceworld-t2-controller-dev-2": SCIENCEWORLD_T2_CONTROLLER_DEV_2,
    "scienceworld-t3-state-aware-dev-2": SCIENCEWORLD_T3_STATE_AWARE_DEV_2,
    "scienceworld-v14-dev-4": SCIENCEWORLD_V14_DEV_4,
    "scienceworld-v14c-dev-check-4": SCIENCEWORLD_V14C_DEV_CHECK_4,
}

SUITE_VARIATION_SPLITS = {
    "scienceworld-pilot-6": "train",
    "scienceworld-v3-heldout-6": "test",
    "scienceworld-v4-heldout-6": "test",
    "scienceworld-v6-router-formal-12": "test",
    "scienceworld-v10-confirm-12": "test",
    "scienceworld-v11b-confirm-18": "test",
    "scienceworld-v12-mechanism-pilot-6": "test",
    "scienceworld-v13-oracle-mechanism-pilot-6": "test",
    "scienceworld-v13b-oracle-mechanism-6": "test",
    "scienceworld-t1-t-shaped-pilot-12": "test",
    "scienceworld-t2-controller-dev-2": "test",
    "scienceworld-t3-state-aware-dev-2": "test",
    "scienceworld-v14-dev-4": "dev",
    "scienceworld-v14c-dev-check-4": "dev",
}

REUSED_MECHANISM_SUITES = {
    "scienceworld-v12-mechanism-pilot-6",
    "scienceworld-v13-oracle-mechanism-pilot-6",
    "scienceworld-v13b-oracle-mechanism-6",
    "scienceworld-t1-t-shaped-pilot-12",
    "scienceworld-t2-controller-dev-2",
    "scienceworld-t3-state-aware-dev-2",
}

TARGETED_SUITE_FAMILIES = {
    "scienceworld-v13b-oracle-mechanism-6": {"boil", "freeze"},
    "scienceworld-t2-controller-dev-2": {"melt", "freeze"},
    "scienceworld-t3-state-aware-dev-2": {"melt", "freeze"},
    "scienceworld-v14-dev-4": set(V4_GOLD_SKILLS),
    "scienceworld-v14c-dev-check-4": set(V4_GOLD_SKILLS),
}

SCIENCEWORLD_TEST_VARIATIONS = {
    **{task: range(21, 30) for task in ("boil", "melt", "freeze")},
    "use-thermometer": range(405, 540),
    "find-living-thing": range(225, 300),
    "find-non-living-thing": range(225, 300),
}


def validate_suites() -> list:
    errors = []
    for name, cases in SUITES.items():
        if len(cases) != len(set(cases)):
            errors.append(f"{name}: task/variation pairs must be unique")
        expected_families = TARGETED_SUITE_FAMILIES.get(name, set(GOLD_SKILLS))
        if {task for task, _ in cases} != expected_families:
            errors.append(f"{name}: task families do not match the frozen Skill labels")
        counts = [sum(task == expected for task, _ in cases) for expected in expected_families]
        if len(set(counts)) != 1:
            errors.append(f"{name}: every task family must have the same number of cases")
        if SUITE_VARIATION_SPLITS[name] == "test":
            invalid = [
                f"{task}:v{variation:03d}"
                for task, variation in cases
                if variation not in SCIENCEWORLD_TEST_VARIATIONS[task]
            ]
            if invalid:
                errors.append(f"{name}: cases outside the official test split: {', '.join(invalid)}")
    suite_items = list(SUITES.items())
    for index, (left_name, left_cases) in enumerate(suite_items):
        for right_name, right_cases in suite_items[index + 1:]:
            if {left_name, right_name} & REUSED_MECHANISM_SUITES:
                continue
            if set(left_cases) & set(right_cases):
                errors.append(f"{left_name} and {right_name} must not overlap")
    return errors


assert not validate_suites(), validate_suites()
