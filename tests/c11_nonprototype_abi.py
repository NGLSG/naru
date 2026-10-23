"""Windows x64 unprototyped calls duplicate FP arguments into GP registers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from c11_conformance import ROOT, fingerprints
from frozen_snapshot import validate_frozen
from native_process import execute


CASES = [
    ('first-float', 'extern int answer();int main(void){return answer(42.0f);}', 0, 'rcx'),
    ('first-double', 'extern int answer();int main(void){return answer(42.0);}', 0, 'rcx'),
    ('second-float', 'extern int answer();int main(void){return answer(1,42.0f);}', 1, 'rdx'),
    ('fourth-float', 'extern int answer();int main(void){return answer(1,2,3,42.0f);}', 3, 'r9'),
    ('function-pointer', 'extern int(*p)();int main(void){return p(42.0f);}', 0, 'rcx'),
]


def inputs(compiler):
    result = fingerprints(compiler)
    result[str(Path(__file__).resolve())] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--report', type=Path, default=ROOT/'target/c11-nonprototype-abi.json')
    parser.add_argument('--frozen', action='store_true')
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    reference = shutil.which('clang.exe')
    if reference is None:
        parser.error('A reference Clang is required to assemble the independent ABI oracle')
    frozen = validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx']) if args.frozen else None
    before = inputs(compiler)
    rules = [] if args.frozen else ['--rules',str(ROOT/'dialects/c11.stx')]
    discovered = execute([str(compiler),'eval',*rules,'--expr','env.entries(headers.toolchain(env.empty()))'],
        cwd=ROOT,env=dict(os.environ,PATH=''),timeout=10)
    assert discovered.returncode==0,discovered.stderr
    target = dict(json.loads(discovered.stdout))
    msvc = Path(target['vc_tools_dir'])/'bin/Hostx64/x64/cl.exe'
    assert msvc.is_file(), 'MSVC is required for the documented Windows x64 unprototyped ABI oracle'
    reference_hashes = {str(Path(reference).resolve()):hashlib.sha256(Path(reference).read_bytes()).hexdigest(),
        str(msvc):hashlib.sha256(msvc.read_bytes()).hexdigest()}
    rows = []
    with tempfile.TemporaryDirectory(prefix='naru C11 no-prototype ABI ') as directory:
        work = Path(directory)
        for name,source,xmm,gp in CASES:
            assembly = work/(name+'.s')
            assembly.write_text('.text\n.globl answer\nanswer:\n'
                f' movq %xmm{xmm}, %rax\n cmpq %{gp}, %rax\n jne .Lbad\n'
                ' movabsq $0x4045000000000000, %rdx\n cmpq %rdx, %rax\n jne .Lbad\n'
                ' movl $42, %eax\n retq\n.Lbad:\n movl $1, %eax\n retq\n'
                '.data\n.globl p\n.p2align 3\np:\n.quad answer\n',encoding='utf-8')
            oracle = work/(name+'.obj')
            assembled = subprocess.run([reference,'-c','-target','x86_64-pc-windows-msvc',str(assembly),'-o',str(oracle)],capture_output=True,text=True,timeout=20)
            assert assembled.returncode == 0, assembled.stdout+assembled.stderr
            path = work/(name+'.c')
            path.write_text(source+'\n',encoding='utf-8')
            for opt in ['0','2']:
                row = dict(id=name,opt=opt,passed=False,clause='6.5.2.2; Windows x64 target ABI',
                    oracle_object_sha256=hashlib.sha256(oracle.read_bytes()).hexdigest())
                try:
                    reference_program = work/(name+'-reference-O'+opt+'.exe')
                    reference_object = work/(name+'-reference-O'+opt+'.obj')
                    checked = subprocess.run([str(msvc),'/nologo','/c','/std:c11','/MT',
                        '/Od' if opt=='0' else '/O2','/Fo'+str(reference_object),str(path)],cwd=work,capture_output=True,text=True,timeout=20)
                    assert checked.returncode == 0, checked.stdout+checked.stderr
                    checked = subprocess.run([reference,'-fuse-ld=lld','-fms-runtime-lib=static',
                        str(reference_object),str(oracle),'-o',str(reference_program)],capture_output=True,text=True,timeout=20)
                    assert checked.returncode == 0, checked.stdout+checked.stderr
                    native = execute([str(reference_program)],cwd=work,timeout=3)
                    assert (native.returncode,native.stdout)==(42,''),str(native)
                    row['reference_validated'] = True
                    program = work/(name+'-naru-O'+opt+'.exe')
                    command = [str(compiler),'build',str(path),
                        *([] if args.frozen else ['--rules',str(ROOT/'dialects/c11.stx')]),
                        '--frontend','c11.frontend','--entry','c11.item','--unit','program',
                        '--relation','c11.emit_program','--runtime','crt-static','--target','exe',
                        '--rule-depth','1024','--rule-budget','100000000','--parse-budget','100000000',
                        '--opt-level',opt,'--link-object',str(oracle),'-o',str(program),'--report',str(work/'build.json')]
                    built = execute(command,cwd=work,env=dict(os.environ,PATH=''),timeout=30,memory_limit=512*1024**2)
                    assert built.returncode==0,built.stdout+built.stderr
                    report = json.loads((work/'build.json').read_text())
                    assert report['backend']=='in-process' and report['processes_spawned']==0,report
                    native = execute([str(program)],cwd=work,timeout=3)
                    assert (native.returncode,native.stdout)==(42,''),str(native)
                    row.update(passed=True,seconds=built.elapsed_seconds,peak_commit_bytes=built.peak_memory_bytes)
                except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                    row['error'] = str(error)
                rows.append(row)
                print(('PASS ' if row['passed'] else 'FAIL ')+name+' O'+opt+('' if row['passed'] else ': '+row['error'][-1000:]),flush=True)
    unchanged = before == inputs(compiler)
    unchanged = unchanged and all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha for path,sha in reference_hashes.items())
    if frozen:
        unchanged = unchanged and frozen == validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx'])
    passed = sum(row['passed'] for row in rows)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(dict(passed=passed,total=len(rows),results=rows,sha256=before,
        inputs_unchanged=unchanged,frozen_provenance=frozen,full_c11_conformance_claimed=False,
        target=target,reference_sha256=reference_hashes,reference_abi='MSVC caller; Clang assembler/linker; documented Windows x64 GP/XMM duplication'),indent=2)+'\n',encoding='utf-8')
    print(f'{passed}/{len(rows)} no-prototype ABI checks; inputs unchanged: {unchanged}',flush=True)
    return int(passed!=len(rows) or not unchanged)


if __name__ == '__main__':
    raise SystemExit(main())
