"""Small hand-authored Skill library for ScienceWorld experiments."""

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

V4_SKILLS = (
    skill(
        "power-component-circuit",
        "Power the named electrical component by closing a circuit with a battery and wires.",
        "Use when the task asks to turn on a named light bulb or other powered component.",
        "Find the exact named component, battery, and two wires in the workshop; focus on the component before wiring it.",
        "Connect the battery anode through one wire to the component cathode, and the battery cathode through the other wire to the component anode. Use the terminal names shown in the room.",
        "Inspect the component after closing both sides of the circuit; use wait1 once if the score has not yet reached 100.",
        termination="The environment score reaches 100 or done is true; one connected side is not a complete circuit.",
    ),
    skill(
        "grow-plant-from-seed",
        "Grow the requested plant from its seed to the reproduction life stage.",
        "Use when the task asks to grow a named plant from seed.",
        "Find the seed jar in the room named by the task, then go to the greenhouse with the exact named seed.",
        "Choose one flower pot. Add soil if it is empty, move the named seed into that pot, and focus on the seed itself rather than the pot.",
        "Fill a jug at the sink and pour water into the same pot. Use short waits while checking the plant's growth stage.",
        "If growth stalls before reproduction, refill the jug and water that same pot again; keep the focused plant identity.",
        termination="The environment score reaches 100 or done is true after the focused plant reaches reproduction.",
    ),
    skill(
        "chemistry-recipe-mix",
        "Create the named substance by following the local recipe and mixing its ingredients.",
        "Use when the task asks to create a substance by chemistry mixing.",
        "Find and read the recipe before selecting ingredients; the required ingredients vary with the target substance.",
        "Put every listed ingredient into one suitable container, obtaining water from a sink if the recipe requires it.",
        "Mix the contents, inspect the resulting substance, and focus on that product rather than an ingredient or container.",
        termination="The environment score reaches 100 or done is true after focusing on the requested product.",
    ),
    skill(
        "measure-inclined-plane-angle",
        "Identify the shallower of two named inclined planes by timing the same sliding block.",
        "Use when the task asks which of two inclined planes has the shallowest angle.",
        "Find the two named planes, a block, and a stopwatch in the workshop; do not focus on either plane before measuring.",
        "Put the same block on the first plane, activate the stopwatch, observe the block until it reaches the bottom, then stop and examine the stopwatch. Record the tick count.",
        "Repeat the same experiment on the second plane. With the same block, the longer travel time indicates the shallower angle.",
        "Focus on the full referent of the plane with the longer recorded time; compare measurements rather than plane letters.",
        termination="The environment score reaches 100 or done is true after the measured shallower plane is focused.",
    ),
)

V4B_SKILL_OVERRIDES = {
    "chemistry-recipe-mix": skill(
        "chemistry-recipe-mix",
        "Create the named substance by following the local recipe and mixing its ingredients.",
        "Use when the task asks to create a substance by chemistry mixing.",
        "Find the recipe, pick it up, then use read recipe in inventory; examine recipe only shows its title, not the ingredients.",
        "Put every listed ingredient into one suitable container, obtaining water from a sink if the recipe requires it.",
        "Use mix <container>, inspect the result, then focus on the product, never the recipe, an ingredient, or its container.",
        termination="The environment score reaches 100 or done is true after focusing on the requested product.",
    ),
}

