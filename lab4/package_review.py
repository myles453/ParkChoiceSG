"""Package the current source and built debug APK, excluding private/generated data."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parent.parent
HERE=Path(__file__).resolve().parent
OUT=HERE/'submission'


def include(path):
    parts=path.relative_to(ROOT).parts
    if any(p in {'data','.venv','__pycache__','.pytest_cache','tmp','build','.dart_tool',
                 '.gradle','.cxx','.externalNativeBuild','.idea','.git','node_modules','submission'} for p in parts):
        return False
    if path.name.startswith('.env') and path.name!='.env.example': return False
    if path.name in {'local.properties','key.properties','GeneratedPluginRegistrant.java',
                     '.flutter-plugins-dependencies','.flutter-plugins','.packages'}: return False
    if path.suffix in {'.pyc','.pyo','.log','.zip','.apk','.jks','.keystore','.iml'}: return False
    return True


def private_values():
    values=[]
    for path in (ROOT/'backend/.env', ROOT/'data-pipeline/.env'):
        if not path.exists(): continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.lstrip().startswith('#'): continue
            key,separator,value=line.partition('=')
            value=value.strip().strip('"').strip("'")
            if separator and len(value)>=8 and key.strip()!='PARKCHOICE_MODEL_URL':
                values.append(value.encode())
    return values


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    platform=json.loads((HERE/'evidence/platform-checks.json').read_text())
    expected_apk=platform['android_build']['sha256']
    built=ROOT/'parkchoice_flutter/build/app/outputs/flutter-apk/app-debug.apk'
    apk=OUT/'ParkChoiceSG-debug-arm64.apk'
    # Do not silently package a stale APK left by a different checkout/build.
    if not built.exists() or sha(built)!=expected_apk:
        if apk.exists() and sha(apk)==expected_apk:
            built=apk
        else:
            raise SystemExit('No APK matches the recorded build. Rebuild and verify it before packaging.')
    for name, expected in platform['android_build'].get('source_sha256',{}).items():
        current=hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if current!=expected:
            raise SystemExit('Android source changed since the verified build: '+name)
    archive=OUT/'ParkChoiceSG-Lab4-Source.zip'
    values=private_values()
    sources=[]
    for folder in ('backend','data-pipeline','ml','parkchoice_flutter','lab4'):
        sources += [p for p in (ROOT/folder).rglob('*') if p.is_file() and include(p)]
    sources += [ROOT/'README.md',ROOT/'.gitignore']
    matches=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
        for path in sorted(set(sources)):
            data=path.read_bytes()
            if any(value in data for value in values): matches.append(str(path.relative_to(ROOT)))
            output.writestr('ParkChoiceSG/'+str(path.relative_to(ROOT)).replace('\\','/'),data)
    if matches:
        archive.unlink()
        raise RuntimeError('Private configuration matched in source files; archive withheld: '+repr(matches))
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        assert not any(Path(name).name=='.env' for name in check.namelist())
    if built.resolve()!=apk.resolve(): shutil.copy2(built,apk)
    manifest={'date':'2026-10-26','source_files':len(set(sources)),
              'source_zip':{'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive)},
              'android_apk':{'file':apk.name,'bytes':apk.stat().st_size,'sha256':sha(apk),
                             'abi':'arm64-v8a','build_type':'debug',
                             'api_url':'http://127.0.0.1:8000','requires_usb_reverse':True,
                             'physical_device_acceptance':'pending'},
              'pdfs':[{ 'file':str(p.relative_to(HERE)).replace('\\','/'),'sha256':sha(p)}
                      for p in sorted((HERE/'output/pdf').glob('*.pdf'))],
              'private_value_matches':0,'database_modified':False,
              'publication':'local review package; not committed or pushed by this script'}
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    main()
