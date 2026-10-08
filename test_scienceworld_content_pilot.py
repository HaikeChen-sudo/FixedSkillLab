import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scienceworld_agent as agent
import scienceworld_content_pilot as pilot
from test_scienceworld_top1_pilot import FakeClient, FakeEnv


class ContentPilotTests(unittest.TestCase):
    def cases(self):
        return pilot.choose_cases(dict(train=[0], dev=list(range(10, 18)), test=[30]), {(pilot.TASK, 10)})

    def test_selection_excludes_seen_and_rejects_overlap(self):
        self.assertEqual([r['variation'] for r in self.cases()], [11, 12, 13, 14])
        with self.assertRaises(ValueError):
            pilot.choose_cases(dict(train=[1], dev=[1, 2, 3, 4], test=[]), set())

    def test_plan_is_48_unique_episodes_with_balanced_positions(self):
        rows = pilot.plan(self.cases())
        self.assertEqual(len(rows), 48)
        self.assertEqual(len({(r['task_id'], r['condition'], r['repeat']) for r in rows}), 48)
        for repeat in range(3):
            for condition in pilot.CONDITIONS:
                self.assertEqual(sorted(r['order_position'] for r in rows if r['repeat'] == repeat and r['condition'] == condition), [0, 1, 2, 3])

    def test_only_one_procedure_line_changes(self):
        specs = pilot.prompt_specs()
        before = specs['content_correct']['prompt']
        after = specs['content_pickup_required']['prompt']
        self.assertEqual(after, before.replace(pilot.ORIGINAL_STEP, pilot.REQUIRED_STEP))
        self.assertEqual(len(pilot.ORIGINAL_STEP.split()), len(pilot.REQUIRED_STEP.split()))
        self.assertEqual(sum(a != b for a, b in zip(before.splitlines(), after.splitlines())), 1)
        self.assertNotEqual(specs['content_correct']['library_sha256'], specs['content_pickup_required']['library_sha256'])

    def record(self, expected, manifest, queries):
        query = queries['cases'][0]['query']
        with patch.object(agent, 'make_env', return_value=FakeEnv(query)), \
                patch.object(agent, 'DeepSeekChatClient', FakeClient), \
                patch.object(agent, 'skill_selection', side_effect=AssertionError('Router must not run')):
            row = agent.run_episode(pilot.MODEL, 0.0, pilot.TASK, expected['variation'], 'easy', pilot.LIMIT,
                                    expected['condition'], environment_max_steps=pilot.LIMIT,
                                    fixed_guidance=pilot.guidance(expected['condition'], query, manifest))
        row.update(expected, run_id=pilot.RUN_ID, thinking='disabled', variation_split='dev',
                   content_manifest_sha256=pilot.file_hash(pilot.MANIFEST), content_queries_sha256=pilot.file_hash(pilot.QUERIES),
                   runner_ms=row['latency_ms'], **pilot.trace_counts(row['trace']))
        return row

    def test_all_four_actual_message_payloads_and_record_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            manifest = dict(prompts=pilot.prompt_specs())
            queries = dict(cases=[dict(task_id=self.cases()[0]['task_id'], query='Find a non-living thing.')])
            (path/'manifest').write_text(json.dumps(manifest))
            (path/'queries').write_text(json.dumps(queries))
            with patch.object(pilot, 'MANIFEST', path/'manifest'), patch.object(pilot, 'QUERIES', path/'queries'):
                for condition in pilot.CONDITIONS:
                    expected = dict(self.cases()[0], condition=condition, repeat=0, order_position=0, plan_index=0)
                    row = self.record(expected, manifest, queries)
                    pilot.validate_record(row, expected, manifest, queries)
                    messages = [m['content'] for m in FakeClient.messages if m['content'].startswith('Fixed Skill guidance:')]
                    prompt = manifest['prompts'][condition]['prompt']
                    self.assertEqual(messages, ['Fixed Skill guidance:\n' + prompt] if prompt else [])
                    for field, bad in [('skill_prompt_sha256','bad'), ('max_steps',999), ('condition','other'), ('total_tokens',-1)]:
                        changed = dict(row, **{field:bad})
                        with self.assertRaises(ValueError):
                            pilot.validate_record(changed, expected, manifest, queries)

    def test_task_drift_stops_before_client_and_closes_environment(self):
        env = FakeEnv('changed task')
        manifest = dict(prompts=pilot.prompt_specs())
        with patch.object(agent, 'make_env', return_value=env), patch.object(env, 'close') as close, \
                patch.object(agent, 'DeepSeekChatClient', side_effect=AssertionError('No API')) as client:
            with self.assertRaises(ValueError):
                agent.run_episode(pilot.MODEL,0,pilot.TASK,11,'easy',100,'content_correct',
                                  fixed_guidance=pilot.guidance('content_correct','original task',manifest))
            client.assert_not_called()
            close.assert_called_once()

    def test_resume_rejects_duplicate_before_another_episode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'episodes.jsonl'
            path.write_text('{"plan_index":0}\n{"plan_index":0}\n')
            with patch.object(pilot,'RESULTS',path), patch.object(pilot,'validate_record'):
                with self.assertRaises(ValueError):
                    pilot.saved_records(dict(episode_plan=[{}]), {})

    def test_default_preview_never_calls_environment_or_model(self):
        with patch.object(pilot,'make_env',side_effect=AssertionError('No env')), \
                patch.object(pilot,'run_episode',side_effect=AssertionError('No API')):
            self.assertEqual(pilot.main([]),0)

    def test_pickup_counts_commands_not_inferred_success(self):
        self.assertEqual(pilot.trace_counts([dict(command=' Pick  up apple ',result=dict(ok=True)),
                                             dict(command='move apple to box',result=dict(ok=False))]),
                         dict(pickup_command_count=1, tool_error_count=1))


if __name__ == '__main__':
    unittest.main()
