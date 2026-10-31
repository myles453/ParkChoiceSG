"""Run the documented offline cases and verify the two control-flow graphs.

Run with the backend Python environment: python lab4/collect_evidence.py.
No live API, database write, retraining or device interaction is performed.
"""
from pathlib import Path
import ast
from datetime import datetime, timezone
import hashlib
import inspect
import io
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'backend'))
sys.path.insert(0, str(ROOT/'backend/validation'))
from test_lab4_controller import CASES, execute
from test_lab4_request_boundaries import REQUEST_CASES
from test_lab4_score_candidate import EC_CASES, BV_CASES, actual, matches
from test_lab4_basis_path import WINDOW_CASES, TIER_CASES
from lab4_report import changed, describe_tiers, describe_window, show
from pricing import window_at, _tier_price
from recommendation import TripRequest
import test_workflow as fixtures


def rows():
    result = []
    for cid, description, inputs, status, ranked, fallback in CASES:
        response = execute(inputs)
        expected = (status, ranked, fallback)
        observed = (response['status'], len(response['ranked']), len(response['fallback_ranked']))
        result.append(dict(id=cid, technique='Control class equivalence / probability boundary',
                           target='RecommendationController.recommend', purpose=description,
                           inputs=repr(inputs) if inputs else 'valid forecast fixture',
                           expected=str(expected), actual=str(observed), passed=expected == observed))
    for cid, field, value, accepted in REQUEST_CASES:
        inputs = dict(origin=fixtures.POINT, destination=fixtures.POINT, duration_minutes=60)
        inputs[field] = value
        try:
            TripRequest(**inputs)
            observed = 'accepted'
        except ValueError:
            observed = 'ValueError'
        expected = 'accepted' if accepted else 'ValueError'
        result.append(dict(id=cid, technique='Request boundary value', target='TripRequest',
                           purpose=field, inputs=f'{field}={value}; other fields nominal',
                           expected=expected, actual=observed, passed=expected == observed))
    for technique, cases in [('Scoring equivalence class', EC_CASES), ('Scoring boundary value', BV_CASES)]:
        for cid, description, inputs, expected in cases:
            observed = actual(inputs)
            display = observed if isinstance(expected, tuple) or observed == 'ValueError' else observed[0]
            result.append(dict(id=cid, technique=technique, target='score_candidate', purpose=description,
                               inputs=changed(inputs), expected=show(expected), actual=show(display),
                               passed=matches(expected, observed)))
    for function, cases, describe in [(window_at, WINDOW_CASES, describe_window),
                                       (_tier_price, TIER_CASES, describe_tiers)]:
        for cid, path, args, expected in cases:
            observed = function(*args)
            result.append(dict(id=cid, technique='Basis path' if '-P' in cid else 'Additional condition',
                               target=function.__name__, purpose=path.split(' (', 1)[-1].rstrip(')'),
                               path=path.split(' (', 1)[0], inputs=describe(args), expected=show(expected),
                               actual=show(observed), passed=expected == observed))
    return result


WINDOW_EDGES = [('1','2'),('2','3'),('2','4'),('4','5'),('4','13'),('5','6'),
                ('6','7'),('6','8'),('7','8'),('8','4'),('8','9'),('9','4'),
                ('9','10'),('10','4'),('10','11'),('11','4'),('11','12'),
                ('3','X'),('12','X'),('13','X')]
TIER_EDGES = [('1','2'),('2','3'),('2','9'),('3','4'),('3','5'),('5','6'),
              ('5','9'),('6','7'),('7','8'),('7','9'),('9','10'),('10','11'),
              ('10','13'),('11','12'),('11','10'),('12','10'),('13','14'),
              ('13','15'),('14','15'),('4','X'),('8','X'),('15','X')]


def node_mapping(function):
    source, first = inspect.getsourcelines(function)
    tree = ast.parse(''.join(source)).body[0]
    mapping = {}

    def mark(statement, number):
        for line in range(statement.lineno, statement.end_lineno+1):
            mapping[first+line-1] = str(number)

    body = tree.body
    if function.__name__ == 'window_at':
        # Skip its descriptive docstring.
        body = body[1:]
        for stmt, number in zip(body, [1, 1, 2, 4, 13]): mark(stmt, number)
        mark(body[2].body[0], 3)
        loop = body[3].body
        for stmt, number in zip(loop, [5,5,6,8,9,9,10,10,11,11,12]): mark(stmt, number)
        mark(loop[2].body[0], 7)
    else:
        for stmt, number in zip(body, [1,1,2,9,10,13,15]): mark(stmt, number)
        entry = body[2].body
        mark(entry[0], 3); mark(entry[0].body[0], 4)
        mark(entry[1], 5); mark(entry[1].body[0], 6)
        mark(entry[1].body[1], 7); mark(entry[1].body[1].body[0], 8)
        for stmt in body[4].body: mark(stmt, 11)
        for stmt in body[4].body[1].body: mark(stmt, 12)
        mark(body[5].body[0], 14)
    return mapping, tree


