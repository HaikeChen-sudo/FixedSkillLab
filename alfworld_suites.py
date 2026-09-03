"""Frozen task indexes for the text-only ALFWorld experiments."""


ALFWORLD_V2_30 = (
    0, 24, 35, 52, 78,       # heat then place
    3, 15, 33, 55, 67,       # clean then place
    6, 12, 30, 40, 87,       # cool then place
    9, 18, 49, 72, 90,       # place two objects
    21, 46, 58, 69, 110,     # inspect object under light
    43, 61, 64, 81, 98,      # simple pick and place
)

ALFWORLD_V3_HELDOUT_30 = (
    1, 2, 25, 26, 27,       # heat then place
    4, 5, 16, 17, 34,       # clean then place
    7, 8, 13, 14, 31,       # cool then place
    10, 11, 19, 20, 50,     # place two objects
    22, 23, 47, 48, 59,     # inspect object under light
    44, 45, 62, 63, 65,     # simple pick and place
)

ALFWORLD_V5_TEST_30 = (
    28, 29, 36, 53, 54,       # heat then place
    37, 38, 39, 56, 57,       # clean then place
    32, 41, 42, 88, 89,       # cool then place
    51, 73, 74, 91, 119,      # place two objects
    60, 70, 71, 111, 112,     # inspect object under light
    66, 82, 83, 84, 85,       # simple pick and place
)

SUITES = {
    "alfworld-v2-30": ALFWORLD_V2_30,
    "alfworld-v3-heldout-30": ALFWORLD_V3_HELDOUT_30,
    "alfworld-v5-test-30": ALFWORLD_V5_TEST_30,
}
SUITE_FAMILIES = {
    "alfworld-v2-30": {
        **{index: "heat_then_place" for index in ALFWORLD_V2_30[0:5]},
        **{index: "clean_then_place" for index in ALFWORLD_V2_30[5:10]},
        **{index: "cool_then_place" for index in ALFWORLD_V2_30[10:15]},
        **{index: "two_object_place" for index in ALFWORLD_V2_30[15:20]},
        **{index: "light_inspection" for index in ALFWORLD_V2_30[20:25]},
        **{index: "simple_pick_place" for index in ALFWORLD_V2_30[25:30]},
    },
    "alfworld-v3-heldout-30": {
        **{index: "heat_then_place" for index in ALFWORLD_V3_HELDOUT_30[0:5]},
        **{index: "clean_then_place" for index in ALFWORLD_V3_HELDOUT_30[5:10]},
        **{index: "cool_then_place" for index in ALFWORLD_V3_HELDOUT_30[10:15]},
        **{index: "two_object_place" for index in ALFWORLD_V3_HELDOUT_30[15:20]},
        **{index: "light_inspection" for index in ALFWORLD_V3_HELDOUT_30[20:25]},
        **{index: "simple_pick_place" for index in ALFWORLD_V3_HELDOUT_30[25:30]},
    },
    "alfworld-v5-test-30": {
        **{index: "heat_then_place" for index in ALFWORLD_V5_TEST_30[0:5]},
        **{index: "clean_then_place" for index in ALFWORLD_V5_TEST_30[5:10]},
        **{index: "cool_then_place" for index in ALFWORLD_V5_TEST_30[10:15]},
        **{index: "two_object_place" for index in ALFWORLD_V5_TEST_30[15:20]},
        **{index: "light_inspection" for index in ALFWORLD_V5_TEST_30[20:25]},
        **{index: "simple_pick_place" for index in ALFWORLD_V5_TEST_30[25:30]},
    },
}


def validate_suites():
    errors = []
    for name, indexes in SUITES.items():
        if len(indexes) != 30 or len(set(indexes)) != 30:
            errors.append(f"{name}: expected 30 unique task indexes")
        families = SUITE_FAMILIES.get(name, {})
        if len(families) != 30 or len(set(families.values())) != 6 or any(list(families.values()).count(family) != 5 for family in set(families.values())):
            errors.append(f"{name}: expected six task families with five tasks each")
    suite_items = list(SUITES.items())
    for offset, (left_name, left) in enumerate(suite_items):
        for right_name, right in suite_items[offset + 1:]:
            if set(left) & set(right):
                errors.append(f"{left_name} and {right_name} must be disjoint")
    return errors


assert not validate_suites(), validate_suites()
