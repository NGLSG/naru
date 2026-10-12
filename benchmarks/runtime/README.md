# Ordinary-source runtime benchmarks

Every language supplies hand-written `kernel(n, seed)` and `main` functions.
Naru loads only `dialects/base.stx`; its `.nru` sources use normal functions,
parameters, calls, mutable variables, assignments, loops, arithmetic and casts.
There are no benchmark-specific `.stx` files and no injected MLIR.

```powershell
python benchmarks/runtime/run.py --samples 25
```

The runner builds each source with O2, validates its 32-bit return value against
an independent Python reference, then performs three warmups and 25 shuffled
sequential process runs. It compares the installed Windows toolchains, which
currently use different LLVM versions. Each executable may inline its ordinary
functions; no compiler gets a special noinline or manual unroll annotation.
All compilation and reference computation completes before timed runs begin.

`lcg` is a modular u32 recurrence. The runner tests 100 million and one billion
iterations. `mix` couples two states through multiply/add/XOR for 100 million
iterations, avoiding the LCG's simple affine recurrence composition. Both
workloads have no I/O; their return values prevent dead-code removal. Timing
includes Windows process startup, CRT startup where applicable, execution and
exit. The longer workloads reduce the relative startup contribution.

Results, every timing sample, exact build commands, compiler versions, rule
and source hashes, generated sources and LLVM IR are saved under
`target/base-runtime-benchmark`. Naru's unoptimized MLIR is also saved, and
the runner requires its optimized scalar loops to retain control flow with
no stack allocations, loads or stores. These are integer-compute benchmarks;
they do not measure compiler latency or establish a general language ranking.

The old `target/crosslang-lcg-runtime.json` is a backend-only experiment that
used an algorithm-specific rule. It is superseded by these frontend benchmarks.
