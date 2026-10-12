# Naru in-process MLIR backend

Naru 0.2 embeds MLIR, LLVM and LLD in `naru_mlir_backend.dll`. The Vyx frontend
loads this library in its own process through `src/mlir_loader.c`. Its C ABI is
in `backend/native/naru_mlir.h`; `src/mlir.vyx` directly constructs MLIR operations
from the rule-generated graph. Only explicit `naru opt` tooling input parses a
whole MLIR text module. Leaf type and attribute descriptors use MLIR parsers.

The frontend uses Vyx LLVM 22. The backend uses LLVM/MLIR 24.0.0 revision
`19d3b2d2887ccd8fae4d091dc6c29d6b6d9e2b98` and matching LLD. C++ objects never cross
the Vyx boundary. Opaque handles belong to one session, which owns the context,
module, builders, regions and blocks. Strings use UTF-8 and explicit byte lengths.

## Developer build and runtime distribution

```powershell
python tools/mlir/bootstrap.py
.\build.ps1 -Release
.\backend\native\plugins\build.ps1
.\package.ps1
```

The bootstrap script downloads the fixed SDK published by llvm/eudsl, checks
SHA256 and extracts it under `.tools/mlir`. Its archive is about 563 MB:

```text
mlir_windows_amd64_20261009+19d3b2d28.tar.gz
SHA256 a14f88bb2bb099505df1b01a06d02935807d5c325e7fa6394a5de8b5febfb6be
```

Clang, CMake, Ninja, Python 3.11+, Git and Visual Studio C++ build tools are
needed for developer builds. `backend/native/lld/build.py` prepares LLD from
the exact backend revision, with the SDK's static CRT, assertions and RTTI
configuration. `backend/native/build-native.ps1` links the static libraries into
the DLL and produces `target/naru_mlir_backend.lib` for native plugins.

The compiled runtime needs `naru.exe` and `naru_mlir_backend.dll` beside it,
plus the selected rules and target data. It does not invoke Python, Clang,
mlir-opt, mlir-translate or lld-link. Override the DLL location with
`--backend-library` or `NARU_MLIR_BACKEND`.

## Commands and pipeline

```powershell
.\target\naru.exe build examples\answer.nru --target exe -o target\answer.exe
.\target\naru.exe opt backend\examples\fold.mlir --target llvm-ir -o target\answer.ll
.\target\naru.exe opt backend\examples\fusion.mlir --target backend\fusion-target.json -o target\fusion.mlir
```

| Option | Meaning |
| --- | --- |
| `--target` | `mlir`, `bytecode`, `llvm-ir`, `object`, `exe`, or a target JSON path |
| `--pass-pipeline` | MLIR optimization pipeline; default `builtin.module(canonicalize,cse)` |
| `--irdl` | Load an IRDL module before building or parsing program IR; repeatable |
| `--dialect-plugin`, `--pass-plugin` | Load native MLIR plugins; repeatable |
| `--lowering-pipeline` | Replace CPU conversion; default SCF to CF, convert to LLVM, reconcile casts |
| `--opt-level` | LLVM O0/O1/O2/O3; `s`/`z` use O2 with optsize/minsize function attributes |
| `--native-entry` | Windows freestanding linker entry; default `main` |
| `--runtime` | `freestanding` (default), `crt-static`, or `crt-dynamic` |
| `--link-object`, `--link-library`, `--library-path` | Additional objects, libraries and search directories; repeatable |
| `--subsystem` | Windows `console` (default) or `windows` |
| `--vc-tools-dir`, `--windows-sdk-dir`, `--windows-sdk-version` | Override native discovery of installed MSVC/SDK libraries |
| `--triple`, `--cpu`, `--features` | LLVM target machine selection |
| `--report` | JSON result, version, pipeline, optimization level and diagnostics |

`--entry` selects the Naru grammar category; it is distinct from `--native-entry`.
`emit` verifies real MLIR and prints generic operation syntax without optimizing.
`build` verifies the module and each pass result, then writes the requested
artifact. CPU output runs MLIR conversion, LLVM's PassBuilder optimization and
TargetMachine object emission. EXE output invokes LLD COFF's library entry point
under a linker mutex. Freestanding mode uses an explicit entry without CRT.
CRT modes discover installed MSVC/Windows SDK libraries through native LLVM
driver APIs and use CRT startup. Extra objects and libraries can be configured
in projects, target JSON or CLI options; see [project configuration](../docs/projects.md).
No compiler, linker or discovery subprocess is spawned. Arbitrary raw linker
flags are not accepted. Other LLVM targets can emit
objects; executable linking for those targets is not implemented.

