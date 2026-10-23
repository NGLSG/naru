"""Clause-tagged C11 acceptance cases. Passing this corpus is not certification."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from native_process import execute
from frozen_snapshot import validate_frozen
from rule_dependencies import c11_rule_inputs
import c11_reference_headers

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'tests/c11/conformance.json'
SUPPORT_PLAN = ROOT / 'tests/c11/support-plan.json'

def fingerprints(compiler: Path, probe_manifest: Path | None = None) -> dict[str, str]:
    paths = [MANIFEST, SUPPORT_PLAN, Path(__file__).resolve(), ROOT/'target/naru_mlir_backend.dll',
             ROOT/'tests/c11_reference_headers.py', ROOT/'tests/native_process.py', *c11_rule_inputs()]
    if probe_manifest: paths.append(probe_manifest)
    result = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    result['compiler:'+str(compiler)] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    backend = compiler.parent/'naru_mlir_backend.dll'
    if backend.is_file(): result['backend:'+str(backend)] = hashlib.sha256(backend.read_bytes()).hexdigest()
    for path in sorted((compiler.parent/'runtime/clang').rglob('*')):
        if path.is_file(): result['resource-header:'+str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--feature', action='append')
    parser.add_argument('--case', action='append')
    parser.add_argument('--opt', action='append', choices=['0','2'])
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--probe-manifest', type=Path, help='Explicit failing baseline; missing support remains a failure')
    parser.add_argument('--report', type=Path, default=ROOT/'target/c11-conformance.json')
    args = parser.parse_args(argv)
    if args.probe_manifest:
        args.probe_manifest = args.probe_manifest.resolve()
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    plan = json.loads(SUPPORT_PLAN.read_text(encoding='utf-8'))
    corpus = json.loads(args.probe_manifest.read_text(encoding='utf-8')) if args.probe_manifest else manifest
    known_features = {f['id'] for f in manifest['features']}
    known_cases = {c['id'] for c in corpus['cases']}
    if plan['target'] != manifest['target']: parser.error('Support plan and corpus targets differ')
    if corpus['target'] != manifest['target']: parser.error('Probe and corpus targets differ')
    items = [item for phase in plan['phases'] for item in phase['work_items']]
    if len({item['id'] for item in items}) != len(items): parser.error('Duplicate support work item')
    if any(set(item['features'])-known_features for item in items): parser.error('Unknown support-plan feature')
    if any(c['feature'] not in known_features for c in corpus['cases']): parser.error('Unknown case feature')
    if len(known_cases) != len(corpus['cases']): parser.error('Duplicate acceptance case')
    if any(c.get('work_item') not in {item['id'] for item in items} for c in corpus['cases'] if 'work_item' in c):
        parser.error('Unknown case support work item')
    if any(c.get('reference_header_policy') not in (None, 'target-crt') for c in corpus['cases']):
        parser.error('Unknown independent reference header policy')
    if any(('reference_source' in c or c.get('reference_additional_sources')) and not c.get('reference_note') for c in corpus['cases']):
        parser.error('Independent reference source variants must state their contract')
    for case in corpus['cases']:
        environment = case.get('translation_environment', {})
        if not isinstance(environment, dict) or any(not isinstance(k, str) or not k or '=' in k or '\0' in k
                or k.upper() == 'PATH' or not isinstance(v, str) or '\0' in v for k, v in environment.items()):
            parser.error('Invalid translation environment (PATH cannot be overridden)')
    if args.feature and set(args.feature)-known_features: parser.error('Unknown feature')
    if args.case and set(args.case)-known_cases: parser.error('Unknown case')
    cases = [c for c in corpus['cases'] if (not args.feature or c['feature'] in args.feature)
             and (not args.case or c['id'] in args.case)]
    if not cases: parser.error('Selected feature has no acceptance cases yet')
    reference = args.reference or shutil.which('clang.exe')
    if not reference: parser.error('A reference Clang is required')
    compiler = args.compiler.resolve()
    frozen = validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx']) if args.frozen else None
    before = fingerprints(compiler,args.probe_manifest)
    results = []
    with tempfile.TemporaryDirectory(prefix='naru C11 conformance ') as directory:
        work = Path(directory)
        rules = [] if args.frozen else ['--rules', str(ROOT/'dialects/c11.stx')]
        reference_header_flags, reference_header_view = [], {}
        if any(case.get('reference_header_policy') == 'target-crt' for case in cases):
            policy = c11_reference_headers.discover(compiler, rules, ROOT)
            reference_header_flags, reference_header_view = c11_reference_headers.reference_view(work, policy)
        common = ([] if args.frozen else ['--rules',str(ROOT/'dialects/c11.stx')])+[
            '--frontend','c11.frontend','--entry','c11.item','--unit','program',
            '--relation','c11.emit_program','--runtime','crt-static',
            '--rule-depth','1024','--rule-budget','100000000','--parse-budget','100000000']
        for case in cases:
            translation_environment = dict(os.environ)
            # Windows environment names are case insensitive. Avoid duplicate
            # spellings when the fixture replaces an inherited variable.
            for key, value in case.get('translation_environment', {}).items():
                translation_environment = {k: v for k, v in translation_environment.items() if k.upper() != key.upper()}
                translation_environment[key] = value
            compiler_environment = {k: v for k, v in translation_environment.items() if k.upper() != 'PATH'}
            compiler_environment['PATH'] = ''
            case_directory = work/case['id']
            case_directory.mkdir()
            path = case_directory/'main.c'
            path.write_text(case['source']+'\n', encoding='utf-8')
            for name, content in case.get('files', {}).items():
                extra = (case_directory/name).resolve()
                if not extra.is_relative_to(case_directory) or extra == path.resolve():
                    parser.error('Invalid case input file: '+name)
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_text(content+'\n', encoding='utf-8')
            include_directories = [(case_directory/name).resolve() for name in case.get('include_directories', [])]
            if any(not directory.is_relative_to(case_directory) or not directory.is_dir() for directory in include_directories):
                parser.error('Invalid case include directory')
            reference_includes = [argument for directory in include_directories for argument in ['-I',str(directory)]]
            if case.get('reference_header_policy') == 'target-crt':
                reference_includes.extend(reference_header_flags)
            case_common = common + (['--frontend-option','include_paths='+'|'.join(map(str,include_directories))] if include_directories else [])
            sources = [path]
            for name, source in case.get('additional_sources', {}).items():
                additional = (case_directory/name).resolve()
                if not additional.is_relative_to(case_directory) or additional == path.resolve():
                    parser.error('Invalid additional translation unit: '+name)
                additional.parent.mkdir(parents=True, exist_ok=True)
                additional.write_text(source+'\n', encoding='utf-8')
                sources.append(additional)
            reference_sources = list(sources)
            reference_hashes = {}
            if 'reference_source' in case:
                if not case.get('reference_note'):
                    parser.error('An alternate oracle must explain its independent reference contract')
                alternate = case_directory/'reference-main.c'
                alternate.write_text(case['reference_source']+'\n', encoding='utf-8')
                reference_sources[0] = alternate
                reference_hashes['reference-main.c'] = hashlib.sha256(alternate.read_bytes()).hexdigest()
            for name, content in case.get('reference_additional_sources', {}).items():
                extra = (case_directory/'reference-only'/name).resolve()
                if not extra.is_relative_to((case_directory/'reference-only').resolve()) or extra.suffix != '.c':
                    parser.error('Invalid reference-only translation unit: '+name)
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_text(content+'\n', encoding='utf-8')
                reference_sources.append(extra)
                reference_hashes['reference-only/'+name] = hashlib.sha256(extra.read_bytes()).hexdigest()
            oracle_error = None
            try:
                if 'reject' in case:
                    ref = subprocess.run([str(reference),'-std=c11','-pedantic-errors',*case.get('reference_flags',[]),*reference_includes,'-fsyntax-only',*map(str,reference_sources)],
                                         capture_output=True,text=True,timeout=20,env=translation_environment)
                    if case.get('reference_reject_required',True):
                        assert ref.returncode != 0, 'Clang accepted the invalid fixture'
                else:
                    reference_output = work/('reference-'+case['id']+'.exe')
                    ref = subprocess.run([str(reference),'-std=c11','-pedantic-errors',*case.get('reference_flags',[]),*reference_includes,'-O2',
                        '-fuse-ld=lld','-fms-runtime-lib=static',*map(str,reference_sources),'-o',str(reference_output)],
                        capture_output=True,text=True,timeout=20,env=translation_environment)
                    assert ref.returncode == 0, ref.stdout+ref.stderr
                    native = execute([str(reference_output)],cwd=work,timeout=3)
                    assert (native.returncode,native.stdout)==(case.get('exit',42),case.get('stdout','')),str(native)
            except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                oracle_error = str(error)
            for opt in args.opt or ['0','2']:
                record = {'id':case['id'],'feature':case['feature'],'clause':case['clause'],
                          'opt':opt,'passed':False,'reference_validated':oracle_error is None}
                if 'work_item' in case: record['work_item']=case['work_item']
                if case.get('translation_environment'): record['translation_environment'] = case['translation_environment']
                if case.get('known_target_contract_gap'):
                    record['known_target_contract_gap'] = case['known_target_contract_gap']
                    record['reference_note'] = case.get('reference_note', '')
                if reference_hashes:
                    record.update(reference_source_sha256=reference_hashes,
                                  reference_note=case.get('reference_note',''),
                                  reference_source_variant='alternate' if 'reference_source' in case else 'same source plus explicit compiler-header support')
                if case.get('reference_header_policy') == 'target-crt':
                    record['reference_header_view'] = reference_header_view
                if 'reference_flags' in case:
                    record.update(reference_flags=case['reference_flags'],reference_note=case.get('reference_note',''))
                # Windows can retain a just-exited image briefly. Independent
                # artifacts avoid racing that handle without delaying the suite.
                output = work/('program-'+case['id']+'-O'+opt+'.exe')
                output.write_bytes(b'previous-success')
                phase = 'reference'
                try:
                    assert oracle_error is None, 'Reference: '+str(oracle_error)
                    phase = 'compile'
                    objects = []
                    compilations = []
                    for index, source in enumerate(sources[1:], 1):
                        object_path = case_directory/('unit-'+str(index)+'-O'+opt+'.obj')
                        unit_report = case_directory/('unit-'+str(index)+'-O'+opt+'.json')
                        compiled = execute([str(compiler),'build',str(source),*case_common,'--opt-level',opt,
                            '--target','object','-o',str(object_path),'--report',str(unit_report)],
                            cwd=work,env=compiler_environment,timeout=30,memory_limit=512*1024**2)
                        compilations.append(dict(source=source.name,exit=compiled.returncode,
                            seconds=compiled.elapsed_seconds,peak_commit_bytes=compiled.peak_memory_bytes))
                        record['compilations'] = compilations
                        assert compiled.returncode == 0, compiled.stdout+compiled.stderr
                        info = json.loads(unit_report.read_text())
                        assert info['backend']=='in-process' and info['processes_spawned']==0,info
                        objects.extend(['--link-object',str(object_path)])
                    built = execute([str(compiler),'build',str(path),*case_common,'--opt-level',opt,
                        '--target','exe','-o',str(output),*objects,'--report',str(work/'build.json')],
                        cwd=work,env=compiler_environment,timeout=30,memory_limit=512*1024**2)
                    record.update(compile_exit=built.returncode,seconds=built.elapsed_seconds,
                                  peak_commit_bytes=built.peak_memory_bytes)
                    if 'reject' in case:
                        phase = 'required-diagnostic'
                        assert built.returncode == 1, built.stdout+built.stderr
                        diagnostic = built.stdout+built.stderr
                        assert diagnostic.strip(), 'Required diagnostic was empty'
                        if isinstance(case['reject'], str):
                            assert case['reject'] in diagnostic, diagnostic
                        else:
                            assert case['reject'] is True, 'Invalid required-diagnostic fixture policy'
                        assert output.read_bytes() == b'previous-success','failed build replaced the artifact'
                    else:
                        assert built.returncode == 0, built.stdout+built.stderr
                        phase = 'runtime'
                        native = execute([str(output)],cwd=work,timeout=3,memory_limit=64*1024**2)
                        record.update(runtime_exit=native.returncode,runtime_stdout=native.stdout)
                        assert (native.returncode,native.stdout)==(case.get('exit',42),case.get('stdout','')),str(native)
                        phase = 'backend-contract'
                        info=json.loads((work/'build.json').read_text())
                        assert info['backend']=='in-process' and info['processes_spawned']==0,info
                        if case.get('llvm_ir_contains'):
                            phase = 'llvm-contract'
                            llvm_ir = case_directory/('main-O'+opt+'.ll')
                            translated = execute([str(compiler),'build',str(path),*case_common,'--opt-level','0',
                                '--target','llvm-ir','-o',str(llvm_ir),'--report',str(work/'ir-build.json')],
                                cwd=work,env=compiler_environment,timeout=30,memory_limit=512*1024**2)
                            assert translated.returncode == 0,translated.stdout+translated.stderr
                            content = llvm_ir.read_text(encoding='utf-8')
                            for fragment in case['llvm_ir_contains']:
                                assert fragment in content,'Missing LLVM fact: '+fragment+'\n'+content
                            info=json.loads((work/'ir-build.json').read_text())
                            assert info['backend']=='in-process' and info['processes_spawned']==0,info
                    record['passed']=True
                except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                    message=str(error)
                    record.update(failure_phase=phase,error=message if len(message)<=4000 else
                        message[:3000]+'\n... diagnostic context truncated ...\n'+message[-1000:])
                results.append(record)
                print(('PASS ' if record['passed'] else 'FAIL ')+case['id']+' O'+opt+
                      (': '+record['error'][-700:] if not record['passed'] else ''),flush=True)
    unchanged = before == fingerprints(compiler,args.probe_manifest) and c11_reference_headers.unchanged(reference_header_view)
    if args.frozen:
        unchanged = unchanged and frozen == validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx'])
    passed = sum(r['passed'] for r in results)
    report = {'format':1,'standard':manifest['standard'],'target':manifest['target'],
              'full_c11_conformance_claimed':False,
              'scope':corpus.get('scope','clause-tagged acceptance corpus; not certification'),
              'all_configured_cases_selected':len(cases)==len(corpus['cases']),
              'features_without_cases':sorted(known_features-{c['feature'] for c in corpus['cases']}),
              'support_plan':SUPPORT_PLAN.relative_to(ROOT).as_posix(),
              'pending_support_work':[item['id'] for item in items if item['status']!='complete'],
              'phase_status':{phase['id']:phase['status'] for phase in plan['phases']},
              'frozen_provenance':frozen,
              'inputs_unchanged':unchanged,'sha256':before,'passed':passed,'total':len(results),'results':results}
    if args.probe_manifest:
        report['work_items_without_probes']=sorted({item['id'] for item in items}-{c.get('work_item') for c in corpus['cases']})
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{passed}/{len(results)} clause-tagged checks passed; inputs unchanged: {unchanged}')
    return int(not unchanged or passed != len(results))

if __name__ == '__main__':
    raise SystemExit(main())
