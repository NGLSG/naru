# Naru acceptance tests

The [C11 full-support plan](../docs/c11-full-support.md) tracks 30 work items.
Run `python tests/c11_full_support.py --jobs 4` for the dynamic gates or add
`--frozen-compiler <current-compiler>` for both modes. `test.ps1 -C11Full`
builds the frozen compiler and runs the full gate. Missing features remain
failures; final acceptance also requires reviewed work-item evidence.

Build with `.\build.ps1 -Release`, then run `.\test.ps1`. Use `-Aot` to build
and verify specialized compilers as well. Tests exercise the public compiler
commands and actual backend libraries. A crash or timeout never counts as a
successful rejection.

Builds and independent acceptance suites default to four workers, configurable
with `-Jobs`. Suite output is retained separately under `target/test-logs`; the
summary is `target/parallel-tests.json`. Performance suites remain serial. The
parallel runner accepts suites with default arguments; run the distribution
suite separately with `--package <directory>` after packaging.
Coroutine source runners also accept `--jobs 4` to execute independent source
programs concurrently; the default remains one worker so suite-level concurrency
retains its existing bound. Every compiled program and report has a separate path.

| Suite | Coverage |
| --- | --- |
| `tests/run.py` | 64 grammar, rule, manifest, ambiguity, exact arithmetic, ownership and dialect-composition cases |
| `tests/rules.py` | 155 open-rule, unification, scope, number, type, custom-constraint, loan, dynamic/AOT-parity and native-execution contracts |
| `tests/base_flow.py` | 34 ordinary base function/mutation/branch/loop/cast checks, O0/O2 native results, stack growth, scope errors and scalar promotion; also runs against frozen base |
| `tests/coro.py` | Source-level synchronous generators: O0/O2, control flow, live SSA, generic/functions/closures/aggregate payloads, owned handles, suspended defer cleanup, diagnostics, upstream async.coro IR and paired MSVC CRT allocation; dynamic and frozen compiler acceptance |
| `tests/tasks.py` | Async tasks/generators, suspending await, executor/timers, promises and real external callbacks, user awaitable conversion, failure/cancellation, consumed ownership, cleanup, contextual typing, allocation leaks, controlled concurrent next/cancel, shutdown; O0/O2 with empty PATH and no compiler children |
| `tests/coro_abi.py` | Separate provider object and consumer for task, generator and async_generator opaque ABI; links and executes O0/O2 without compiler child processes; dynamic/frozen acceptance |
| `tests/externc.py` | 24 C declaration/type/string checks and O0/O2 scalar/pointer/UTF-8 ABI calls linked with an independent C harness; also runs against frozen externc |
| `tests/projects.py` | 59 project-reference, graph/version, lock/fingerprint, relocation, input-protection and native-link checks; 11 checks against the project-frozen externc compiler |
| `tests/modules.py` | 9 source dependency graph and module-header cases |
| `tests/entry_files.py` | Filename-independent entries, raw frontend selection/options, project main.c, dependency protection and matching-rule conflicts |
| `tests/frontend_infra.py` | Immutable list sharing, persistent environment collisions, contextual syntax guards/commit, pure candidate ranking, line/column frontends, independently configurable depths, finite budgets and native SDK discovery; dynamic and frozen modes |
| `tests/freeze_driver.py` | Low-memory sampling failures preserve real child success/failure; invalid worker limits reject before staging |
| `tests/storage.py` | 68 configured O0/O2 window/image/memory-path checks: padding, resize, malformed shapes, indexed projections, lazy producers, alignment routing, zero/one/multiple results and diagnostics; the 44 new checks are deferred; errors preserve output |
| `tests/collect.py` | Additive candidate indexing preserves generic/fixed peer order, guards, repeated binders, fallback facts, atom kinds and strict ordinary ambiguity |
| `tests/iteration.py` | Batched unfold/fold lifetimes: output/state roots, immutable shared tails, persistent environment indexes, nested replacement and rejection/budget contracts; dynamic and frozen modes |
| `tests/allocation.py` | Cross-language static allocation facts, lexical pruning, site conflicts, committed source identity, loop entry slots and unevaluated literal allocation; dynamic and frozen C11 modes |
| `tests/name_scope.py` | Seven generic immutable scope contracts: stable declaration identities, child snapshots, namespace separation and visible/local lookup |
| `tests/c11_tags.py` | C11 tag, enum and ordinary declaration points, lexical/prototype identities, incomplete-type constraints and per-token name reads; O0/O2 reference-checked sources and preserved failed output |
| `tests/tree_perf.py` | Serial, identical-rule measurements of wide/deep traversal, replaced scratch states, sparse unfolding and fold accumulation; time and peak commit |
| `tests/cli_logging.py` | Standard-library log levels, stderr diagnostics, unchanged eval stdout and artifact completion logs |
| `tests/interpreter_perf.py` | Isolated eval-only collection scaling with separate STX loading control, identical before/after rules, serial samples, time and peak commit |
| `tests/storage_perf.py` | Same-core object-image/window comparison, optional before/after compiler selection; serial O2 builds with actual execution and immutable rule snapshots; measures compiler time and commit |
| `tests/c11_conformance.py` | 157 clause-tagged C11 inputs at O0/O2, reference Clang, auto/register constraints, compound-literal lifetime, 127 parameters, address relocations and 8192-element nested-callback retention; dynamic and frozen modes; reports the pending full-support queue; not a certification suite |
| `tests/c11_specifiers.py` | 73 declaration inputs: interleaved/repeated specifiers, typedef boundaries, pointer qualifier compositions, storage/inline/alignment constraints and hosted main; independent strict C11 reference, O0/O2 and frozen modes |
| `tests/c11_generic.py` | 74 generic-selection inputs and 4 volatile IR checks: selected value categories, no controlling/unselected evaluation, recursive compatible types, ambiguous matches and required diagnostics; O0/O2 and frozen modes |
| `tests/c11_initializers.py` | 109 inputs: current-object traversal, brace elision, nested/chained designators, overwriting, aggregate evaluation, strings and unknown array inference including self-reference; O0/O2 strict reference and frozen modes |
| `tests/c11_declaration_model.py` | 49 inputs: immutable declaration views, recursive composite types, block extern/prototypes, incomplete result declarations, old-style/default-promotion ABI, expression tag points and required diagnostics; O0/O2 and frozen modes |
| `tests/c11_nonprototype_abi.py` | Five independent Windows x64 assembly oracles: unprototyped float/double calls duplicate XMM values to first/second/fourth GP registers, including a loaded function pointer; O0/O2, MSVC caller reference and frozen modes |
| `tests/c11_full_support.py` | Bounded full-plan gate across dynamic/frozen modes, pending features, system headers and unchanged projects; missing support or outstanding work items prevents completion |
| `tests/full_support_guard.py` | Ten reuse-evidence contracts: stale inputs, edited reports/logs, altered arguments, incomplete queues and waived failures are rejected |
| `tests/c11_static_literals.py` | 59 static literal/address inputs: distinct objects, nested initializers, symbolic offsets, pointer-condition truth, qualified casts, local static identities and declaration-point snapshots; O0/O2 and frozen modes |
| `tests/c11_temporaries.py` | 40 expression inputs: returned/assigned/conditional/comma aggregate members, full-expression temporaries, call-frame isolation, unevaluated operands, cast constraints and integer/pointer conversions; O0/O2 plus volatile MLIR checks, dynamic and frozen modes |
| `tests/c11_headers.py` | Explicit baseline for all 29 actual system C11 headers at O0/O2; bounded independent jobs; unsupported interfaces remain failures and are not counted as expected passes |
| `tests/c11_support.py` | Explicit pending-feature baseline tied to support work items; uses the same guarded clause runner and reports compile rejection and accepted wrong runtime behavior as failures |
| `tests/process_guard.py` | Concurrent output handle isolation, child-process denial and cleanup after a guarded timeout |
| `tests/syntax_bind.py` | Syntax-action lexical locals, nested destructuring, capture shadowing, initializer scope, repeated binders and rejection parity in dynamic and frozen modes |
| `tests/frozen_snapshot_test.py` | Frozen provenance rejects pending builds, stale generator/rules/generated source/backend/artifacts before parity claims |
| `tests/parser_perf.py` | Same-input baseline/current parser timing and peak commit for 2003 rules, recursive prefixes and real system stdio parsing; asserts identical AST hashes |
| `tests/c11_stress.py` | 12 real C11/system-CRT probes including nested/designated initialization, unchanged pinned TinyExpr and cJSON; incomplete language features remain failures |
| `tests/c11_composition.py` | Clang-checked O0/O2 union/anonymous-member/FAM layout, enum constants, switch/goto, compound bit/shift assignment, SDK warning pragmas and symbol-policy combinations; diagnostics and failed-output preservation |
| `tests/dialect_debug.py` | 232 adversarial B/Pascal/C11/BASIC dialect regressions (28 B, 24 Pascal, 43 C11, 21 BASIC fixtures at O0 and O2): word-addressing and octal constants, Pascal scoping/for/case, C11 null-pointer/sizeof constraints, and BASIC line-number control flow, arrays, DATA/READ, GOSUB, DEF FN and INPUT (fed through the harness stdin channel); C11 fixtures cross-checked against a reference Clang; asserts unchanged rule fingerprints |
| `tests/rule_tools.py` | Shared object layout, 10,000-element and 2,048-level iterative tree folds, caller-defined traversal boundaries and CFG label reachability; dynamic and frozen modes |
| `tests/invariants.py` | 19 boundary cases: laziness, regions, paths, NUL, output preservation |
| `tests/backend.py` | 6 source-to-backend cases: grammar equivalence, MLIR folding, O0/O3 executables, IRDL |
| `tools/mlir/test_backend.py` | 9 direct native backend cases including affine fusion and path protection |
| `tests/native_backend.py` | 28 native artifact, CFG, plugin, DLL-symbol, bounds, symbolic initializer, failure cleanup, volatile and escaped storage cases; 30 with both frozen compilers |
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
the clause, scope, composition and allocation checks without loading the C11
rule files at runtime. Add `-C11Stress` for unchanged real-project checks in
both dynamic and frozen modes. The frozen manifest is checked before and
after each suite; stale or unfinished builds cannot establish parity.
`test.ps1 -FrontendAot` freezes the
iteration lifetime contracts and shared layout/tree/CFG rule tools as well as
the frontend infrastructure.
# 普通语言库组合

