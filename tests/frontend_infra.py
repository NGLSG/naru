"""Generic frontend facilities: persistent values, contextual parsing and SDK facts."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'target/naru.exe')
    parser.add_argument('--frozen', action='store_true')
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    results = []
    with tempfile.TemporaryDirectory(prefix='naru frontend infra ') as directory:
        work = Path(directory)
        def call(command, *options):
            return execute([str(compiler), command, *map(str, options)], cwd=work,
                           env=dict(os.environ, PATH=''), timeout=90, memory_limit=2 * 1024**3)
        def rule(name):
            if args.frozen:
                return []
            dependencies = ['--rules', ROOT / 'dialects/parse.stx', '--rules', ROOT / 'tests/fixtures/frontend_choices.stx'] if name == 'tests/fixtures/frontend_infra.stx' else []
            return [*dependencies, '--rules', ROOT / name]
        def evaluate(expression, expected, *options):
            result = call('eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr', expression, *options)
            assert result.returncode == 0, result.stdout + result.stderr
            assert result.stdout.strip().replace(' ', '') == expected.replace(' ', ''), result.stdout
            return result
        def check(name, action):
            try:
                value = action()
                item = {'name': name, 'passed': True}
                if value is not None and hasattr(value, 'peak_memory_bytes'):
                    item.update(elapsed_seconds=value.elapsed_seconds, peak_memory_bytes=value.peak_memory_bytes)
                results.append(item)
                print('PASS ' + name, flush=True)
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                results.append({'name': name, 'passed': False, 'error': str(error)})
                print('FAIL ' + name + ': ' + str(error), flush=True)
        check('sharing list tails preserves all prior values', lambda: evaluate(
            'bind($a,[2,3],bind($b,list.prepend(1,$a),bind($c,list.concat($a,[4]),[$a,$b,$c,list.tail($b),list.tail(list.tail($b))])))',
            '[[2,3],[1,2,3],[2,3,4],[2,3],[3]]'))
        check('flatten composes chunks including empty chunks', lambda: evaluate(
            'list.flatten([[],[1,2],[],[3],[]])', '[1,2,3]'))
        check('tail of singleton remains an empty reusable value', lambda: evaluate(
            'bind($a,list.tail([1]),[$a,list.prepend(2,$a),$a])', '[[],[2],[]]'))
        check('indexed scopes retain parent shadowing and arbitrary term keys', lambda: evaluate(
            'bind($a,env.put(env.empty(),term("key",[1,[2,3]]),7),bind($b,env.put($a,term("key",[1,[2,3]]),9),[env.get($a,term("key",[1,[2,3]])),env.get($b,term("key",[1,[2,3]]))]))', '[7,9]'))
        check('indexed scopes distinguish text and integer keys', lambda: evaluate(
            'bind($a,env.put(env.put(env.empty(),"1",7),1,9),[env.get($a,"1"),env.get($a,1)])', '[7,9]'))
        check('hash collisions preserve distinct keys and old versions', lambda: evaluate(
            'bind($a,env.put(env.put(env.empty(),"cfnwhydaxw",7),"kkwakwunre",9),bind($b,env.put($a,"cfnwhydaxw",11),[env.get($a,"cfnwhydaxw"),env.get($a,"kkwakwunre"),env.get($b,"cfnwhydaxw"),env.get($b,"kkwakwunre")]))', '[7,9,11,9]'))
        for size in (2000, 10000):
            check(f'{size} composed list and scope operations', lambda size=size: evaluate(
                f'frontend_infra.verify({size})', '[1,1,1,1,1]', '--rule-budget', '10000000'))
        check('nested callbacks reclaim discarded work', lambda: evaluate(
            'frontend_infra.scratch(4000,64)', '[64,252000]', '--rule-budget', '100000000'))
        check('escaped collision maps and shared cursors survive nested scopes', lambda: evaluate(
            'list.fold("frontend_infra.escape_sum",frontend_infra.escaped(1000),0)', '2006000', '--rule-budget', '100000000'))
        check('atomic operator remains indivisible', lambda: evaluate(
            'source.parse_expression([[14,"++","<atomic>",1,1],[2,"42","<atomic>",1,3]],"atomic.expr")',
            'frontend_cache.Increment(frontend_cache.Number(42))', *rule('tests/fixtures/frontend_cache.stx')))
        check('separate operator tokens remain separate', lambda: evaluate(
            'source.parse_expression([[14,"+","<atomic>",1,1],[14,"+","<atomic>",1,3],[2,"42","<atomic>",1,5]],"atomic.expr")',
            'frontend_cache.Positive(frontend_cache.Positive(frontend_cache.Number(42)))', *rule('tests/fixtures/frontend_cache.stx')))
        check('environment enumeration exposes current collision bindings', lambda: evaluate(
            'bind($old,env.put(env.put(env.empty(),"cfnwhydaxw",7),"kkwakwunre",9),bind($new,env.put($old,"cfnwhydaxw",21),[size(env.entries($new)),list.fold("frontend_infra.entry_sum",env.entries($new),0),list.fold("frontend_infra.entry_sum",env.entries($old),0)]))',
            '[2,30,16]'))
        check('literal metadata preserves delimiters, escapes and UTF8', lambda: evaluate(
            'frontend_infra.literal_snapshot()', '["a:b","\\\"","line\\nnext","你好",""]'))
        def rejection(*options, contains):
            result = call(*options)
            assert result.returncode in (1, 2), result.stdout + result.stderr
            assert contains in result.stdout + result.stderr, result.stdout + result.stderr
        check('Unicode scalars decode ASCII BMP and supplementary UTF8', lambda: evaluate(
            'text.codepoints("Aα😀")', '[65,945,128512]'))
        check('Unicode encoding preserves all UTF8 width boundaries and NUL', lambda: evaluate(
            'text.codepoints(text.from_codepoints([0,127,128,2047,2048,55295,57344,65535,65536,1114111]))',
            '[0,127,128,2047,2048,55295,57344,65535,65536,1114111]'))
        check('binary text preserves NUL and non-UTF8 bytes', lambda: evaluate(
            'bind($s,text.from_bytes([0,128,255]),[text.len($s),text.byte($s,0),text.byte($s,1),text.byte($s,2)])',
            '[3,0,128,255]'))
        check('ASCII predicate distinguishes UTF8 and binary text', lambda: evaluate(
            '[text.is_ascii(""),text.is_ascii("abc"),text.is_ascii("α"),text.is_ascii(text.from_bytes([255]))]',
            '[1,1,0,0]'))
        for values in ('[192,128]', '[237,160,128]', '[244,144,128,128]', '[240,159]', '[128]'):
            check('malformed UTF8 is rejected '+values, lambda values=values: rejection(
                'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr',
                'text.codepoints(text.from_bytes('+values+'))', contains='UTF-8'))
        for value in ('-1', '55296', '57343', '1114112'):
            check('invalid Unicode scalar is rejected '+value, lambda value=value: rejection(
                'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr',
                'text.from_codepoints(['+value+'])', contains='invalid Unicode scalar'))
        for value in ('-1', '256'):
            check('invalid byte is rejected '+value, lambda value=value: rejection(
                'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr',
                'text.from_bytes(['+value+'])', contains='byte value outside'))
        check('captured values fit their exact evaluation budget', lambda: evaluate(
            'frontend_infra.identity([1,2])', '[1,2]', '--rule-budget', '5'))
        check('captured values still charge an evaluation step', lambda: rejection(
            'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr', 'frontend_infra.identity([1,2])',
            '--rule-budget', '4', contains='budget exhausted'))
        check('guards and captures fit their exact evaluation budget', lambda: evaluate(
            'frontend_infra.guarded_identity(42)', '42', '--rule-budget', '6'))
        check('guarded bodies still charge an evaluation step', lambda: rejection(
            'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr', 'frontend_infra.guarded_identity(42)',
            '--rule-budget', '5', contains='budget exhausted'))
        check('recursive rules do not charge router stack depth', lambda: evaluate(
            'frontend_infra.descend(100)', '42'))
        check('recursive rules retain their semantic depth limit', lambda: rejection(
            'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr', 'frontend_infra.descend(140)',
            contains='recursion depth limit exceeded (256)'))
        for budget in ('0', '-1', '1000000001', '1.5', '1x'):
            check('invalid evaluation budget ' + budget, lambda budget=budget: rejection(
                'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr', '1', '--rule-budget', budget,
                contains='evaluation budget must be'))
        check('a small evaluation budget remains enforceable', lambda: rejection(
            'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr', 'frontend_infra.verify(100)',
            '--rule-budget', '10', contains='budget exhausted'))
        def data(expression, expected):
            result = call('eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr', expression)
            assert result.returncode == 0, result.stdout + result.stderr
            assert json.loads(result.stdout) == expected, result.stdout
            return result
        for value, expected in [('', []), ('a', ['a']), ('a\n', ['a']), ('\n', ['']),
                                ('a\r\nb\rc\n\n', ['a', 'b', 'c', ''])]:
            check('physical lines ' + repr(value), lambda value=value, expected=expected:
                  data('text.lines(' + json.dumps(value) + ')', expected))
        check('line spans preserve original CRLF byte offsets', lambda: data(
            'text.line_spans("a\\r\\nb\\rc\\n")', [[0,1,1],[3,4,2],[5,6,3]]))
        check('byte columns clip short rows and preserve empty fields', lambda: data(
            'text.columns("abcdef",[[0,2],[2,4],[8,12],[1,1]])', ['ab','cd','','']))
        check('Unicode columns count scalars including supplementary planes', lambda: data(
            'text.columns("A你好😀B",[[0,1],[1,3],[3,4],[4,9]],"unicode")', ['A','你好','😀','B']))
        check('tab expansion tracks Unicode columns and resets on newlines', lambda: data(
            'text.expand_tabs("你\\tX\\nA\\tY",4)', ['你   X', 'A   Y'][0] + '\n' + ['你   X', 'A   Y'][1]))
        check('line and column rules compose as a fixed column frontend', lambda: data(
            'frontend_choices.column_program("AB\\tCD\\r\\n123456789")', [['AB  ','    ','CD'],['1234','5678','9']]))
        check('negative columns are diagnosed', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', 'text.columns("abc",[[-1,2]])', contains='invalid column range'))
        check('unknown column units are diagnosed', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', 'text.columns("abc",[[0,2]],"display")', contains='column unit must be'))
        check('Unicode columns reject truncated byte slices', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', 'text.columns(text.slice("你",0,1),[[0,1]],"unicode")', contains='truncated UTF-8'))
        check('reversed column ranges are diagnosed', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', 'text.columns("abc",[[2,1]])', contains='invalid column range'))
        word = '[[1,"class","<choices>",1,1]]'
        check('strict syntax still rejects peers', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', f'source.parse_expression({word},"choices.word")', contains='ambiguous syntax'))
        check('specificity automatically selects literal rules', lambda: evaluate(
            f'source.parse_expression({word},"choices.word","parse.specific")', 'frontend_choices.Keyword()'))
        check('equal specificity still rejects incompatible rewrites', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', f'source.parse_expression({word},"choices.tie","parse.specific")', contains='ambiguous ranked candidates'))
        check('discarded AST actions are never evaluated by the resolver', lambda: evaluate(
            f'source.parse_expression({word},"choices.opaque","frontend_choices.names")', 'frontend_choices.Name("class")'))
        check('resolver candidate indexes are checked', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', f'source.parse_expression({word},"choices.word","frontend_choices.bad_index")', contains='candidate index outside'))
        check('resolver source IO is forbidden', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', f'source.parse_expression({word},"choices.word","frontend_choices.io")', contains='guards cannot perform source IO'))
        check('rank callbacks also enforce purity outside a parser', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', 'rule.select([1,2],"frontend_choices.ranking_io",0)', contains='guards cannot perform source IO'))
        check('ranked selection uses unique maximum and context', lambda: data(
            'rule.select([40,42,44],"frontend_choices.context_rank",42)', 1))
        check('integer ranks choose the same maximum independently of order', lambda: data(
            '[rule.select([40,42,44],"frontend_choices.integer_rank",0),rule.select([44,42,40],"frontend_choices.integer_rank",0)]', [2,0]))
        check('large ranking reclaims temporary callback scores', lambda: evaluate(
            'bind([$n,$values],frontend_infra.generate(10000),rule.select($values,"frontend_choices.integer_rank",0))', '0', '--rule-budget', '10000000'))
        check('all rejected candidates produce a diagnostic', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', 'rule.select([1,2],"frontend_choices.rejected_rank",0)', contains='rejected every candidate'))
        check('equal maximum rank produces a diagnostic', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', 'rule.select([1,2],"frontend_choices.constant_rank",0)', contains='ambiguous ranked candidates'))
        check('infix alternatives can be resolved from AST facts', lambda: evaluate(
            'source.parse_expression([[2,"20","<choices>",1,1],[5,"+","<choices>",1,3],[2,"22","<choices>",1,4]],"choices.expr","frontend_choices.vector")',
            'frontend_choices.VectorAdd(frontend_choices.Number(20),frontend_choices.Number(22))'))
        check('prefix ties do not reject a later longer production', lambda: evaluate(
            'source.parse_expression([[1,"a","<choices>",1,1],[1,"b","<choices>",1,3]],"choices.long")', 'frontend_choices.Long()'))
        check('raised rule depth allows deeper valid compositions', lambda: evaluate(
            'frontend_infra.descend(200)', '42', '--rule-depth', '512'))
        check('maximum configured rule depth supports deep finite chains', lambda: evaluate(
            'frontend_infra.descend(500)', '42', '--rule-depth', '1024'))
        check('configured rule depth still bounds recursion', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', 'frontend_infra.descend(30)', '--rule-depth', '32', contains='recursion depth limit exceeded (32)'))
        for option in ('--rule-depth', '--parse-depth'):
            for value in ('0', '-1', '1025', '1x'):
                check('invalid depth ' + option + ' ' + value, lambda option=option, value=value: rejection(
                    'eval', *rule('tests/fixtures/frontend_infra.stx'), '--expr', '1', option, value, contains='evaluation depth must be'))
        source = work / 'choices.custom'
        source.write_text('class ordinary', encoding='utf-8')
        check('selected candidates alone enter contextual commit', lambda: evaluate(
            'source.parse_tokens([[1,"class","<choices>",1,1]],"choices.word",env.empty(),"frontend_choices.commit","parse.specific")',
            '[frontend_choices.Keyword()]'))
        def configured_parse_depth():
            source.write_text('(' * 140 + '42' + ') a' * 140 + ';', encoding='utf-8')
            rejection('parse', source, *rule('tests/fixtures/frontend_cache.stx'), '--entry', 'cache.item', '--parse-depth', '64', contains='recursion depth limit exceeded (64)')
            result = call('parse', source, *rule('tests/fixtures/frontend_cache.stx'), '--entry', 'cache.item', '--parse-depth', '512')
            assert result.returncode == 0, result.stdout + result.stderr
            assert result.stdout.count('frontend_cache.A(') == 140, result.stdout
            return result
        check('parse depth is configurable independently from rule depth', configured_parse_depth)
        def frozen_matcher_budget():
            # cache.item first enters cache.expr, so three parser steps are
            # enough for the interpreted category calls but not for both
            # production match attempts.  Frozen matchers must charge the
            # same syntax budget as dynamic match_syntax.
            source.write_text('1;', encoding='utf-8')
            result = call('parse', source, *rule('tests/fixtures/frontend_cache.stx'),
                          '--entry', 'cache.item', '--parse-steps', '3')
            assert result.returncode in (1, 2), result.stdout + result.stderr
            assert 'syntax evaluation budget exhausted' in result.stdout + result.stderr, result.stdout + result.stderr
            return result
        check('dynamic and frozen syntax matchers charge identical parse steps', frozen_matcher_budget)
        def parser_steps_charge_rule_budget():
            # Keep the token rows outside the rule AST so this isolates the
            # parser's own work from argument evaluation.  The old path could
            # parse all 100 items while consuming only the outer call steps.
            source_text = '1;' * 100
            config = '["abcdefghijklmnopqrstuvwxyz","abcdefghijklmnopqrstuvwxyz","0123456789","0123456789","",[";"],[],""]'
            expression = 'source.parse_tokens(text.lex(' + json.dumps(source_text) + ',"<budget>",' + config + '),"cache.item")'
            return rejection('eval', *rule('tests/fixtures/frontend_cache.stx'), '--expr', expression,
                             '--rule-budget', '20', contains='budget exhausted')
        check('parser steps consume the caller rule budget', parser_steps_charge_rule_budget)
        check('parser rule callbacks cannot escape the caller budget', lambda: rejection('eval', *rule('tests/fixtures/frontend_infra.stx'),
            '--expr', f'source.parse_expression({word},"choices.guarded")', '--rule-budget', '11', contains='budget exhausted'))
        def project_limits():
            project = work / 'Naru.toml'
            selected_rules = [(ROOT/'tests/fixtures/frontend_infra.stx').as_posix()]
            if args.frozen:
                metadata = json.loads((compiler.parent.parent/'naru-frozen-project.json').read_text())
                selected_rules = [Path(path).as_posix() for path in metadata['explicit_rules']]
            project.write_text('[package]\nname="limits-test"\nversion="0.1.0"\n'
                '[language]\nrules='+json.dumps(selected_rules)+'\n[limits]\nrule_depth=32\nparse_depth=64\n'
                'rule_steps=1000000\nparse_steps=1000000\n', encoding='utf-8')
            rejection('eval', '--project', project, '--expr', 'frontend_infra.descend(30)', contains='recursion depth limit exceeded (32)')
            result = call('eval', '--project', project, '--expr', 'frontend_infra.descend(200)', '--rule-depth', '512')
            assert result.returncode == 0 and result.stdout.strip() == '42', result.stdout+result.stderr
            project.write_text(project.read_text().replace('rule_depth=32', 'rule_depth=0'), encoding='utf-8')
            rejection('eval', '--project', project, '--expr', '1', contains='evaluation depth must be')
            return result
        check('integer project limits are validated and CLI values override them', project_limits)
        source = work / 'main.custom'
        source.write_text('declare T; T;', encoding='utf-8')
        contextual = ['--frontend', 'contextual_frontend.frontend', *rule('tests/fixtures/contextual_frontend.stx')]
        def context_success():
            result = call('parse', source, *contextual)
            assert result.returncode == 0, result.stdout + result.stderr
            assert 'contextual_frontend.Seen("T")' in result.stdout, result.stdout
            return result
        check('committed context makes a later syntax rule eligible', context_success)
        def forward():
            source.write_text('T; declare T;', encoding='utf-8')
            rejection('parse', source, *contextual, contains='cannot parse contextual.item')
        check('a later declaration cannot alter earlier syntax matches', forward)
        def conflict():
            source.write_text('declare T; T;', encoding='utf-8')
            rejection('parse', source, *contextual, '--rules', ROOT / 'tests/fixtures/contextual_conflict.stx', contains='ambiguous syntax')
        check('matching contextual peer rules still diagnose ambiguity', conflict)
        def io_guard():
            source.write_text('read missing;', encoding='utf-8')
            rejection('parse', source, *contextual, '--rules', ROOT / 'tests/fixtures/contextual_io_guard.stx', contains='guards cannot perform source IO')
        check('a contextual syntax guard cannot perform source IO', io_guard)
        def shared_prefixes():
            source.write_text('(' * 50 + '42' + ') a' * 50 + ';', encoding='utf-8')
            result = call('parse', source, *rule('tests/fixtures/frontend_cache.stx'), '--entry', 'cache.item')
            assert result.returncode == 0, result.stdout + result.stderr
            assert result.stdout.count('frontend_cache.A(') == 50 and 'frontend_cache.Number(42)' in result.stdout, result.stdout
            return result
        check('shared recursive grammar prefixes stay bounded', shared_prefixes)
        def toolchain():
            result = call('eval', *rule('dialects/headers.stx'), '--expr',
                'bind($t,headers.toolchain(env.empty()),[env.get($t,"triple"),env.get($t,"pointer_bits"),env.get($t,"include_paths"),env.get($t,"library_paths")])')
            assert result.returncode == 0, result.stdout + result.stderr
            facts = json.loads(result.stdout)
            assert facts[0].startswith('x86_64-') and facts[1] == 64, facts
            assert any((Path(path) / 'stdio.h').is_file() for path in facts[2]), facts
            assert any((Path(path) / 'libucrt.lib').is_file() for path in facts[3]), facts
            assert all('Naru/dialects' not in path.replace('\\', '/') for path in facts[2]), facts
            return result
        check('headers and libraries come from installed target SDKs without a child process', toolchain)
        check('an invalid SDK override is a diagnostic', lambda: rejection(
            'eval', *rule('dialects/headers.stx'), '--expr',
            'target.toolchain("{\\"vc_tools_dir\\":\\"does-not-exist\\"}")', contains='directory does not exist'))
    passed = sum(item['passed'] for item in results)
    report = ROOT / 'target' / ('frontend-infra-frozen.json' if args.frozen else 'frontend-infra.json')
    report.write_text(json.dumps({'passed': passed, 'total': len(results), 'results': results}, indent=2) + '\n', encoding='utf-8')
    print(f'\n{passed}/{len(results)} frontend infrastructure checks passed')
    return int(passed != len(results))

if __name__ == '__main__':
    raise SystemExit(main())
