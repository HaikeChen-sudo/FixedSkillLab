"""Small helpers for reading immutable experiment records."""


def deduplicate_records(records):
    """Keep the first saved episode for each planned run position."""
    kept = []
    seen = set()
    for record in records:
        task = record.get("task_index", record.get("task_id"))
        key = (record.get("run_id"), task, record.get("condition"), record.get("repeat", 0))
        if key in seen:
            continue
        seen.add(key)
        kept.append(record)
    return kept, len(records) - len(kept)