`python tests/emergence.py` 验证标准方言的结构体、泛型、枚举和模式、函数值与闭包、普通函数的所有权/借用、数组和向量、范围控制流及 defer。O0/O2 运行、非法程序、越界和清理顺序均在禁止子进程、PATH 为空的 Windows Job 中完成。完整工程额外组合本地规则、自定义类型和 CRT 链接。

`python tests/emergence.py --compiler target/specialized-emergence/target/naru.exe --frozen` 用同一套源程序验证整个组合后的 AOT 编译器；冻结方式见 `docs/rule-libraries.md`。

`python tests/operators.py` 验证用户声明的运算符、异类型参数、独立结果类型、所有权/借用、字面量选择、动态库候选、项目引用和冲突诊断。传入 `--compiler <frozen.exe> --frozen` 验证冻结及动态规则的混合装载；小组冻结可加 `--minimal`，追加标准库可用 `--overlay-standard`。

`tests/c11_language_features.py` 为最终统一验收准备了 ISO inline／`_Noreturn`、TLS、固定数组参数说明符、UCN 和 UTF／宽字符用例。跨翻译单元用例的每个对象都由 Naru 编译，随后由进程内后端链接；LLVM 属性检查使用 O0，避免优化删除未调用函数。2026-10-13 起按用户要求暂不运行构建、冻结或测试。这里登记的是待执行的输入，不能作为通过证据。

