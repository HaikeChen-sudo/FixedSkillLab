"""Hand-authored, fixed procedures for the Mini Lab's first skill phase."""

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    activation_condition: str
    procedure: Tuple[str, ...]
    termination_condition: str


def skill(
    name: str, description: str, activation: str, *procedure: str, termination: str
) -> Skill:
    return Skill(name, description, activation, procedure, termination)


SKILL_LIST = [
    skill(
        "file-read", "Read one named text file before using its contents.",
        "Use when the task names a file whose text determines the answer or next action.",
        "Call read_file with the named path.",
        "Extract only the value needed by the task.",
        termination="The required value is known or a read error makes the task impossible.",
    ),
    skill(
        "file-write", "Create or replace one text file with exact content.",
        "Use when a task requires a file at a known path with specified text.",
        "Build the exact requested content, including newlines.",
        "Call write_file once with the target path and content.",
        termination="The target file has been written; let the task grader judge its contents.",
    ),
    skill(
        "file-copy", "Copy a file while retaining the source.",
        "Use when a task asks for a duplicate at a second path.",
        "Call copy_file with the stated source and destination.",
        "Do not alter the source unless a later task instruction explicitly requires it.",
        termination="The copy operation returns successfully.",
    ),
    skill(
        "file-move", "Relocate a file and remove its old path.",
        "Use when a task says move, archive, relocate, or rename a file.",
        "Call move_file with the original and destination paths.",
        "Repeat for every explicitly named file.",
        termination="Every requested move returns successfully.",
    ),
    skill(
        "file-search", "Find text occurrences below a file or directory path.",
        "Use when the answer depends on files or lines containing a literal query.",
        "Call search_text with the exact case-sensitive query and bounded path.",
        "Derive file paths, line counts, or line text from the returned records.",
        termination="The requested search result has been derived from all returned records.",
    ),
    skill(
        "file-listing", "Enumerate files matching a filename pattern.",
        "Use when a task asks which files exist or asks for a list of matching paths.",
        "Call list_files with the narrowest stated directory and pattern.",
        "Use the returned sorted relative paths without inventing extra paths.",
        termination="The required path list has been obtained.",
    ),
    skill(
        "text-replacement", "Replace every literal occurrence in one text file.",
        "Use when a task gives old and new text for a named file.",
        "Call replace_text with the path, old text, and new text.",
        "If several files are named, repeat once per file.",
        termination="Each requested file has been replaced successfully.",
    ),
    skill(
        "config-editing", "Make a narrow deterministic configuration substitution.",
        "Use when a configuration file needs one literal setting changed without reformatting it.",
        "Read the file if the target value is not explicit.",
        "Use replace_text for the exact old and new fragments.",
        termination="The requested setting has been replaced and no unrelated rewrite was performed.",
    ),
    skill(
        "arithmetic-calculation", "Evaluate one arithmetic expression safely through the calculator tool.",
        "Use when the task states a numeric expression or reduces to one.",
        "Write the expression using only numeric literals and arithmetic operators.",
        "Call calculate and retain its returned number.",
        termination="A finite numeric result is returned or the calculator reports invalid input.",
    ),
    skill(
        "answer-submission", "Submit a final scalar or structured answer for a non-file task.",
        "Use when the task explicitly asks to submit a value, count, path, or list.",
        "Derive the answer from tool output.",
        "Call submit with the value in its native JSON type.",
        termination="The answer has been recorded by submit.",
    ),
    skill(
        "csv-analysis", "Inspect a CSV through targeted aggregate or extrema tools.",
        "Use when a task asks for a count, total, minimum, or maximum from a CSV column.",
        "Choose count_rows, sum_column, find_min, or find_max to match the requested statistic.",
        "Pass numeric=True only when the comparison is numeric.",
        termination="The requested statistic has been returned by one CSV tool.",
    ),
    skill(
        "json-conversion", "Convert CSV rows into a JSON array file.",
        "Use when a task asks to turn a CSV file into JSON.",
        "Call convert_csv with the CSV source and JSON destination.",
        "Do not manually serialize rows unless conversion cannot be used.",
        termination="The conversion tool returns a row count.",
    ),
    skill(
        "csv-sorting", "Order a CSV by one column into a destination CSV.",
        "Use when a task asks for sorted, ranked, ascending, or descending CSV rows.",
        "Identify the requested column and direction.",
        "Call sort_data; set numeric=True for number-like values.",
        termination="The sorted destination has been written.",
    ),
    skill(
        "csv-filtering", "Keep CSV rows that satisfy one explicit comparison.",
        "Use when a task asks to retain, exclude, or threshold rows.",
        "Map the condition to eq, ne, gt, ge, lt, or le.",
        "Call filter_data with numeric=True only for numeric comparisons.",
        termination="The filtered destination has been written.",
    ),
    skill(
        "csv-extrema", "Find one largest or smallest CSV value.",
        "Use when a task asks for a maximum, minimum, highest, or lowest value.",
        "Choose find_max or find_min for the stated column.",
        "Set numeric=True when values represent numbers.",
        termination="The requested extreme value has been returned.",
    ),
    skill(
        "csv-summing", "Compute the numeric total of one CSV column.",
        "Use when a task asks for a sum, total, or aggregate amount.",
        "Call sum_column with the source and column.",
        "Use the returned number directly in a submission or output file.",
        termination="The total has been returned.",
    ),
    skill(
        "row-counting", "Count CSV data rows without counting the header.",
        "Use when a task asks how many records a CSV contains.",
        "Call count_rows with the source CSV path.",
        "Submit or reuse the returned integer.",
        termination="The row count has been returned.",
    ),
    skill(
        "log-inspection", "Identify errors or matching log lines using literal search.",
        "Use when a task asks about ERROR, WARN, or another known log token.",
        "Call search_text with the token and log directory.",
        "Count matches or deduplicate file paths as the task requests.",
        termination="The requested log fact has been derived from matching records.",
    ),
    skill(
        "statistical-summary", "Produce one requested summary statistic from structured data.",
        "Use when a task asks for count, total, minimum, or maximum and no transformation is needed.",
        "Select the matching CSV aggregate tool.",
        "Submit the returned result or write it in the requested format.",
        termination="The one requested statistic has been emitted in the required destination.",
    ),
    skill(
        "threshold-filter", "Filter numeric CSV values at an inclusive or exclusive threshold.",
        "Use when a task uses phrases such as greater than, at least, at most, or below.",
        "Map the phrase to gt, ge, le, or lt.",
        "Call filter_data with numeric=True and the stated threshold.",
        termination="The threshold-filtered CSV has been written.",
    ),
    skill(
        "ranking-table", "Create a ranked CSV ordering from a numeric score column.",
        "Use when a task asks for highest-first or lowest-first rankings.",
        "Call sort_data on the score column with numeric=True.",
        "Set descending=True for highest-first rankings.",
        termination="The ranking CSV has been written in the requested direction.",
    ),
    skill(
        "table-to-json", "Transform a prepared or source CSV table into JSON.",
        "Use when the final output must be a JSON representation of CSV rows.",
        "Ensure any required filtering or sorting CSV step is complete.",
        "Call convert_csv from that CSV to the requested JSON destination.",
        termination="The JSON output has been written.",
    ),
    skill(
        "totals-report", "Write a CSV numeric total into a specified text report format.",
        "Use when a task asks for a total and a text file such as total=VALUE.",
        "Call sum_column for the required column.",
        "Build exactly the requested report text and call write_file.",
        termination="The report file contains the returned total in the requested format.",
    ),
    skill(
        "maximum-report", "Write a CSV maximum into a specified text report format.",
        "Use when a task asks for a highest value and a summary text file.",
        "Call find_max with numeric=True when appropriate.",
        "Write the returned value with the exact requested label and newline.",
        termination="The summary file contains the maximum in the requested format.",
    ),
    skill(
        "filter-then-convert", "Create JSON from a subset of CSV rows.",
        "Use when a task first imposes a CSV row condition and finally requests JSON.",
        "Call filter_data into a temporary CSV path.",
        "Call convert_csv from that temporary CSV to the final JSON path.",
        termination="The final JSON contains only the selected rows.",
    ),
    skill(
        "sort-then-convert", "Create JSON from an ordered CSV table.",
        "Use when a task requires CSV sorting before a JSON result.",
        "Call sort_data into a temporary CSV path.",
        "Call convert_csv from that temporary CSV to the final JSON path.",
        termination="The final JSON preserves the requested order.",
    ),
    skill(
        "copy-then-customize", "Make a derived file without modifying its template.",
        "Use when a task asks to copy a template and change placeholders only in the copy.",
        "Call copy_file to create the derived path.",
        "Call replace_text on the derived file for each stated placeholder.",
        termination="The derived file is customized and the template remains unchanged.",
    ),
    skill(
        "batch-archival", "Move several named files into one archive directory.",
        "Use when a task lists multiple files to archive while retaining their filenames.",
        "For each named source, call move_file with archive/<filename> as destination.",
        "Do not touch unlisted files.",
        termination="Every listed file is present in the archive and absent from its source path.",
    ),
    skill(
        "search-and-count", "Count literal text matches across one bounded tree.",
        "Use when a task asks how many matching lines or records a query has.",
        "Call search_text with the exact query and stated path.",
        "Count returned records and submit the integer.",
        termination="The matching-record count has been submitted.",
    ),
    skill(
        "read-calculate-submit", "Derive an arithmetic answer from a small configuration file.",
        "Use when a task supplies numeric inputs in text and asks for a computed submitted result.",
        "Call read_file and extract the stated numeric inputs.",
        "Call calculate with the requested expression, then submit the result.",
        termination="The computed value has been submitted.",
    ),
]


SKILLS: Dict[str, Skill] = {item.name: item for item in SKILL_LIST}


def render(skill_item: Skill) -> str:
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(skill_item.procedure, 1))
    return (
        f"Name\n{skill_item.name}\n\n"
        f"Description\n{skill_item.description}\n\n"
        f"Activation Condition\n{skill_item.activation_condition}\n\n"
        f"Procedure\n{steps}\n\n"
        f"Termination Condition\n{skill_item.termination_condition}\n"
    )


def validate_library() -> List[str]:
    errors = []
    if len(SKILLS) != 30:
        errors.append(f"expected 30 skills, got {len(SKILLS)}")
    if len(SKILLS) != len(SKILL_LIST):
        errors.append("skill names must be unique")
    for item in SKILL_LIST:
        if not item.name or not item.description or not item.activation_condition or not item.procedure or not item.termination_condition:
            errors.append(f"{item.name}: all five fields are required")
        if any(not step for step in item.procedure):
            errors.append(f"{item.name}: procedure contains an empty step")
    return errors


assert not validate_library(), validate_library()