V4C_SKILL_OVERRIDES = {
    "power-component-circuit": skill(
        "power-component-circuit",
        "Turn on a named light bulb or electrical component by building an electrical circuit that powers it on.",
        "Use when the task asks to turn on a named light bulb or other powered component.",
        "Find the exact named component, battery, and two wires in the workshop; focus on the component before wiring it.",
        "Connect the battery anode through one wire to the component cathode, and the battery cathode through the other wire to the component anode. Use the terminal names shown in the room.",
        "Inspect the component after closing both sides of the circuit; use wait1 once if the score has not yet reached 100.",
        termination="The environment score reaches 100 or done is true; one connected side is not a complete circuit.",
    ),
    "measure-inclined-plane-angle": skill(
        "measure-inclined-plane-angle",
        "Identify the shallower of two named inclined planes by timing the same sliding block.",
        "Use when the task asks which of two inclined planes has the shallowest angle.",
        "Find the two named planes, a block, and a stopwatch in the workshop; do not focus on either plane before measuring.",
        "Put the block on the first plane and activate the stopwatch. After short waits, examine the plane until the observation explicitly says the block is at the bottom. Intermediate tick readings are not a completed measurement. Only then stop and examine the stopwatch; record that time.",
        "Repeat with the same block on the second plane. Compare only two times measured after the block reached the bottom; the longer time indicates the shallower angle.",
        "If either reading was taken before the block reached the bottom, redo that measurement. Otherwise focus on the full referent of the plane with the longer time.",
        termination="The environment score reaches 100 or done is true after the measured shallower plane is focused.",
    ),
}

V4_GOLD_SKILLS = {
    "power-component": "power-component-circuit",
    "grow-plant": "grow-plant-from-seed",
    "chemistry-mix": "chemistry-recipe-mix",
    "inclined-plane-determine-angle": "measure-inclined-plane-angle",
}

ALL_GOLD_SKILLS = {**GOLD_SKILLS, **V4_GOLD_SKILLS}

T_STRUCTURE_VERSION = "t1"
T_HORIZONTAL_SKILL_NAME = "scienceworld-execution-control"
T_HORIZONTAL_SKILL = skill(
    T_HORIZONTAL_SKILL_NAME,
    "Apply one stable execution discipline across ScienceWorld task families.",
    "Use for any interactive ScienceWorld task, independent of the task domain.",
    "Preserve the full object referent and the identity of the selected target across actions.",
    "Before an irreversible focus action, confirm that the target itself, not its container or a similar object, matches the task.",
    "After every action, read the new observation, score, done flag, and environment state before choosing the next action.",
    "If two actions make no progress, inspect inventory, location, container state, and unmet preconditions before retrying.",
    termination="Stop only when the environment score reaches 100 or done is true; otherwise diagnose the blocked precondition.",
)

# These paths are fixed experimental labels, not a learned graph. The final
# leaf reuses the v3 task-specific Procedure already tested in earlier runs.
T_VERTICAL_PATHS = {
    "boil": ("state-change", "heating", "boil"),
    "melt": ("state-change", "heating", "melt"),
    "freeze": ("state-change", "cooling", "freeze"),
    "use-thermometer": ("measurement", "temperature-classification"),
    "find-living-thing": ("object-classification", "living-object"),
    "find-non-living-thing": ("object-classification", "nonliving-object"),
}


def t_skill_names(condition: str, task_name: str) -> Tuple[str, ...]:
    if task_name not in GOLD_SKILLS:
        raise ValueError(f"no frozen Oracle label for task: {task_name}")
    if condition in {"t_horizontal", "t2_horizontal"}:
        return (T_HORIZONTAL_SKILL_NAME,)
    if condition == "t3_horizontal":
        return ()
    if condition in {"t_vertical", "t2_vertical", "t3_vertical"}:
        return (GOLD_SKILLS[task_name],)
    if condition in {"t_full", "t2_full"}:
        return (T_HORIZONTAL_SKILL_NAME, GOLD_SKILLS[task_name])
    if condition == "t3_full":
        return (GOLD_SKILLS[task_name],)
    raise ValueError(f"not a T-shaped condition: {condition}")


