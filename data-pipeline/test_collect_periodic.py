import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import collect_periodic as periodic


class PeriodicCollectionTests(unittest.TestCase):
    def test_rejects_zero_negative_and_nonfinite_intervals(self):
        for value in ('0', '-5', 'nan', 'inf', '-inf'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                periodic.positive_number(value)

    def test_cadence_skips_missed_slots_without_a_burst(self):
        self.assertEqual(periodic.next_slot(0, 120, 300), 300)
        self.assertEqual(periodic.next_slot(0, 350, 300), 600)
        self.assertEqual(periodic.next_slot(0, 650, 300), 900)
        self.assertEqual(periodic.next_slot(0, 600, 300), 600)

    def test_provider_timeout_and_failure_do_not_skip_other_providers(self):
        commands = []
        def execute(command, **kwargs):
            commands.append(command)
            if len(commands) == 1:
                raise subprocess.TimeoutExpired(command, 180)
            if len(commands) == 2:
                kwargs['stdout'].write(json.dumps({'run_id':'00000000-0000-0000-0000-000000000001',
                    'status':'loaded','accepted':40}).encode())
                return SimpleNamespace(returncode=0)
            return SimpleNamespace(returncode=1)
        with tempfile.TemporaryDirectory() as folder:
            with patch('collect_periodic.subprocess.run', side_effect=execute), redirect_stdout(io.StringIO()):
                audit = io.StringIO()
                outcomes = periodic.collect_cycle(periodic.PROVIDERS, False, 180, Path(folder), 1, audit)
            self.assertEqual([r['status'] for r in outcomes], ['timed_out','success','failed'])
            self.assertEqual(outcomes[1]['capture_status'], 'loaded')
            self.assertEqual(outcomes[1]['accepted'], 40)
            self.assertEqual(len(commands), 3)
            self.assertTrue(all('--load' in command for command in commands))
            self.assertTrue(all('--include-rates' not in command for command in commands))

    def test_archive_mode_never_requests_database_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('collect_periodic.subprocess.run', return_value=SimpleNamespace(returncode=0)) as execute:
                with redirect_stdout(io.StringIO()):
                    periodic.collect_cycle(['hdb'], True, 180, Path(folder), 1, io.StringIO())
                self.assertNotIn('--load', execute.call_args.args[0])

    def test_slow_cycles_are_serial_and_keep_the_configured_schedule(self):
        clock = SimpleNamespace(now=0)
        starts = []
        def cycle(*args):
            starts.append(clock.now)
            clock.now += 350
            return [{'provider':'hdb','status':'success'}]
        def sleep(seconds):
            clock.now += seconds
        args = SimpleNamespace(interval_minutes=5, providers=['hdb'], archive_only=False,
                               provider_timeout_seconds=180, cycles=2)
        with tempfile.TemporaryDirectory() as folder:
            with patch('collect_periodic.time.monotonic', side_effect=lambda: clock.now), \
                 patch('collect_periodic.time.sleep', side_effect=sleep), \
                 patch('collect_periodic.collect_cycle', side_effect=cycle), redirect_stdout(io.StringIO()):
                self.assertEqual(periodic.run(args, Path(folder)), 0)
            events = [json.loads(line) for line in (Path(folder)/'events.jsonl').read_text().splitlines()]
            self.assertEqual(starts, [0,600])
            self.assertEqual(next(e for e in events if e['event']=='next_cycle')['skipped_slots'], 1)

    def test_second_process_cannot_collect_until_lock_is_released(self):
        code = 'from pathlib import Path\nimport sys\nfrom collect_periodic import collector_lock\nwith collector_lock(Path(sys.argv[1])): pass'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'collector.lock'
            with periodic.collector_lock(path):
                blocked = subprocess.run([sys.executable,'-c',code,str(path)], cwd=periodic.BASE,
                                         capture_output=True, timeout=10)
            allowed = subprocess.run([sys.executable,'-c',code,str(path)], cwd=periodic.BASE,
                                     capture_output=True, timeout=10)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn(b'already running', blocked.stderr)
        self.assertEqual(allowed.returncode, 0)


if __name__ == '__main__':
    unittest.main()
