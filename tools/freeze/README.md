# Native syntax and effect specialization

`naru freeze --rules dialects/base.stx -o specialized.vyx` emits Vyx code for
the linked rule group. Syntax templates become unrolled token/capture checks;
syntax result trees become direct constructors. Effect patterns become native
shape checks and bindings, and static RHS expressions become native functions.
Arena and rule metadata initializers are generated in bounded chunks to avoid
feeding one enormous SSA graph to the host optimizer.
There is no runtime STX reparsing or pattern/RHS interpreter walk for these
statically known rules.

Shared Pratt scheduling still handles grammar categories, precedence and
associativity using initialized metadata. Dynamically shaped captured terms can
use the common evaluator; their effect calls route to the native dispatcher.
This is rule specialization, not allocation-free compilation. Lazy `choose`,
`seq`, `mlir.region` and `mlir.in_block` retain dynamic semantics and restore
insertion context. The same generic MLIR builder is used by both compiler kinds.

```powershell
python tools/freeze/build.py --core target/naru.exe --rules dialects/base.stx --output target/specialized-base
.\target\specialized-base\target\naru.exe build examples\answer.nru --target exe -o target\frozen-answer.exe
python tools/freeze/build.py --core target/naru.exe --rules dialects/standard.stx --output target/specialized-standard
.\target\specialized-standard\target\naru.exe check examples\ownership\unless_valid.nru --relation ownership.analyze
```

The script stages a separate Vyx project, substitutes `src/specialized.vyx` and
builds it with Vyx. `--sdk`, `VYX_SDK` or the configured default select the SDK.
`--compiler-opt-level 0|1|2|3` controls optimization of the compiler's Vyx
implementation (default 2), independently of the generated program's
`--opt-level`. Level 0 is useful for validating a large rule group while
investigating costly host optimization; it still compiles rules to native code.
The resulting compiler embeds its dialect group and accepts `--rules` to
append new modules. Frozen rules keep native matchers and bodies, while appended
rules use the dynamic evaluator in a shared ambiguity/fallback decision.
Identical frozen modules may be selected again; changed contents are rejected.
Projects may add dialects while retaining the embedded dependency closure.
The augmented group can itself be frozen into another compiler.
`naru-frozen-project.json` fingerprints transitive rule dependencies, generated
code, core compiler, Vyx compiler and deployed backend DLL. `artifact.txt`
records the executable path reported by Vyx.
Builds default to four Vyx workers (`-j4`); `--jobs 1..64` configures concurrency.
Use `--jobs 1` for serial builds when memory is tight. The manifest records the
worker setting, build time and sampled process-tree private commit. Sampling
errors are recorded separately and never hide the compiler's exit status; an
unavailable peak is null rather than zero. Build metrics describe that invocation,
which may be a cache hit. The SDK itself is not rebuilt.

The in-process backend DLL is copied beside the frozen executable; target
profiles and IRDL data are also staged. The frozen compiler needs neither the
source SDK installation nor Python nor external MLIR tools at runtime. The
builder updates only marked frozen-project directories. Previously generated
legacy tool directories are removed only after resolving and validating their
paths under that owned output directory.

`.\test.ps1 -Aot` builds base, ownership, effect-test, control-flow, general
rule-contract, multi-resource borrowing, custom numeric-type and composed
standard-dialect compilers and checks
parse trees, failure diagnostics, ownership fixed points, lazy evaluation,
repeated captures, recursion, ambiguity, region isolation and native MLIR
emission against dynamic loading. It also freezes the generic rule contract and
checks guards, explicit fallback priority, lexical binders, exact arithmetic,
type rules, custom types, and a program containing forward calls at O0/O3. It
compares the 155 public rule/type contracts with the dynamic compiler and checks
that custom resource and `money` libraries work without loading `.stx` files.
Native backend tests also run the frozen
compiler from another directory with empty PATH in a Job that prohibits child
processes. `tools/freeze/verification.json` records effect parity results.
`tools/freeze/measure.py` is a small interleaved whole-process timing tool; its
results include startup and initialization, and do not establish parser-only
speedups or mature compilation throughput.
For a whole-program relation, pass `--unit program --relation standard.emit_program`
alongside the source and rule paths.

`test.ps1 -C11Aot` freezes the complete selected C rule group into one compiler
and runs `tests/c11_composition.py --frozen` against it. The programs still use
ordinary C source and the installed system headers/CRT. This checks rule
execution and native-code parity for the supported features; it is not a C11
conformance claim. `test.ps1 -FrontendAot` also freezes the shared layout,
iterative tree traversal and CFG tools and runs their public checks without
runtime rule paths.
