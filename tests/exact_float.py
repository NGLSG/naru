"""Format-preserving APFloat rule tools, including range and rounding facts."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from run import Case, ROOT, evaluate, run_case

RULES = 'tests/fixtures/rule_contract.stx'

def attr(spelling: str, fmt: str = 'f64') -> str:
    return f'arg(float.attr("{spelling}","{fmt}",0),0)'

CASES = [
    Case('fractional conversion truncates toward zero', evaluate(f'float.to_int({attr("42.75")},32,1)', RULES), tree='[42,16]'),
    Case('negative conversion truncates toward zero', evaluate(f'float.to_int({attr("-42.75")},32,1)', RULES), tree='[-42,16]'),
    Case('negative fraction converts to unsigned zero', evaluate(f'float.to_int({attr("-0.75")},32,0)', RULES), tree='[0,16]'),
    Case('out of range conversion reports invalid', evaluate(f'arg(float.to_int({attr("2147483648")},32,1),1)', RULES), tree='1'),
    Case('signed minimum remains exact', evaluate(f'float.to_int({attr("-2147483648")},32,1)', RULES), tree='[-2147483648,0]'),
    Case('unsigned maximum remains exact', evaluate(f'float.to_int({attr("4294967295")},32,0)', RULES), tree='[4294967295,0]'),
    Case('f32 integer conversion preserves source rounding', evaluate('float.to_int(arg(float.from_int(16777217,"f32",0),0),64,1)', RULES), tree='[16777216,0]'),
    Case('f32 rounding exposes inexact', evaluate('arg(float.from_int(16777217,"f32",0),1)', RULES), tree='16'),
    Case('f128 preserves integers beyond host double', evaluate('float.to_int(arg(float.from_int(1267650600228229401496703205377,"f128",0),0),128,1)', RULES), tree='[1267650600228229401496703205377,0]'),
    Case('wide exact conversion exceeds i64', evaluate(f'float.to_int({attr("0x1p100")},128,1)', RULES), tree='[1267650600228229401496703205376,0]'),
    Case('floating addition', evaluate(f'float.to_int(arg(float.add({attr("20.5")},{attr("21.5")},0),0),32,1)', RULES), tree='[42,0]'),
    Case('floating subtraction', evaluate(f'float.to_int(arg(float.sub({attr("43.5")},{attr("1.5")},0),0),32,1)', RULES), tree='[42,0]'),
    Case('floating multiplication', evaluate(f'float.to_int(arg(float.mul({attr("10.5")},{attr("4")},0),0),32,1)', RULES), tree='[42,0]'),
    Case('floating division', evaluate(f'float.to_int(arg(float.div({attr("84")},{attr("2")},0),0),32,1)', RULES), tree='[42,0]'),
    Case('division by zero exposes IEEE status', evaluate(f'arg(float.div({attr("1")},{attr("0")},0),1)', RULES), tree='2'),
    Case('float negation', evaluate(f'float.to_int(arg(float.neg({attr("42")}),0),32,1)', RULES), tree='[-42,0]'),
    Case('signed zeros compare equal', evaluate(f'float.compare({attr("-0.0")},{attr("0.0")})', RULES), tree='0'),
    Case('less comparison', evaluate(f'float.compare({attr("1")},{attr("2")})', RULES), tree='-1'),
    Case('greater comparison', evaluate(f'float.compare({attr("2")},{attr("1")})', RULES), tree='1'),
    Case('NaN is unordered', evaluate(f'float.compare({attr("nan")},{attr("1")})', RULES), tree='2'),
    Case('format conversion rounds before integer conversion', evaluate(f'float.to_int(arg(float.convert({attr("16777217")},"f32",0),0),64,1)', RULES), tree='[16777216,0]'),
    Case('directed conversion preserves selected rounding', evaluate(f'float.to_int(arg(float.convert({attr("16777217")},"f32",2),0),64,1)', RULES), tree='[16777218,0]'),
    Case('binary floating formats must match', evaluate(f'float.add({attr("1","f32")},{attr("1")},0)', RULES), False, contains=('same MLIR format',)),
    Case('invalid rounding mode is diagnosed', evaluate(f'float.convert({attr("1")},"f32",5)', RULES), False, contains=('rounding mode',)),
    Case('invalid destination width is diagnosed', evaluate(f'float.to_int({attr("1")},0,1)', RULES), False, contains=('integer width',)),
    Case('invalid signedness is diagnosed', evaluate(f'float.to_int({attr("1")},32,2)', RULES), False, contains=('signedness',)),
    Case('integer attribute cannot masquerade as float', evaluate('float.neg("42:i32")', RULES), False, contains=('floating attribute',)),
]

def main() -> int:
    compiler = ROOT / 'target/naru.exe'
    results = []
    for case in CASES:
        error = run_case(compiler, case, 10)
        results.append({'name': case.name, 'passed': error is None, 'error': error})
        print(('PASS ' if error is None else 'FAIL ') + case.name + (': ' + error if error else ''), flush=True)
    report = {'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
              'backend_sha256': hashlib.sha256((ROOT / 'target/naru_mlir_backend.dll').read_bytes()).hexdigest(),
              'passed': sum(r['passed'] for r in results), 'total': len(results), 'results': results}
    (ROOT / 'target/exact-float.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return int(report['passed'] != report['total'])

if __name__ == '__main__':
    raise SystemExit(main())
