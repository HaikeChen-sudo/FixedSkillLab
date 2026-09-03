"""Fixed, hand-authored Skills for the text-only ALFWorld experiment."""

import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class AlfworldSkill:
    name: str
    description: str
    activation_condition: str
    procedure: Tuple[str, ...]
    termination_condition: str


def skill(name: str, description: str, activation: str, *procedure: str, termination: str) -> AlfworldSkill:
    return AlfworldSkill(name, description, activation, procedure, termination)


SKILL_LIST = [
    skill("task-goal-parse", "Extract the object, required state, and destination from the task.", "Use at the first observation.", "Identify target object, transformation, and final receptacle.", "Keep these three facts in memory.", termination="The required end state is explicit."),
    skill("room-search", "Explore rooms methodically when a required object has not been found.", "Use after the target location is unknown.", "Visit one unsearched receptacle at a time.", "Read every observation before choosing the next location.", termination="The target or a useful location clue has been found."),
    skill("container-search", "Find an object inside openable or visible receptacles.", "Use when the target object is not on the current floor or surface.", "Go to likely receptacles and open them when needed.", "Inspect the observation after each open action.", termination="The target object's current container is known."),
    skill("inventory-check", "Check whether the agent already carries an object before fetching it again.", "Use before moving, transforming, or placing a target.", "Read the latest observation for inventory facts.", "If held, continue with the next required operation.", termination="It is known whether the target is held."),
    skill("find-object", "Locate one named target object.", "Use when the task names an object whose location is unknown.", "Search likely receptacles using room-search and container-search.", "Take the object once it is found and needed.", termination="The required object is held or its exact location is known."),
    skill("find-receptacle", "Locate the named destination receptacle.", "Use when the task states a destination whose location is unknown.", "Search rooms and inspect matching furniture or containers.", "Open it if the final placement needs it open.", termination="The destination can receive the object."),
    skill("open-container", "Open a closed container only when access requires it.", "Use when an object or destination is inside an openable closed receptacle.", "Go to the receptacle.", "Call open <receptacle> and inspect the returned observation.", termination="The receptacle is open or the environment rejects opening it."),
    skill("close-container", "Close a container when an appliance action requires closure.", "Use immediately before heating or cooling if the appliance is open.", "Ensure the held target is inside the appliance.", "Call close <appliance>.", termination="The appliance is closed."),
    skill("object-transfer", "Move a held object to its final receptacle with ALFWorld action syntax.", "Use after the target has the required state and destination is ready.", "Go to the destination.", "Call move <object> to <receptacle>.", termination="The environment reports completion or the object is placed."),
    skill("action-syntax-recovery", "Recover from a rejected action by using ALFWorld's exact verbs.", "Use after an action error or an unsupported put/place command.", "Read the error literally.", "For final placement, prefer move <object> to <receptacle>.", termination="A valid next command is available."),
    skill("heat-object", "Heat a held object in a microwave.", "Use when the goal requires the object to be hot.", "Go to a microwave and open it if needed.", "Move the object into it, close it, then call heat <object> with <microwave>.", termination="The observation confirms the object is heated."),
    skill("cool-object", "Cool a held object in a fridge.", "Use when the goal requires the object to be cold.", "Go to a fridge and open it if needed.", "Move the object into it, close it, then call cool <object> with <fridge>.", termination="The observation confirms the object is cooled."),
    skill("clean-object", "Clean a held object at a sink basin.", "Use when the goal requires the object to be clean.", "Go to a sink basin.", "Call clean <object> with <sink basin>.", termination="The observation confirms the object is clean."),
    skill("appliance-precondition", "Meet appliance preconditions before a state-changing action.", "Use before heat or cool actions.", "Put the target inside the correct appliance.", "Close the appliance if its observation says it is open.", termination="The appliance action can be attempted."),
    skill("execute-heat-place", "Complete a heat-then-place task in goal order.", "Use for pick_heat_then_place_in_recep goals.", "Find and take the target.", "Heat it in a microwave, then move it to the final receptacle.", termination="The environment marks the task won."),
    skill("execute-cool-place", "Complete a cool-then-place task in goal order.", "Use for pick_cool_then_place_in_recep goals.", "Find and take the target.", "Cool it in a fridge, then move it to the final receptacle.", termination="The environment marks the task won."),
    skill("execute-clean-place", "Complete a clean-then-place task in goal order.", "Use for pick_clean_then_place_in_recep goals.", "Find and take the target.", "Clean it at a sink basin, then move it to the final receptacle.", termination="The environment marks the task won."),
    skill("two-object-placement", "Place both requested objects in one destination.", "Use for pick_two_obj_and_place goals.", "Find, take, and move the first target to the destination.", "Repeat for the second target; do not stop after one object.", termination="The environment marks the task won."),
    skill("look-at-object", "Inspect a target object under its required desk lamp.", "Use for look_at_obj goals.", "Find and take the target object.", "Go to the desk lamp and call use <desklamp> while holding the target.", termination="The environment marks the task won."),
    skill("use-desk-lamp", "Use a desk lamp to complete an inspection task.", "Use when the task asks to look at an object under a lamp.", "Hold the target object and go to the desk lamp.", "Call use <desklamp>; do not call toggle or examine first.", termination="The environment marks the task won or rejects the command."),
    skill("observation-memory", "Use the latest environment observation as the state record.", "Use after every act call.", "Record locations, open/closed state, held objects, and error messages.", "Do not repeat a failed action without changed preconditions.", termination="The next action follows from current evidence."),
    skill("target-disambiguation", "Choose the exact numbered object named in the observation.", "Use when several objects share a noun.", "Match the target to its displayed number and location.", "Reuse the same identifier until the object moves.", termination="One unambiguous target reference is selected."),
    skill("source-receptacle-selection", "Choose a plausible source receptacle for a missing object.", "Use when several containers could hold the target.", "Prefer receptacles mentioned in observations, then likely room furniture.", "Inspect before moving to another candidate.", termination="A source is inspected or ruled out."),
    skill("shortest-navigation", "Avoid unnecessary room changes while completing a known plan.", "Use when source, appliance, and destination are known.", "Complete all useful actions at the current location first.", "Move only to the next location needed by the plan.", termination="The next move is required by the task."),
    skill("goal-state-check", "Check whether the environment, not the model, has declared success.", "Use after a final placement or examine action.", "Read won and done from the tool result.", "Stop issuing actions when won is true.", termination="Success or incomplete state is known from the environment."),
    skill("invalid-action-recovery", "Recover after a failed command without restarting the whole plan.", "Use whenever act returns an error or no state change.", "Identify the unmet precondition from the observation.", "Issue one corrected action rather than repeating the same command.", termination="A corrected next action is identified."),
    skill("light-inspection-sequence", "Execute the ALFWorld light-assisted inspection sequence.", "Use when the task requires looking at an object under a lamp.", "Find and take the target object.", "Go to the desk lamp and call use <desklamp> while holding the target.", termination="The environment marks the task won."),
    skill("endgame-recovery", "Finish a nearly complete task after an incomplete final action.", "Use when the target was transformed but the task is not won.", "Check whether the target remains held, inside an appliance, or at a wrong receptacle.", "Move it to the named final receptacle using exact syntax.", termination="The task is won or the missing precondition is known."),
    skill("step-budget-management", "Use actions deliberately under a fixed step limit.", "Use throughout every episode.", "Prefer known goal actions over broad exploration.", "After an error, correct the command instead of retrying blindly.", termination="The task is done or no justified action remains."),
    skill("simple-pick-place", "Put one ordinary object in or on a named destination receptacle.", "Use when the task says put some object in or on a receptacle with no requested transformation.", "Find and take the target object.", "Find the destination and move the target there.", termination="The environment marks the task won."),
]

SKILLS: Dict[str, AlfworldSkill] = {item.name: item for item in SKILL_LIST}


def render(item: AlfworldSkill) -> str:
    procedure = "\n".join(f"{index}. {step}" for index, step in enumerate(item.procedure, 1))
    return f"Name\n{item.name}\n\nDescription\n{item.description}\n\nActivation Condition\n{item.activation_condition}\n\nProcedure\n{procedure}\n\nTermination Condition\n{item.termination_condition}\n"


def loaded_skill_text(names: Iterable[str]) -> str:
    return "\n---\n".join(render(SKILLS[name]) for name in names)


def library_hash() -> str:
    return hashlib.sha256("\n".join(render(item) for item in SKILL_LIST).encode("utf-8")).hexdigest()


def validate_library() -> List[str]:
    errors = []
    if len(SKILL_LIST) != 30:
        errors.append(f"expected 30 skills, got {len(SKILL_LIST)}")
    if len(SKILLS) != len(SKILL_LIST):
        errors.append("skill names must be unique")
    for item in SKILL_LIST:
        if not all((item.name, item.description, item.activation_condition, item.procedure, item.termination_condition)):
            errors.append(f"{item.name}: all five fields are required")
    return errors


assert not validate_library(), validate_library()
