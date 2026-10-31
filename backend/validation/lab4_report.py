"""Run the Lab 4 test cases and write their results tables into LAB4-TESTING.md.

Usage, from backend/: python validation/lab4_report.py
"""
from datetime import datetime
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE)); sys.path.insert(0,str(HERE.parent))
from pricing import _tier_price, window_at  # noqa: E402
from test_lab4_basis_path import TIER_CASES, WINDOW_CASES  # noqa: E402
from test_lab4_score_candidate import BV_CASES, EC_CASES, NOMINAL, actual, matches  # noqa: E402

DOC=HERE/'LAB4-TESTING.md'


def changed(kwargs):
    diff={k:v for k,v in kwargs.items() if NOMINAL.get(k,'absent')!=v or type(NOMINAL.get(k)) is not type(v)}
    return 'nominal' if not diff else ', '.join(f'{k}={v!r}' for k,v in diff.items())


def show(value):
    if isinstance(value,tuple) and value and isinstance(value[0],datetime):
        return ' to '.join(v.strftime('%a %H:%M') for v in value)
    if isinstance(value,tuple):
        return f'{value[0]} ({value[1]})'
    return 'None' if value is None else str(value)


def score_table(cases):
    rows=['| ID | Class or boundary | Test input (changes from nominal) | Expected output | Actual output | Result |',
          '|---|---|---|---|---|---|']
    for cid,label,kwargs,expected in cases:
        got=actual(kwargs)
        shown=got if expected==got or got=='ValueError' or isinstance(expected,tuple) else got[0]
        rows.append(f'| {cid} | {label} | `{changed(kwargs)}` | {show(expected)} | {show(shown)} | '
                    f'{"Pass" if matches(expected,got) else "FAIL"} |')
    return '\n'.join(rows)


def path_table(cases, function, describe):
    rows=['| ID | Path | Test input | Expected output | Actual output | Result |','|---|---|---|---|---|---|']
    for cid,path,args,expected in cases:
        got=function(*args)
        rows.append(f'| {cid} | {path} | {describe(args)} | {show(expected)} | {show(got)} | '
                    f'{"Pass" if got==expected else "FAIL"} |')
    return '\n'.join(rows)


def describe_window(args):
    rule,instant,_=args
    extra=f", {rule['calculation']}" if rule['calculation'] else ''
    return f"{rule['day_type']} {rule['start_time']}-{rule['end_time']}{extra}; at {instant:%a %H:%M}"


def describe_tiers(args):
    rule,minutes,first=args
    calc=rule['calculation']
    tiers=[f"{t['duration_minutes']}m@{t['amount_cents']}c/{t['unit_minutes']}m" for t in calc.get('tiers',[])]
    parts=[f"tiers [{', '.join(tiers)}]"]
    if calc.get('first_entry_required'): parts.append('first entry required')
    if 'repeat_entry_tiers' in calc: parts.append('repeat tier 60m@200c/60m')
    return f"{'; '.join(parts)}; {minutes} min; first_entry={first}"


def replace(text, name, table):
    pattern=re.compile(rf'(<!-- {name}:start -->\n).*?(<!-- {name}:end -->)',re.S)
    assert pattern.search(text),name
    return pattern.sub(lambda m:m.group(1)+table+'\n'+m.group(2),text)


if __name__=='__main__':
    text=DOC.read_text(encoding='utf-8')
    text=replace(text,'ec',score_table(EC_CASES))
    text=replace(text,'bv',score_table(BV_CASES))
    text=replace(text,'wa',path_table(WINDOW_CASES,window_at,describe_window))
    text=replace(text,'tp',path_table(TIER_CASES,_tier_price,describe_tiers))
    DOC.write_text(text,encoding='utf-8')
    print(f'Updated {DOC}')
