"""Collect training observations periodically; default start interval: five minutes.

Runs in the foreground until Ctrl+C, or for --cycles N. Uses the existing
provider cleaners/loaders. Pricing capture is separate from this training loop.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from provider_puller import load_local_env

BASE = Path(__file__).resolve().parent
DEFAULT_INTERVAL_MINUTES = 5.0
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 180.0
PROVIDERS = ('hdb', 'lta', 'ura')


def positive_number(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('Use a finite number greater than zero')
    return number


def positive_integer(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('Use a whole number greater than zero')
    return number


def next_slot(scheduled, finished, interval):
    """Keep start-to-start cadence, skipping expired slots without catch-up bursts."""
    following = scheduled + interval
    if following < finished:
        following += math.ceil((finished - following) / interval) * interval
    return following


@contextmanager
def collector_lock(path):
    """OS releases the lock on exit/crash; the leftover file is harmless."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another periodic collector is already running in this workspace') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def event(stream, name, **fields):
    item = {'at': datetime.now(timezone.utc).isoformat(), 'event': name, **fields}
    stream.write(json.dumps(item) + '\n')
    stream.flush()


def capture_summary(log_path):
    """Copy only known public capture fields into the session audit log."""
    text = log_path.read_text(encoding='utf-8', errors='replace')
    try:
        manifest, _ = json.JSONDecoder().raw_decode(text[text.index('{'):])
        uuid.UUID(manifest['run_id'])
        return {field: manifest[field] for field in (
            'run_id', 'status', 'retrieved_at', 'accepted', 'rejected', 'trainable_car_rows'
        ) if field in manifest}
    except (ValueError, KeyError, TypeError):
        return {}


def collect_cycle(providers, archive_only, timeout_seconds, session, cycle, audit):
    results = []
    for provider in providers:
        command = [sys.executable, str(BASE / 'puller.py')] if provider == 'hdb' else [
            sys.executable, str(BASE / 'provider_puller.py'), '--provider', provider]
        if not archive_only:
            command.append('--load')
        # Absolute output path and cwd make invocation from any directory safe.
        command.extend(['--output', str(BASE / 'data')])
        log_path = session / f'cycle-{cycle:05d}-{provider}.log'
        event(audit, 'provider_started', cycle=cycle, provider=provider, log=log_path.name)
        print(f'Cycle {cycle}: collecting {provider.upper()}...', flush=True)
        began = time.monotonic()
        try:
            with log_path.open('wb') as log:
                result = subprocess.run(command, cwd=BASE, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=timeout_seconds, check=False)
            status = 'success' if result.returncode == 0 else 'failed'
            details = {'returncode': result.returncode, **capture_summary(log_path)}
            # Keep execution outcome separate from the provider manifest status.
            if 'status' in details:
                details['capture_status'] = details.pop('status')
        except subprocess.TimeoutExpired:
            status, details = 'timed_out', {}
        except OSError as exc:
            status, details = 'failed', {'error_type': type(exc).__name__}
        outcome = {'provider': provider, 'status': status,
                   'elapsed_seconds': round(time.monotonic() - began, 3),
                   'log': log_path.name, **details}
        event(audit, 'provider_finished', cycle=cycle, **outcome)
        results.append(outcome)
        print(f'Cycle {cycle}: {provider.upper()} {status}; log: {log_path.name}', flush=True)
    return results


def run(args, session):
    interval = args.interval_minutes * 60
    failures = 0
    cycle = 0
    due = time.monotonic()
    with (session / 'events.jsonl').open('a', encoding='utf-8') as audit:
        event(audit, 'session_started', pid=os.getpid(), interval_minutes=args.interval_minutes,
              providers=args.providers, archive_only=args.archive_only,
              provider_timeout_seconds=args.provider_timeout_seconds, max_cycles=args.cycles)
        try:
            while args.cycles is None or cycle < args.cycles:
                delay = due - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                cycle += 1
                event(audit, 'cycle_started', cycle=cycle)
                results = collect_cycle(args.providers, args.archive_only,
                                        args.provider_timeout_seconds, session, cycle, audit)
                failures += sum(result['status'] != 'success' for result in results)
                event(audit, 'cycle_finished', cycle=cycle, failed_providers=[
                    result['provider'] for result in results if result['status'] != 'success'])
                if args.cycles is not None and cycle >= args.cycles:
                    break
                following = next_slot(due, time.monotonic(), interval)
                skipped = max(0, round((following - due) / interval) - 1)
                due = following
                next_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, due-time.monotonic()))
                event(audit, 'next_cycle', next_at=next_at.isoformat(), skipped_slots=skipped)
                print(f'Next cycle: {next_at.isoformat()} (skipped slots: {skipped}). Ctrl+C to stop.', flush=True)
        except KeyboardInterrupt:
            event(audit, 'session_stopped', reason='keyboard_interrupt', cycles_started=cycle)
            print('\nCollector stopped. Completed captures are preserved.', flush=True)
            return 130
        event(audit, 'session_stopped', reason='cycle_limit', cycles_started=cycle,
              failed_provider_attempts=failures)
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interval-minutes', type=positive_number, default=DEFAULT_INTERVAL_MINUTES)
    parser.add_argument('--providers', nargs='+', choices=PROVIDERS, default=list(PROVIDERS))
    parser.add_argument('--cycles', type=positive_integer, help='Stop after N cycles; default: continue until Ctrl+C')
    parser.add_argument('--provider-timeout-seconds', type=positive_number,
                        default=DEFAULT_PROVIDER_TIMEOUT_SECONDS)
    parser.add_argument('--archive-only', action='store_true', help='Save cleaned local captures without database writes')
    args = parser.parse_args()
    args.providers = list(dict.fromkeys(args.providers))
    try:
        load_local_env(BASE / '.env')
    except ValueError as exc:
        parser.error(str(exc))
    required = ([] if args.archive_only else ['DATABASE_URL'])
    required += ['LTA_ACCOUNT_KEY'] if 'lta' in args.providers else []
    required += ['URA_ACCESS_KEY'] if 'ura' in args.providers else []
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        parser.error('Missing configuration: ' + ', '.join(missing))
    collection_root = BASE / 'data' / 'collection'
    try:
        with collector_lock(collection_root / 'collector.lock'):
            session = collection_root / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
            session.mkdir()
            print(f'Interval: {args.interval_minutes:g} minutes. First cycle starts now.\nSession logs: {session}', flush=True)
            code = run(args, session)
    except RuntimeError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        code = 130
    raise SystemExit(code)


if __name__ == '__main__':
    main()
