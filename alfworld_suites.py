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

ALFWORLD_V6_DEV_20 = (
    2, 39, 46, 56, 74, 98, 100, 101, 110, 115,  # heat then place, valid_seen
    1, 16, 35, 41, 43, 66, 75, 82, 83, 91,       # place two objects, valid_seen
)

ALFWORLD_V7_TARGETED_TEST_10 = (
    79, 80, 101, 102, 103, 113, 114, 115,  # heat then place, valid_unseen
    120, 121,                                # place two objects, valid_unseen
)

ALFWORLD_V8_CONFIRM_20 = (
    120, 123, 125, 135, 136, 139,                 # heat then place, valid_seen
    10, 13, 47, 58, 59, 70, 78, 80, 87, 89, 92, 104, 121, 128,  # place two objects, valid_seen
)

SUITES = {
    "alfworld-v2-30": ALFWORLD_V2_30,
    "alfworld-v3-heldout-30": ALFWORLD_V3_HELDOUT_30,
    "alfworld-v5-test-30": ALFWORLD_V5_TEST_30,
    "alfworld-v6-dev-20": ALFWORLD_V6_DEV_20,
    "alfworld-v7-targeted-test-10": ALFWORLD_V7_TARGETED_TEST_10,
    "alfworld-v8-confirm-20": ALFWORLD_V8_CONFIRM_20,
}
SUITE_SPLITS = {
    "alfworld-v2-30": "valid_unseen",
    "alfworld-v3-heldout-30": "valid_unseen",
    "alfworld-v5-test-30": "valid_unseen",
    "alfworld-v6-dev-20": "valid_seen",
    "alfworld-v7-targeted-test-10": "valid_unseen",
    "alfworld-v8-confirm-20": "valid_seen",
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
    "alfworld-v6-dev-20": {
        **{index: "heat_then_place" for index in ALFWORLD_V6_DEV_20[0:10]},
        **{index: "two_object_place" for index in ALFWORLD_V6_DEV_20[10:20]},
    },
    "alfworld-v7-targeted-test-10": {
        **{index: "heat_then_place" for index in ALFWORLD_V7_TARGETED_TEST_10[0:8]},
        **{index: "two_object_place" for index in ALFWORLD_V7_TARGETED_TEST_10[8:10]},
    },
    "alfworld-v8-confirm-20": {
        **{index: "heat_then_place" for index in ALFWORLD_V8_CONFIRM_20[0:6]},
        **{index: "two_object_place" for index in ALFWORLD_V8_CONFIRM_20[6:20]},
    },
}

SUITE_EXPECTED_FAMILIES = {
    "alfworld-v2-30": {"heat_then_place": 5, "clean_then_place": 5, "cool_then_place": 5, "two_object_place": 5, "light_inspection": 5, "simple_pick_place": 5},
    "alfworld-v3-heldout-30": {"heat_then_place": 5, "clean_then_place": 5, "cool_then_place": 5, "two_object_place": 5, "light_inspection": 5, "simple_pick_place": 5},
    "alfworld-v5-test-30": {"heat_then_place": 5, "clean_then_place": 5, "cool_then_place": 5, "two_object_place": 5, "light_inspection": 5, "simple_pick_place": 5},
    "alfworld-v6-dev-20": {"heat_then_place": 10, "two_object_place": 10},
    "alfworld-v7-targeted-test-10": {"heat_then_place": 8, "two_object_place": 2},
    "alfworld-v8-confirm-20": {"heat_then_place": 6, "two_object_place": 14},
}


def validate_suites():
    errors = []
    for name, indexes in SUITES.items():
        expected = SUITE_EXPECTED_FAMILIES[name]
        expected_size = sum(expected.values())
        if len(indexes) != expected_size or len(set(indexes)) != expected_size:
            errors.append(f"{name}: expected {expected_size} unique task indexes")
        families = SUITE_FAMILIES.get(name, {})
        counts = {family: list(families.values()).count(family) for family in set(families.values())}
        if len(families) != expected_size or counts != expected:
            errors.append(f"{name}: unexpected task-family distribution")
    suite_items = list(SUITES.items())
    for offset, (left_name, left) in enumerate(suite_items):
        for right_name, right in suite_items[offset + 1:]:
            if SUITE_SPLITS[left_name] == SUITE_SPLITS[right_name] and set(left) & set(right):
                errors.append(f"{left_name} and {right_name} must be disjoint")
    return errors


assert not validate_suites(), validate_suites()
