"""Small hand-authored Skill library for the first ScienceWorld pilot."""

import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class ScienceWorldSkill:
    name: str
    description: str
    activation_condition: str
    procedure: Tuple[str, ...]
    termination_condition: str


def skill(name: str, description: str, activation: str, *procedure: str, termination: str) -> ScienceWorldSkill:
    return ScienceWorldSkill(name, description, activation, procedure, termination)


SKILL_LIST = (
    skill(
        "boil-substance",
        "Cause the named substance to reach its gaseous state by controlled heating.",
        "Use when the task asks to boil a substance.",
        "Find a suitable container, the target substance, a thermometer, and a heat source.",
        "Focus on the target substance before changing its state.",
        "Place the contained substance on the heat source and activate it.",
        "Wait, examine the substance, and measure it until the environment recognizes boiling or combustion.",
        termination="The environment score reaches 100, or heating cannot proceed after its unmet precondition is checked.",
    ),
    skill(
        "melt-substance",
        "Cause the named solid substance to become liquid.",
        "Use when the task asks to melt a substance.",
        "Find or create the named substance in solid form and focus on it.",
        "Move its container to a heat source and activate the source.",
        "Wait, examine, and use a thermometer when available; keep the same target in view.",
        termination="The environment score reaches 100, or the selected substance is not the requested solid.",
    ),
    skill(
        "freeze-substance",
        "Cause the named liquid substance to become solid.",
        "Use when the task asks to freeze a substance.",
        "Put the requested liquid in a movable container and focus on the substance.",
        "Open the freezer if needed and move the container into it.",
        "Wait, examine, and measure until the substance changes to its solid state.",
        termination="The environment score reaches 100, or cooling cannot proceed after its unmet precondition is checked.",
    ),
    skill(
        "measure-and-classify-temperature",
        "Measure an unknown substance and place it according to the threshold in the task.",
        "Use when the task asks for a thermometer measurement followed by classification.",
        "Find the thermometer, pick it up, and focus on it.",
        "Find the exact unknown substance, pick it up, and focus on it.",
        "Use the thermometer in inventory on the substance in inventory.",
        "Compare the measured value with the task threshold and move the substance to the specified colored box.",
        termination="The environment score reaches 100, or the measurement needed for classification is unavailable.",
    ),
    skill(
        "find-living-object",
        "Select a living organism and deliver it to the requested container.",
        "Use when the task asks for any living thing.",
        "Search likely indoor or outdoor locations for a plant or animal.",
        "Focus on one living target; if it changes form, track the resulting object named by the observation.",
        "Pick up or directly move that target to the task's destination.",
        termination="The environment score reaches 100, or the candidate is shown not to be living.",
    ),
    skill(
        "find-nonliving-object",
        "Select a non-living object and deliver it to the requested container.",
        "Use when the task asks for any non-living thing.",
        "Choose an ordinary manufactured object rather than a plant, animal, egg, seed, or fruit.",
        "Focus on that exact object and keep its full referent from the observation.",
        "Pick up or directly move the same object to the task's destination.",
        termination="The environment score reaches 100, or the candidate is shown to be living.",
    ),
)

SKILLS: Dict[str, ScienceWorldSkill] = {item.name: item for item in SKILL_LIST}

V2_SKILL_OVERRIDES = {
    "melt-substance": skill(
        "melt-substance",
        "Turn the named solid into liquid while preserving the identity of the focused sample.",
        "Use when the task asks to melt a substance.",
        "For water, take an empty movable container, fill it at a sink, and focus on the water inside that container; do not focus on water in a toilet or fountain.",
        "Move that same container into a freezer and use wait1 until its contents become ice.",
        "Retrieve the same container, move it to a stove, and activate the stove.",
        "Use wait1, examine the contents, and measure when useful until the focused ice becomes liquid.",
        termination="The environment score reaches 100; never replace the focused sample with water from another source.",
    ),
    "freeze-substance": skill(
        "freeze-substance",
        "Turn the named liquid into a solid while preserving the identity of the focused sample.",
        "Use when the task asks to freeze a substance.",
        "Take one empty movable container, place it in a sink, activate then deactivate the sink, and pick up the filled container.",
        "Focus on the substance inside that container only after it has been filled; do not focus on a different source of the same substance.",
        "Move that same container into a freezer, close the freezer, and use wait1 rather than wait.",
        "Examine the contents after short waits without switching containers.",
        termination="The environment score reaches 100; a different frozen sample does not satisfy the focused target.",
    ),
    "find-living-object": skill(
        "find-living-object",
        "Select a living organism itself and deliver it to the requested container.",
        "Use when the task asks for any living thing.",
        "Search the greenhouse or outside for an explicitly named plant or animal.",
        "Focus on the organism referent, such as pea plant in flower pot 5; never focus on its flower pot, hive, cage, or other container.",
        "Pick up the same organism and move it to the task destination.",
        termination="The environment score reaches 100; stop before focusing if the candidate referent names only a container.",
    ),
}

