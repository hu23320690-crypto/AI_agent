"""Evidence I/O must not prevent cancellation or commit after a deadline."""
from dataclasses import replace
from threading import Event, Thread
import unittest

from agent.runtime import (
    RunContext, RunLimits, ExecutionRuntime, RunCancelled,
    DeadlineExceeded, CallTimeout,
)


def isolated_run(**changes):
    limits = replace(RunLimits(), **changes)
    return RunContext(limits, ExecutionRuntime(limits))


class CommitBoundaryTests(unittest.TestCase):
    def test_next_turn_history_validation_obeys_deadline_without_changing_history(self):
        from langchain_core.messages import HumanMessage
        from test_core_flows import ScriptedModel, answer, scripted_agent

        limits = replace(RunLimits(), total_seconds=.15)
        model = ScriptedModel(responses=[answer('must-not-call-model')])
        agent = scripted_agent('1001', model=model, limits=limits, executor=ExecutionRuntime(limits))
        previous = [HumanMessage(content='previous question'), answer('previous grounded answer')]
        agent.messages = list(previous)
        entered, release, check_exited, finished = Event(), Event(), Event(), Event()
        errors = []

        def history_check():
            entered.set()
            try:
                release.wait(3)
            finally:
                check_exited.set()

        def next_turn():
            try:
                list(agent.execute_stream('new question'))
            except BaseException as exc:
                errors.append(exc)
            finally:
                finished.set()

        agent._history_checks = [history_check]
        worker = Thread(target=next_turn)
        worker.start()
        try:
            self.assertTrue(entered.wait(1), 'Historic evidence validation did not start')
            self.assertTrue(finished.wait(1), 'Historic evidence I/O delayed the turn deadline')
            self.assertFalse(check_exited.is_set(), 'Historic evidence I/O unexpectedly finished early')
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], (DeadlineExceeded, CallTimeout))
            self.assertEqual(agent.last_run['status'], 'timed_out')
            self.assertEqual(agent.messages, previous)
            self.assertEqual(agent._history_checks, [history_check])
            self.assertEqual(model.seen, [], 'A new model call started despite the timed-out history check')
            completed_snapshot = agent.last_run
        finally:
            release.set()
            worker.join(2)
        self.assertTrue(check_exited.wait(1), 'Late historic evidence validation did not exit')
        self.assertFalse(worker.is_alive())
        self.assertEqual(agent.messages, previous, 'Late historic evidence validation modified history')
        self.assertEqual(agent._history_checks, [history_check])
        self.assertEqual(agent.last_run, completed_snapshot)
        self.assertEqual(model.seen, [])

    def test_evidence_io_does_not_block_cancellation(self):
        run = isolated_run(total_seconds=5)
        entered, release, cancelled = Event(), Event(), Event()
        errors = []

        def evidence_check():
            entered.set()
            release.wait(3)

        def validate():
            try:
                run.validate_commit_checks()
            except BaseException as exc:
                errors.append(exc)

        def cancel():
            run.cancel()
            cancelled.set()

        run.add_commit_check(evidence_check)
        worker = Thread(target=validate)
        cancellation = Thread(target=cancel)
        worker.start()
        try:
            self.assertTrue(entered.wait(1), "Evidence validation did not start")
            cancellation.start()
            self.assertTrue(cancelled.wait(.5), "Cancellation waited for evidence I/O")
            self.assertEqual(run.status, 'cancelled')
        finally:
            release.set()
            worker.join(2)
            if cancellation.ident is not None:
                cancellation.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(cancellation.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RunCancelled)

    def test_commit_validation_obeys_deadline_and_late_result_never_commits(self):
        run = isolated_run(total_seconds=.25)
        entered, release, check_exited, finished = Event(), Event(), Event(), Event()
        errors, commits = [], []

        def evidence_check():
            entered.set()
            try:
                release.wait(3)
            finally:
                check_exited.set()

        def complete():
            try:
                run.complete(commit=lambda: commits.append('committed'))
            except BaseException as exc:
                errors.append(exc)
            finally:
                finished.set()

        run.add_commit_check(evidence_check)
        worker = Thread(target=complete)
        worker.start()
        try:
            self.assertTrue(entered.wait(1), "Commit validation did not start")
            self.assertTrue(finished.wait(1), "Commit waited for evidence I/O past its deadline")
            self.assertFalse(check_exited.is_set(), "Evidence operation unexpectedly finished early")
            self.assertEqual(commits, [])
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], (DeadlineExceeded, CallTimeout))
            self.assertEqual(run.status, 'timed_out')
        finally:
            release.set()
            worker.join(2)
        self.assertTrue(check_exited.wait(1), "Late evidence operation did not exit")
        self.assertFalse(worker.is_alive())
        self.assertEqual(commits, [], "A late validation result committed the answer")
        self.assertEqual(run.status, 'timed_out')


if __name__ == '__main__':
    unittest.main()