`tests/c11_vm_layout.py` 登记 89 个 VLA／VM、位域和 `_Alignas` 成员输入，复用严格 C11、实际 CRT 的独立参考对照。它检查源语言副作用、步长、跳转诊断、位域相邻存储和真实成员布局，未在这一实现批次执行。新规则加入总验收闭包后须重建核心／后端、更新锁文件并冻结最终快照。

`tests/c11_atomics.py`、`tests/c11_abi.py`、`tests/c11_abi_interop.py`、`tests/c11_complex.py` 和 `tests/c11_header_features.py` 分别登记原子 62 项、ABI 35 项、真实独立 C 对象互操作 22 组、复数 44 项与头文件查找 21 项。仅登记源码输入，全部等待最后统一验收。标准头使用实际 SDK／LLVM 资源文件；参考编译器只生成验收对照对象，不参与 Naru 编译实现。

`tests/c11_fenv.py` 另登记 25 个浮点环境输入，覆盖真实 UCRT `fenv.h`、动态舍入、无用结果的异常、转换、NaN、原子／复数和跨翻译单元 `selectany`。有序 IR 区域需要重建原生后端；这些输入没有执行，强制 CAS 失败、多线程和硬件陷阱也没有验收。总验收队列现为 26 个套件。

`tests/c11_system_control.py` 与 `tests/c11_threads.py` 各登记 22 个系统控制／线程输入，复用真实 MSVC 头和运行库。总队列现为 26 个套件；均未运行。跨编译器 ABI 队列新增 3 组对齐类型，共 22 组。