def versioned_skills(version: str = "v1") -> Tuple[ScienceWorldSkill, ...]:
    if version == "v1":
        return SKILL_LIST
    if version == "v2":
        return tuple(V2_SKILL_OVERRIDES.get(item.name, item) for item in SKILL_LIST)
    if version == "v3":
        return tuple(V3_SKILL_OVERRIDES.get(item.name, item) for item in versioned_skills("v2"))
    if version == "v4":
        return versioned_skills("v3") + V4_SKILLS
    if version == "v4b":
        return tuple(V4B_SKILL_OVERRIDES.get(item.name, item) for item in versioned_skills("v4"))
    if version == "v4c":
        return tuple(V4C_SKILL_OVERRIDES.get(item.name, item) for item in versioned_skills("v4b"))
    if version == T_STRUCTURE_VERSION:
        return (T_HORIZONTAL_SKILL,) + versioned_skills("v3")
    raise ValueError(f"unknown skill library version: {version}")


PLACEBO_WORDS = (
    "read", "the", "current", "view", "then", "choose", "one", "valid",
    "action", "check", "the", "new", "state", "and", "continue", "while",
    "the", "task", "is", "unfinished",
)


def placebo_text(source: str, offset: int = 0) -> str:
    count = len(source.split())
    return " ".join(PLACEBO_WORDS[(offset + index) % len(PLACEBO_WORDS)] for index in range(count)) + "."


def render(item: ScienceWorldSkill, mode: str = "full") -> str:
    if mode == "metadata_only":
        return f"Name\n{item.name}\n\nDescription\n{item.description}\n\nActivation Condition\n{item.activation_condition}\n"
    if mode not in {"full", "placebo"}:
        raise ValueError(f"unknown Skill render mode: {mode}")
    steps = item.procedure if mode == "full" else tuple(
        placebo_text(step, index * 5) for index, step in enumerate(item.procedure)
    )
    termination = item.termination_condition if mode == "full" else placebo_text(item.termination_condition)
    procedure = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, 1))
    return f"Name\n{item.name}\n\nDescription\n{item.description}\n\nActivation Condition\n{item.activation_condition}\n\nProcedure\n{procedure}\n\nTermination Condition\n{termination}\n"


def loaded_skill_text(names: Iterable[str], version: str = "v1", mode: str = "full") -> str:
    selected = {item.name: item for item in versioned_skills(version)}
    return "\n---\n".join(render(selected[name], mode) for name in names)


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
    if len(V4_SKILLS) != len(V4_GOLD_SKILLS) or set(V4_GOLD_SKILLS.values()) != {item.name for item in V4_SKILLS}:
        errors.append("v4 task families must map to four distinct new Skills")
    if set(V4_GOLD_SKILLS) & set(GOLD_SKILLS) or {item.name for item in V4_SKILLS} & set(SKILLS):
        errors.append("v4 must not replace any v3 task family or Skill")
    if any(name not in {item.name for item in V4_SKILLS} or item.name != name for name, item in V4B_SKILL_OVERRIDES.items()):
        errors.append("v4b overrides must replace existing v4 Skills without renaming them")
    if any(name not in {item.name for item in V4_SKILLS} or item.name != name for name, item in V4C_SKILL_OVERRIDES.items()):
        errors.append("v4c overrides must replace existing v4 Skills without renaming them")
    if T_HORIZONTAL_SKILL_NAME in SKILLS:
        errors.append("the horizontal Skill must not replace a task-specific Skill")
    if set(T_VERTICAL_PATHS) != set(GOLD_SKILLS):
        errors.append("every task family must have one frozen vertical path")
    if any(len(path) < 2 for path in T_VERTICAL_PATHS.values()):
        errors.append("every vertical path must include a domain and a task leaf")
    for item in SKILL_LIST + V4_SKILLS + tuple(V4B_SKILL_OVERRIDES.values()) + tuple(V4C_SKILL_OVERRIDES.values()):
        if not all((item.name, item.description, item.activation_condition, item.procedure, item.termination_condition)):
            errors.append(f"{item.name}: all five fields are required")
    return errors


assert not validate_library(), validate_library()