def traced_nodes(function, args, mapping):
    nodes = []
    def tracer(frame, event, arg):
        if frame.f_code is function.__code__ and event == 'line':
            node = mapping.get(frame.f_lineno)
            if node and (not nodes or nodes[-1] != node): nodes.append(node)
        return tracer
    previous = sys.gettrace()
    try:
        sys.settrace(tracer)
        function(*args)
    finally:
        sys.settrace(previous)
    return nodes+['X']


def binary_rank(vectors):
    pivots = {}
    for vector in vectors:
        while vector:
            pivot = vector.bit_length()-1
            if pivot not in pivots:
                pivots[pivot] = vector
                break
            vector ^= pivots[pivot]
    return len(pivots)


def verify_graph(function, cases, edges):
    mapping, tree = node_mapping(function)
    checked, vectors = [], []
    for cid, description, args, _ in cases:
        declared = re.findall(r'\d+', description.split(' (', 1)[0])+['X']
        observed = traced_nodes(function, args, mapping)
        checked.append(dict(id=cid, declared=declared, observed=observed, matches=declared == observed))
        traversed = list(zip(observed, observed[1:]))
        if any(edge not in edges for edge in traversed):
            raise AssertionError(f'{cid}: actual trace contains an undeclared graph edge')
        if '-P' in cid:
            vectors.append(sum(1 << i for i, edge in enumerate(edges) if traversed.count(edge) % 2))
    nodes = set(n for edge in edges for n in edge)
    decisions = sum(isinstance(n, (ast.If, ast.For, ast.While)) for n in ast.walk(tree))
    return dict(function=function.__name__, nodes=len(nodes), edges=len(edges),
                complexity_edges=len(edges)-len(nodes)+2, complexity_decisions=decisions+1,
                compound_condition_convention='one decision per if/for/while; Boolean operands are not separate nodes',
                basis_path_count=len(vectors), independent_rank=binary_rank(vectors),
                traces=checked, graph_edges=edges)


def main():
    evidence = HERE/'evidence'
    evidence.mkdir(exist_ok=True)
    results = rows()
    graphs = [verify_graph(window_at, WINDOW_CASES, WINDOW_EDGES),
              verify_graph(_tier_price, TIER_CASES, TIER_EDGES)]
    # A basis set is not automatically condition coverage: retain the equal-time full-day case.
    source = inspect.getsource(window_at).replace('if closing <= opening:', 'if closing < opening:')
    namespace = dict(window_at.__globals__)
    exec(compile(source, '<targeted-window-mutant>', 'exec'), namespace)
    mutant = namespace['window_at']
    killed = [cid for cid, _, args, expected in WINDOW_CASES if mutant(*args) != expected]
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT/'backend/validation'), pattern='test_*.py')
    run = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    source_files = [*ROOT.joinpath('backend').glob('*.py'),
                    *ROOT.joinpath('backend/validation').glob('test_*.py'),
                    ROOT/'data-pipeline/provider_puller.py']
    report = dict(date='2026-10-26', executed_at_utc=datetime.now(timezone.utc).isoformat(),
                  source_state='origin/main 790ac78 plus reconciled local ranking/frontend work and Lab 4 additions',
                  python=sys.version.split()[0], documented_cases=len(results),
                  documented_passed=sum(r['passed'] for r in results), rows=results, control_flow=graphs,
                  targeted_mutation=dict(change='window closing <= opening changed to <', killed_by=killed),
                  regression=dict(methods=run.testsRun, failures=len(run.failures), errors=len(run.errors),
                                  skipped=len(run.skipped), passed=run.wasSuccessful()),
                  source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in source_files},
                  limits=['Controlled fixtures, not real-provider accuracy or on-phone verification.',
                          'Unittest methods and documented parameter cases are different counts.'])
    text = stream.getvalue().replace(str(ROOT), '<workspace>')
    (evidence/'backend-unittest.log').write_text(text, encoding='utf-8')
    (evidence/'test-results.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    valid = (all(r['passed'] for r in results) and run.wasSuccessful()
             and all(g['complexity_edges'] == g['complexity_decisions'] == g['independent_rank'] == 8
                     and all(t['matches'] for t in g['traces']) for g in graphs)
             and killed == ['WA-C1'])
    print(json.dumps(dict(documented_cases=len(results), passed=report['documented_passed'],
                         regression=report['regression'], graph_verification=valid, mutation_killed_by=killed), indent=2))
    if not valid: raise SystemExit(1)


if __name__ == '__main__':
    main()
