# Naru acceptance tests

Build with `.\build.ps1 -Release`, then run `.\test.ps1`. Use `-Aot` to build
and verify specialized compilers as well. Tests exercise the public compiler
commands and actual backend libraries. A crash or timeout never counts as a
successful rejection.

| Suite | Coverage |
| --- | --- |
| `tests/run.py` | 64 grammar, rule, manifest, ambiguity, exact arithmetic, ownership and dialect-composition cases |
| `tests/rules.py` | 155 open-rule, unification, scope, number, type, custom-constraint, loan, dynamic/AOT-parity and native-execution contracts |
| `tests/base_flow.py` | 34 ordinary base function/mutation/branch/loop/cast checks, O0/O2 native results, stack growth, scope errors and scalar promotion; also runs against frozen base |
| `tests/externc.py` | 24 C declaration/type/string checks and O0/O2 scalar/pointer/UTF-8 ABI calls linked with an independent C harness; also runs against frozen externc |
| `tests/projects.py` | 59 project-reference, graph/version, lock/fingerprint, relocation, input-protection and native-link checks; 11 checks against the project-frozen externc compiler |
| `tests/modules.py` | 9 source dependency graph and module-header cases |
| `tests/entry_files.py` | Filename-independent entries, raw frontend selection/options, project main.c, dependency protection and matching-rule conflicts |
| `tests/frontend_infra.py` | Immutable list sharing, persistent environment collisions, contextual syntax guards/commit, pure candidate ranking, line/column frontends, independently configurable depths, finite budgets and native SDK discovery; dynamic and frozen modes |
| `tests/freeze_driver.py` | Low-memory sampling failures preserve real child success/failure; invalid worker limits reject before staging |
| `tests/parser_perf.py` | Same-input baseline/current parser timing and peak commit for 2003 rules, recursive prefixes and real system stdio parsing; asserts identical AST hashes |
| `tests/c11_stress.py` | 12 real C11/system-CRT probes including nested/designated initialization, unchanged pinned TinyExpr and cJSON; incomplete language features remain failures |
| `tests/c11_composition.py` | Clang-checked O0/O2 union/anonymous-member/FAM layout, enum constants, switch/goto, compound bit/shift assignment, SDK warning pragmas and symbol-policy combinations; diagnostics and failed-output preservation |
| `tests/dialect_debug.py` | 190 adversarial B/Pascal/C11 dialect regressions (28 B, 24 Pascal, 43 C11 fixtures at O0 and O2): word-addressing and octal constants, Pascal scoping/for/case, and C11 null-pointer/sizeof constraints; C11 fixtures cross-checked against a reference Clang; asserts unchanged rule fingerprints |
| `tests/rule_tools.py` | Shared object layout, 10,000-element and 2,048-level iterative tree folds, caller-defined traversal boundaries and CFG label reachability; dynamic and frozen modes |
| `tests/invariants.py` | 19 boundary cases: laziness, regions, paths, NUL, output preservation |
| `tests/backend.py` | 6 source-to-backend cases: grammar equivalence, MLIR folding, O0/O3 executables, IRDL |
| `tools/mlir/test_backend.py` | 9 direct native backend cases including affine fusion and path protection |
| `tests/native_backend.py` | 22 native artifact, CFG, plugin, DLL-symbol, bounds and diagnostic cases; 24 with both frozen compilers |
| `tests/parity.py` | 11 dynamic/AOT parser and ownership comparisons |
| `tools/freeze/test_frozen.py` | 10 dynamic/AOT effect and MLIR comparisons |
| `tests/distribution.py` | Relocated package, default program dialect, custom numeric type, IRDL target and native plugin without PATH or child processes |
| `tests/path_lifetime.py` | Separate O0/O2 Vyx regression programs for retained paths and input lengths |

`test.ps1` builds native plugin samples before testing them. Developer builds
and tests need their host tools. The compiler being tested has no Python or
external compiler dependency: backend suites launch it using `native_process.py`
in a Windows Job with ActiveProcessLimit=1 and an empty PATH. The executable
runs and produces MLIR, bytecode, LLVM IR, objects and linked executables under
that restriction. A child-process-based implementation necessarily fails.

The native plugin pass checks ModuleOp and IntegerAttr TypeIDs as well as actual
pass execution. The native dialect's verifier accepts positive workgroup counts
and rejects invalid ones. IRDL tests verify custom types and attributes.
Optimization tests inspect actual transformed IR: arithmetic folds to 42 and
affine fusion removes a loop and intermediate allocation/load/store/deallocation.
CFG tests execute block-argument loops and backedges at O0/O3 and return 42.
These are correctness and optimization acceptance fixtures, not peak throughput
or general optimization-quality benchmarks.

`ownership.stx` remains a single-resource branch and loop example. `types.stx`
also provides MLIR's target-sized `index` type through ordinary rules, with
exact source literals preserved until lowering. `resources.stx`
independently exercises multiple resource identities, shared/exclusive lexical
loans, conflicts, moves, explicit loan endings, nested branch joins and
branch-local loan closure. Cross-function lifetimes, destructor insertion, aliases and
runtime ownership are not yet a complete integrated language implementation.
Arbitrary recursive rules have step and depth limits, without a general
convergence guarantee.

Frozen parity uses a different working directory and supplies no rule paths to
the specialized compiler. Rules define all surface keywords such as fn, def,
move, unless and sum_loop; the tests require no built-in meanings for them.
The standard aggregation check also freezes one compiler from
`dialects/standard.stx` and exercises the ownership relation without loading
any individual dialect file at runtime.
Use `tests/distribution.py --package target/dist/naru-windows-x86_64` after
packaging to verify the relocated runtime under the same no-child restriction.

`test.ps1 -C11Aot` additionally builds a single frozen C dialect group and runs
the C composition cases without `--rules`. `test.ps1 -FrontendAot` freezes the
shared layout/tree/CFG rule tools as well as the frontend infrastructure.
# 普通语言库组合

`python tests/emergence.py` 验证标准方言的结构体、泛型、枚举和模式、函数值与闭包、普通函数的所有权/借用、数组和向量、范围控制流及 defer。O0/O2 运行、非法程序、越界和清理顺序均在禁止子进程、PATH 为空的 Windows Job 中完成。完整工程额外组合本地规则、自定义类型和 CRT 链接。

`python tests/emergence.py --compiler target/specialized-emergence/target/naru.exe --frozen` 用同一套源程序验证整个组合后的 AOT 编译器；冻结方式见 `docs/rule-libraries.md`。

`python tests/operators.py` 验证用户声明的运算符、异类型参数、独立结果类型、所有权/借用、字面量选择、动态库候选、项目引用和冲突诊断。传入 `--compiler <frozen.exe> --frozen` 验证冻结及动态规则的混合装载；小组冻结可加 `--minimal`，追加标准库可用 `--overlay-standard`。
