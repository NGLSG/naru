"""Provenance failures cannot silently become dynamic/AOT parity evidence."""
import copy
import json
from pathlib import Path
import tempfile
from frozen_snapshot import digest, validate_frozen

ROOT = Path(__file__).resolve().parents[1]


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix='naru frozen snapshot ') as directory:
        work = Path(directory)
        project = work/'frozen'
        (project/'src').mkdir(parents=True)
        (project/'target').mkdir()
        files = {'core':work/'core.exe', 'rule':work/'library.stx',
            'generated':project/'src/specialized.vyx', 'compiler':project/'target/naru.exe',
            'backend':project/'target/naru_mlir_backend.dll'}
        original = {name: name.encode() for name in files}
        for name, path in files.items(): path.write_bytes(original[name])
        marker = project/'naru-frozen-project.json'
        base = {'core_sha256':digest(files['core']), 'executable':str(files['compiler']),
            'executable_sha256':digest(files['compiler']), 'build_metrics':{'seconds':1},
            'rules':[{'path':str(files['rule']), 'sha256':digest(files['rule'])}],
            'specialization_sha256':digest(files['generated']),
            'backend':{'sha256':digest(files['backend'])}}
        def check(name, mutate=None, reject=None):
            for key, path in files.items(): path.write_bytes(original[key])
            info = copy.deepcopy(base)
            if mutate: mutate(info)
            marker.write_text(json.dumps(info),encoding='utf-8')
            try:
                result = validate_frozen(files['compiler'],core=files['core'],required_rules=[files['rule']])
                assert reject is None, 'stale snapshot was accepted'
                assert len(result['executable_sha256'])==64
                passed=True
            except ValueError as error:
                passed=reject is not None and reject in str(error)
            except AssertionError:
                passed=False
            results.append({'name':name,'passed':passed})
            print(('PASS ' if passed else 'FAIL ')+name)
        check('complete matching snapshot')
        check('unfinished rebuild',lambda i:i.pop('build_metrics'),'unfinished')
        check('different executable path',lambda i:i.update(executable=str(work/'other.exe')),'executable')
        check('generator changed',lambda i:files['core'].write_bytes(b'changed'),'generator')
        check('rules changed',lambda i:files['rule'].write_bytes(b'changed'),'rules differ')
        check('required module absent',lambda i:i.update(rules=[]),'required rule')
        check('generated source changed',lambda i:files['generated'].write_bytes(b'changed'),'generated source')
        check('backend changed',lambda i:files['backend'].write_bytes(b'changed'),'backend changed')
        check('executable changed',lambda i:files['compiler'].write_bytes(b'changed'),'executable changed')
        check('legacy manifest reports limited artifact attestation',lambda i:i.pop('executable_sha256'))
    passed=sum(r['passed'] for r in results)
    (ROOT/'target/frozen-snapshot.json').write_text(json.dumps({'passed':passed,'total':len(results),'results':results},indent=2)+'\n')
    return int(passed!=len(results))


if __name__=='__main__':
    raise SystemExit(main())
