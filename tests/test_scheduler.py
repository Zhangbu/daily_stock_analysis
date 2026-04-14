# -*- coding: utf-8 -*-
"""Tests for scheduler daily/interval mode."""

import unittest
from unittest.mock import Mock, patch

from src.scheduler import Scheduler, run_with_schedule


class _FakeJob:
    def __init__(self, owner):
        self.owner = owner

    @property
    def day(self):
        return self

    def at(self, when):
        self.owner.at_time = when
        return self

    @property
    def minutes(self):
        return self

    def do(self, fn):
        self.owner.job_fn = fn
        return self


class _FakeSchedule:
    def __init__(self):
        self.last_interval = None
        self.at_time = None
        self.job_fn = None

    def every(self, interval=None):
        self.last_interval = interval
        return _FakeJob(self)


class SchedulerModeTestCase(unittest.TestCase):
    def test_set_interval_task_registers_minutes_job(self):
        scheduler = Scheduler.__new__(Scheduler)
        scheduler.schedule = _FakeSchedule()
        scheduler._task_callback = None

        scheduler.set_interval_task(lambda: None, interval_minutes=15, run_immediately=False)

        self.assertEqual(scheduler.schedule.last_interval, 15)
        self.assertIsNotNone(scheduler.schedule.job_fn)

    def test_set_daily_task_registers_daily_job(self):
        scheduler = Scheduler.__new__(Scheduler)
        scheduler.schedule = _FakeSchedule()
        scheduler._task_callback = None
        scheduler.schedule_time = "18:00"

        scheduler.set_daily_task(lambda: None, run_immediately=False)

        self.assertEqual(scheduler.schedule.at_time, "18:00")
        self.assertIsNotNone(scheduler.schedule.job_fn)

    @patch("src.scheduler.Scheduler")
    def test_run_with_schedule_uses_interval_branch(self, scheduler_cls: Mock):
        scheduler = scheduler_cls.return_value

        run_with_schedule(lambda: None, schedule_time="18:00", interval_minutes=30, run_immediately=False)

        scheduler.set_interval_task.assert_called_once()
        scheduler.set_daily_task.assert_not_called()
        scheduler.run.assert_called_once()

    @patch("src.scheduler.Scheduler")
    def test_run_with_schedule_uses_daily_branch_when_interval_disabled(self, scheduler_cls: Mock):
        scheduler = scheduler_cls.return_value

        run_with_schedule(lambda: None, schedule_time="18:00", interval_minutes=0, run_immediately=False)

        scheduler.set_daily_task.assert_called_once()
        scheduler.set_interval_task.assert_not_called()
        scheduler.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
