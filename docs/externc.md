# C interop rules

`dialects/externc.stx` imports base, types and numbers and extends their qualified
relations. The source program needs no rule imports:

```text
extern "C" {
    fn puts(text: *char) -> i32;
}
fn greeting() -> i32 {
    return puts("hello from Naru");
}
```

Use the project in `examples/ffi` to build an executable directly:

```powershell
.\target\naru.exe build --project examples\ffi
& .\examples\ffi\target\ffi-demo.exe
```

That project references exported base/externc dialects and selects
`[link] runtime = "crt-static"`. Naru discovers installed MSVC/Windows SDK
libraries and invokes LLD in process. Declaring `puts` still requires its
implementation; runtime selection supplies the CRT libraries automatically.
See [project and link configuration](projects.md) for external objects and libraries.
An explicit equivalent is:

```powershell
.\target\naru.exe build greeting.nru --rules dialects\externc.stx --unit program --relation base.emit_program --target exe --runtime crt-static -o target\greeting.exe
```

Alternatively compile an object for a host application to link:

```powershell
.\target\naru.exe build greeting.nru --rules dialects\externc.stx --unit program --relation emit_program --target object -o target\greeting.obj
```

Object generation and executable linking remain entirely in process. The
default freestanding runtime omits CRT startup and libraries; select a CRT
runtime for C standard-library calls. These modes need the library files,
but do not need external compiler or linker executables at Naru build time.

The library supports C scalar declarations for signed/unsigned 8, 16, 32 and
64-bit integers, f32, f64, char, opaque `ptr` and typed `*T` pointers. Source
`char` preserves a distinct semantic type with byte literals 0..255; arithmetic
signedness is not inferred from the target. Pointer representations are LLVM
opaque pointers. Scalar calls have been executed against an independent C
harness on Windows x64 at O0 and O2; other targets may need additional ABI rules.
Struct layout, varargs, void results, dereference and pointer arithmetic are
not implemented by this library.

String literals have natural type `*char`, and may be checked as `ptr`. They
become immutable UTF-8 globals ending in NUL, deduplicated by content across
the entire program. Empty strings, quotes, backslashes, newline, CR and tab are
supported. Embedded NUL and the `\0` source escape are rejected by the core
lexer. String lowering requires the program emitter so static storage can be
prepared before type checking. `null` can take an expected pointer type, and
explicit `as` casts can convert between raw and typed opaque pointers.

When extending these libraries, qualify effect definitions:

```text
mod my_extension;
use base;
use types;
effect types.repr(MyType()) => "i32";
effect base.lower(Typed(MyType(), MyValue($n)), $environment)
    => mlir.op("arith.constant", [], ["i32"], [Attr("value", $n, "i32")], []);
```

An unqualified `effect lower` would create `my_extension.lower`, which base's
emitter does not call. All rule bodies are linked when the library loads, so an
undefined call such as `mlir.cstring` fails even when the current user program
contains no string literals. C strings here use ordinary `llvm.mlir.global`
and `llvm.mlir.addressof` construction rules instead.

Run `python tests/externc.py` for native calls, type errors and static-storage
checks. `test.ps1 -Aot` also builds and checks a frozen compiler containing this
library, without loading STX files at runtime.
