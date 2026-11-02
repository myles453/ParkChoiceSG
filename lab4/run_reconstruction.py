"""Replay the final reconstruction in an isolated, credential-free source copy.

The first failed generated attempt is preserved as historical evidence; replay
tests the saved final replacement and never edits the working controller.
"""
from pathlib import Path
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent


def main():
    (HERE/'tmp').mkdir(exist_ok=True)
    production = ROOT/'backend/recommendation.py'
    before = hashlib.sha256(production.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='replay-', dir=HERE/'tmp') as temporary:
        sandbox = Path(temporary)
        for folder in ('backend','data-pipeline'):
            for path in (ROOT/folder).rglob('*'):
                if not path.is_file() or path.suffix not in {'.py','.json'}:
                    continue
                if any(p in {'data','.venv','__pycache__','.pytest_cache'} for p in path.relative_to(ROOT/folder).parts):
                    continue
                target = sandbox/path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        frozen = HERE/'ai-exercises/frozen_controller_tests.py'
        shutil.copy2(frozen, sandbox/'backend/validation/test_lab4_controller.py')
        target = sandbox/'backend/recommendation.py'
        source = target.read_text()
        node = next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef)
                    and n.name == 'RecommendationController')
        lines = source.splitlines(keepends=True)
        missing = ''.join(lines[:node.lineno-1])+''.join(lines[node.end_lineno:])
        target.write_text(missing, encoding='utf-8')
        command = [sys.executable,'-m','unittest','discover','-s','backend/validation','-p']
        red = subprocess.run(command+['test_lab4_controller.py','-q'],cwd=sandbox,capture_output=True,text=True)
        generated = (HERE/'ai-exercises/reconstructed_controller.py').read_text()
        generated = generated[generated.index('class RecommendationController:'):]
        target.write_text(missing.replace('def recommend(request: TripRequest, router: RoutingProvider,',
                                          generated+'\n\n\ndef recommend(request: TripRequest, router: RoutingProvider,',1),
                          encoding='utf-8')
        green = subprocess.run(command+['test_*.py','-q'],cwd=sandbox,capture_output=True,text=True)
        record = dict(date='2026-10-26', missing_class_returncode=red.returncode,
                      regenerated_returncode=green.returncode,
                      frozen_test_sha256=hashlib.sha256(frozen.read_bytes()).hexdigest(),
                      working_source_unchanged=before==hashlib.sha256(production.read_bytes()).hexdigest(),
                      red_output=(red.stdout+red.stderr).replace(str(sandbox),'<sandbox>'),
                      green_output=(green.stdout+green.stderr).replace(str(sandbox),'<sandbox>'))
        (HERE/'evidence/reconstruction-replay.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if not k.endswith('_output')},indent=2))
    if red.returncode == 0 or green.returncode != 0 or not record['working_source_unchanged']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