Successful output replaces the final path atomically. Failures preserve existing
artifacts. Output and report paths cannot overwrite source inputs, transitive
rules, manifests, lock files, link objects/libraries, target profiles, IRDL files
or plugins, including hard-link aliases.
Unregistered dialects and operations, invalid attributes and unknown pass names
are failures. The backend never enables allow-unregistered-dialect.
Repeated extension files, including hard-link aliases, load once. Conflicting
IRDL definitions of an already registered dialect produce a normal diagnostic.

## Rule-facing construction API

```text
mlir.op(name, operands, result_types, attributes, regions[, successors])
mlir.region(body)                  // lazy isolated region body
mlir.block(argument_types)        // creates a block with SSA arguments
mlir.block_arg(block, index)
mlir.in_block(block, body)         // lazy body with block-local insertion
mlir.region_blocks(blocks)
```

Operations return one SSA value or a list of results. Attributes are ordinary
`Attr(name,value[,type])` and `RawAttr(name,text)` terms. The importer predeclares
all blocks and arguments in a region, then constructs its operations and resolves
successors; MLIR checks dominance and branch signatures. `dialects/control_flow.stx`
defines a four-block loop with a backedge through these generic APIs.

`mlir.region_blocks([])` creates a region with zero blocks, as required for
external `func.func` declarations and initialized `llvm.mlir.global` operations.
This differs from `mlir.region(body)`, which creates an implicit block even if
the body emits no operations. There is no `mlir.cstring` builtin: a rule library
can emit a static LLVM global and an address-of operation with the generic API.

CPU lowering accepts `Attr("naru.llvm.dll_storage_class", "export"|"import")`
on LLVM functions, globals and aliases. This namespaced symbol fact is applied
to LLVM GlobalValues before optimization, preserving COFF exports and imported
references independently of a source language. It requires an external symbol
on a Windows target; imports must be declarations. Wrong types, unrecognized
values, internal symbols and non-Windows targets are diagnostics. MLIR-only
outputs preserve the fact for a later CPU lowering. Native tests inspect both
optimized LLVM IR and COFF export directives and check failure preservation.

## Custom dialects and pass plugins

`backend/examples/device.irdl.mlir` registers custom `tile<f32>` types and device
operations. Its operand and attribute constraints are verified by MLIR IRDL.

```powershell
.\target\naru.exe build examples\device.nru --rules dialects\custom_device.stx --target backend\device-target.json -o target\device.mlir
.\target\naru.exe build examples\native_device.nru --rules dialects\native_device.stx --dialect-plugin target\naru_device_plugin.dll -o target\native-device.mlir
.\target\naru.exe build examples\answer.nru --pass-plugin target\naru_mark_plugin.dll --pass-pipeline 'builtin.module(naru-test-mark,canonicalize,cse)' -o target\marked.mlir
```

Native plugins must match this backend's revision, CRT, assertions and RTTI.
They link `naru_mlir_backend.lib`, avoiding a second static copy of MLIR's registry.
The bundled `naru_plugin.h` and locally generated TypeID header overlay import
shared Windows TypeID data correctly, including TypeID<void>. Include the helper
before MLIR headers; declare plugin-owned types afterward. Samples exercise
host ModuleOp/IntegerAttr identity, pass registration, dynamic dialect registration
and operation verification. The exported C++ support subset covers core IR,
passes, transforms, arith and func; additional dialect APIs may require extending
`export_symbols.py` and the imported header set. The pure C frontend ABI remains
independent of these native plugin details.

A target profile selects an artifact, registered extensions and a pass pipeline:

```json
{
  "artifact": "mlir",
  "pipeline": "builtin.module(my-device-pass,canonicalize)",
  "irdl": ["my-device.irdl.mlir"],
  "dialect_plugins": ["my-device.dll"],
  "pass_plugins": ["my-device-passes.dll"]
}
```

Extension paths in profiles are relative to the profile. Explicit CLI pipeline
options override profile settings. Device operations can remain in MLIR or
bytecode and never need to pass through LLVM. External emitter commands are
rejected by this backend; target code generation can be implemented in native
plugins/passes. Device-specific optimization semantics still require their
interfaces, rewrite patterns and passes.

## Acceptance

`python tools/mlir/test_backend.py --report backend/verification.json` covers
constant folding, executable exit 42, affine loop fusion with temporary buffer
elimination, custom IRDL type/attribute checks and input/output protection.
`python tests/native_backend.py` covers all artifact kinds, CFG execution,
size preferences, native plugins, integer overflow and failure reports.
Both suites run the compiler in a Windows Job with ActiveProcessLimit=1 and
empty PATH. A compiler that tries to create a child compiler, optimizer or
linker cannot pass these checks. Reports record `backend: in-process` and
`processes_spawned: 0`; the Job restriction supplies independent evidence.

These fixtures establish actual correctness and selected optimization effects,
not a general throughput benchmark or a complete device runtime.
