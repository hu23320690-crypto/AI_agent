"""Request-owned runs preserve cancellation before a synchronous worker starts."""
from dataclasses import replace
from threading import Event, Thread
import unittest
from unittest.mock import patch

from agent.runtime import DeadlineExceeded, ExecutionRuntime, RunCancelled, RunContext, RunLimits
from test_core_flows import ScriptedModel, answer, scripted_agent


def isolated_agent(*, limits=None):
    limits = limits or RunLimits()
    executor = ExecutionRuntime(limits)
    model = ScriptedModel(responses=[answer('完整回答')])
    agent = scripted_agent('1001', model=model, limits=limits, executor=executor)
    return agent, model


class ExternalRunContextTests(unittest.TestCase):
    def test_valid_external_run_keeps_identity_and_commits(self):
        agent, model = isolated_agent()
        run = RunContext(agent.limits, agent.executor)
        self.assertEqual(''.join(agent.execute_stream('问题', run_context=run)), '完整回答')
        self.assertEqual(run.status, 'succeeded')
        self.assertEqual(agent.last_run['run_id'], run.run_id)
        self.assertEqual(len(model.seen), 1)
        self.assertEqual(agent.messages[-1].content, '完整回答')
        self.assertIsNone(agent._active_run)

    def test_original_call_remains_compatible(self):
        agent, model = isolated_agent()
        self.assertEqual(''.join(agent.execute_stream('问题')), '完整回答')
        self.assertEqual(agent.last_run['status'], 'succeeded')
        self.assertEqual(len(model.seen), 1)

    def test_cancellation_before_worker_starts_cannot_create_a_fresh_run(self):
        agent, model = isolated_agent()
        run = RunContext(agent.limits, agent.executor)
        # Constructing the generator does not yet start the turn.
        pending = agent.execute_stream('排队中的问题', run_context=run)
        run.cancel()
        with self.assertRaises(RunCancelled):
            list(pending)
        self.assertEqual(run.status, 'cancelled')
        self.assertEqual(agent.last_run['run_id'], run.run_id)
        self.assertEqual(agent.messages, [])
        self.assertEqual(model.seen, [])
        self.assertEqual(run.counts, {})
        self.assertIsNone(agent._active_run)
        # The cancelled turn also releases the per-session lock.
        self.assertEqual(''.join(agent.execute_stream('下一轮')), '完整回答')

    def test_queued_deadline_is_not_reset_at_worker_start(self):
        agent, model = isolated_agent()
        now = [10.0]
        run = RunContext(agent.limits, agent.executor, clock=lambda: now[0])
        pending = agent.execute_stream('问题', run_context=run)
        now[0] = run.deadline
        with self.assertRaises(DeadlineExceeded):
            list(pending)
        self.assertEqual(run.status, 'timed_out')
        self.assertEqual(model.seen, [])
        self.assertEqual(agent.messages, [])

    def test_cancel_at_commit_boundary_prevents_history_commit(self):
        agent, model = isolated_agent()
        run = RunContext(agent.limits, agent.executor)
        entered, release = Event(), Event()
        errors = []
        original_complete = run.complete

        def delayed_complete(**kwargs):
            entered.set()
            if not release.wait(3):
                raise AssertionError('test did not release commit barrier')
            return original_complete(**kwargs)

        def turn():
            try:
                list(agent.execute_stream('问题', run_context=run))
            except BaseException as exc:
                errors.append(exc)

        with patch.object(run, 'complete', side_effect=delayed_complete):
            worker = Thread(target=turn)
            worker.start()
            try:
                self.assertTrue(entered.wait(2), 'turn did not reach commit')
                self.assertEqual(len(model.seen), 1)
                run.cancel()
            finally:
                release.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RunCancelled)
        self.assertEqual(agent.messages, [])
        self.assertEqual(agent.last_run['status'], 'cancelled')

    def test_wrong_limits_are_rejected_without_dispatch(self):
        agent, model = isolated_agent()
        run = RunContext(replace(agent.limits, max_model_calls=1), agent.executor)
        with self.assertRaises(ValueError):
            list(agent.execute_stream('问题', run_context=run))
        self.assertEqual(model.seen, [])
        self.assertEqual(agent.messages, [])
        self.assertIsNone(agent.last_run)
        self.assertEqual(run.status, 'running')

    def test_wrong_executor_is_rejected_without_dispatch(self):
        agent, model = isolated_agent()
        run = RunContext(agent.limits, ExecutionRuntime(agent.limits))
        with self.assertRaises(ValueError):
            list(agent.execute_stream('问题', run_context=run))
        self.assertEqual(model.seen, [])
        self.assertIsNone(agent.last_run)
        self.assertEqual(run.status, 'running')

    def test_non_run_context_is_rejected(self):
        agent, model = isolated_agent()
        with self.assertRaises(TypeError):
            list(agent.execute_stream('问题', run_context={'cancelled': False}))
        self.assertEqual(model.seen, [])
        self.assertIsNone(agent.last_run)

    def test_completed_external_run_is_not_reused(self):
        agent, model = isolated_agent()
        run = RunContext(agent.limits, agent.executor)
        run.complete()
        with self.assertRaises(RunCancelled):
            list(agent.execute_stream('问题', run_context=run))
        self.assertEqual(run.status, 'succeeded')
        self.assertEqual(agent.messages, [])
        self.assertEqual(model.seen, [])


if __name__ == '__main__':
    unittest.main()