V3_SKILL_OVERRIDES = {
    "boil-substance": skill(
        "boil-substance",
        "Drive the named sample past melting until it boils or acceptably combusts.",
        "Use when the task asks to boil a substance.",
        "Find the exact named sample and focus on it before changing its state; keep that same sample or its container throughout.",
        "Put it in a heat-resistant movable container such as a metal pot. Use the strongest working heat source; if a kitchen appliance is broken or too weak, use the blast furnace in the foundry.",
        "Stay with the active heat source and alternate short waits with examining or measuring the current substance referent.",
        "A change from solid to liquid is only melting. Continue heating the liquid sample until the environment score reaches 100; do not wander away or declare completion at an intermediate score.",
        termination="The environment score reaches 100 or done is true; a liquid state or partial score alone is not termination.",
    ),
    "melt-substance": skill(
        "melt-substance",
        "Turn the exact named solid sample into liquid without unnecessary preparation.",
        "Use when the task asks to melt a substance.",
        "Find and focus on the named sample. If it is already liquid, freeze that same contained sample first; otherwise skip any water-specific preparation.",
        "Move the solid or its heat-resistant container to a working heat source. If the stove or oven is broken or too weak, use the foundry blast furnace.",
        "Activate the heat source, stay nearby, and use short waits with examine or thermometer checks while preserving the sample identity after its referent changes.",
        termination="The environment score reaches 100 or done is true after the focused sample becomes liquid.",
    ),
    "freeze-substance": skill(
        "freeze-substance",
        "Freeze the named sample after ensuring that the focused sample is liquid.",
        "Use when the task asks to freeze a substance.",
        "Find the exact named sample and focus on it. Inspect its current state before choosing the cooling procedure.",
        "If the sample starts solid, first put that same sample in a heat-resistant container and melt it with a working heat source such as the foundry blast furnace; never try to freeze an already-solid sample.",
        "After the referent becomes liquid, retrieve the same container, open a freezer, move the container inside, and close the freezer.",
        "Use short waits, then examine or measure the same contained sample until it becomes solid; do not switch to another sample with the same name.",
        termination="The environment score reaches 100 or done is true; a focused but unchanged sample and partial score are not termination.",
    ),
}

GOLD_SKILLS = {
    "boil": "boil-substance",
    "melt": "melt-substance",
    "freeze": "freeze-substance",
    "use-thermometer": "measure-and-classify-temperature",
    "find-living-thing": "find-living-object",
    "find-non-living-thing": "find-nonliving-object",
}


def versioned_skills(version: str = "v1") -> Tuple[ScienceWorldSkill, ...]:
    if version == "v1":
        return SKILL_LIST
    if version == "v2":
        return tuple(V2_SKILL_OVERRIDES.get(item.name, item) for item in SKILL_LIST)
    if version == "v3":
        return tuple(V3_SKILL_OVERRIDES.get(item.name, item) for item in versioned_skills("v2"))
    raise ValueError(f"unknown skill library version: {version}")


def render(item: ScienceWorldSkill) -> str:
    procedure = "\n".join(f"{index}. {step}" for index, step in enumerate(item.procedure, 1))
    return f"Name\n{item.name}\n\nDescription\n{item.description}\n\nActivation Condition\n{item.activation_condition}\n\nProcedure\n{procedure}\n\nTermination Condition\n{item.termination_condition}\n"


def loaded_skill_text(names: Iterable[str], version: str = "v1") -> str:
    selected = {item.name: item for item in versioned_skills(version)}
    return "\n---\n".join(render(selected[name]) for name in names)


def library_hash(version: str = "v1") -> str:
    return hashlib.sha256("\n".join(render(item) for item in versioned_skills(version)).encode("utf-8")).hexdigest()


def validate_library() -> list:
    errors = []
    if len(SKILL_LIST) != 6 or len(SKILLS) != 6:
        errors.append("the pilot must contain six uniquely named Skills")
    if set(GOLD_SKILLS.values()) != set(SKILLS):
        errors.append("every pilot Skill must have exactly one task-family label")
    if any(name not in SKILLS or item.name != name for name, item in V2_SKILL_OVERRIDES.items()):
        errors.append("v2 overrides must replace existing Skills without renaming them")
    if any(name not in SKILLS or item.name != name for name, item in V3_SKILL_OVERRIDES.items()):
        errors.append("v3 overrides must replace existing Skills without renaming them")
    for item in SKILL_LIST:
        if not all((item.name, item.description, item.activation_condition, item.procedure, item.termination_condition)):
            errors.append(f"{item.name}: all five fields are required")
    return errors


assert not validate_library(), validate_library()