`tests/c11_library_contract.py` 登记 31 个实际头／库契约输入，含六个可取地址原子函数、跨文件身份、全部原子类型别名、66 个复数接口的类型、ISO 构造宏与实际 UCRT tgmath。参考头视图只映射安装的原文件；显式载体参考源码／资源头支持 TU 均记录用途与哈希，从不交给 Naru。总队列现为 27 个套件。本批次仍未执行编译或测试。

`tests/c11_sdk_wide.py` 登记 42 个真实 SDK／宽字符输入；`tests/c11_preprocessor.py` 登记 54 个宏与 pragma 输入。实际 UCRT 的 fwide 方向缺陷保持必过反例，参考 CRT 的相同失败不能当作标准正确性。这里只完成源码与静态结构检查，全部等待统一构建／冻结／验收。

`tests/c11_packing.py` 登记 50 个目标 packing／稳定翻译时间输入，包括联合体内嵌套 packed 指针的必过反例。`tests/c11_static_images.py` 再增加 31 个全局镜像、位域、初始化覆盖及 TLS 输入；独立 ABI 对象对照随后增加原生原子组，当前为 32 组。参考编译与 Naru 使用相同的逐项翻译环境，Naru 编译依旧禁止子进程且 PATH 为空。上述两批队列为 31 项，尚未执行。

`tests/c11_atomic_alignment.py` 新增 39 个原子地址协议／类型查询输入；`tests/storage.py` 增加 12 个通用内存分派输入。packed 对象在 Naru 输入中强制未对齐，参考 Clang 明确使用自然对齐对象，只对照操作语义，不据此推断外部未对齐 helper ABI。总验收队列现为 32 项；新源码仍等待统一构建、冻结及验收。

`python tests/vyx_dist_compat.py` 独立验证宿主 SDK：StringBuilder、字符串字典键的生命周期、2048/2049 个函数的具名模块，以及跨 2048 个槽位重复借用的内存峰值。它不运行 Naru，也不计入 C11 支持度；失败保持失败，并在 `target/vyx-dist-compat.json` 记录 SDK 哈希与原始日志。结果中的 `1000000` 是一次无循环内分配的借用压力样例，其内存数值单独报告，不以程序返回正确代替内存验收。

C11 资源头对齐扩展新增 5 个输入：真实 `max_align_t`、GNU 成员对齐、重复对齐合并、类型 `__alignof__` 与非法对齐诊断。规则位于 `dialects/c11/gnu_attributes.stx`，仍由 `tests/c11_header_features.py` 的原有内存、参考编译器和子进程限制验收。
