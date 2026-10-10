-- Keep batch boundaries: protocols and task selection changed between batches.
SELECT * FROM condition_metrics
WHERE batch_id = 'scienceworld_v11b'
ORDER BY condition;

-- Failures remain visible, including long runs rather than only successful costs.
SELECT batch_id, task_id, condition, repeat, score, total_tokens, cost_usd
FROM episodes
WHERE success = 0
ORDER BY total_tokens DESC
LIMIT 20;

-- Same task/repeat, same batch. Check paired coverage before interpreting deltas.
SELECT a.task_id, a.repeat,
       a.success AS flat_success, b.success AS body_success,
       b.total_tokens - a.total_tokens AS body_minus_flat_tokens,
       CASE WHEN a.skill_prompt_sha256 IS NOT NULL AND b.skill_prompt_sha256 IS NOT NULL
            THEN a.skill_prompt_sha256 = b.skill_prompt_sha256 END AS same_skill_prompt
FROM episodes AS a
JOIN episodes AS b
  ON a.batch_id = b.batch_id AND a.task_id = b.task_id AND a.repeat = b.repeat
WHERE a.batch_id = 'semantic_top3'
  AND a.condition = 'semantic_flat_retrieval'
  AND b.condition = 'semantic_body_retrieval'
ORDER BY a.task_id, a.repeat;

-- A null fingerprint is unknown, not an empty prompt or an equal prompt.
SELECT batch_id, COUNT(*) AS episodes,
       SUM(runner_ms IS NULL) AS missing_end_to_end,
       SUM(skill_prompt_sha256 IS NULL) AS missing_skill_prompt_hash,
       SUM(initial_observation_sha256 IS NULL) AS missing_initial_observation_hash
FROM episodes GROUP BY batch_id;

-- One row per loaded Skill; position retains loading order.
SELECT e.batch_id, e.task_id, e.condition, e.repeat, s.position, s.skill_name
FROM episodes e JOIN loaded_skills s USING (episode_id)
WHERE e.batch_id = 'semantic_top3'
ORDER BY e.task_id, e.repeat, e.condition, s.position;

SELECT * FROM data_dictionary ORDER BY table_name, column_name;
