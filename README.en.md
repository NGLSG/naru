# Naru

[中文](README.md) · [Build](docs/building.md) · [Status](docs/status.md) · [Contribute](CONTRIBUTING.md)

Naru is an experimental AOT compiler written in Vyx. Its core provides rule evaluation, modules, toolchain support and an MLIR interface. `.stx` libraries define a language's syntax, types, ownership and compilation stages.

`fn`, `let`, structures and operators are library syntax. A project selects its dialects, then uses their syntax directly. Entry files may use `.nru`, `.c` or another extension. Libraries can be combined; conflicting peer matches produce an error.

The backend runs MLIR in process and supports custom dialects and passes. CPU targets use LLVM and LLD to produce native programs; device targets can retain their own IR. Rules can be loaded dynamically or AOT-compiled into a compiler.

The current version is **0.2.0-preview.1**, developed on **Windows x86_64**. C11 compatibility testing is incomplete. See [status](docs/status.md) for known issues.

## Example

```text
fn main() -> i32 {
    var total = 0;
    var i = 0;
    while i < 7 {
        total = total + i;
        i = i + 1;
    }
    return total * 2;
}
```

This program uses the [base dialect](dialects/base.stx). Its addition syntax is defined by a rule:

```text
syntax expr[50,left] `$a:expr + $b:expr` => Add($a, $b);
```

`syntax` produces structured terms; `effect` relations analyze and lower them. A library can extend the meaning of existing syntax or supply its own frontend. See the [rule system](docs/rule-system.md) and [library composition](docs/rule-libraries.md).

## Use a distribution

Run inside the extracted directory:

```powershell
.\naru.exe build --project .\Naru.toml --target exe -o .\target\answer.exe
& .\target\answer.exe
$LASTEXITCODE # 42
```

Keep the bundled rules, backend DLL, plugins and runtimes. The compiler requires neither Python nor an external compiler process. System CRT linking requires installed MSVC/Windows SDK libraries. Package tooling needs Python 3.11+, plus Git for Git sources.

## Build from source

Install a Vyx Windows LLVM 22 SDK and the [build dependencies](docs/building.md). In an x64 developer PowerShell:

```powershell
$env:VYX_SDK_ROOT = 'C:\SDK\vyx-sdk-windows-x86_64-llvm22'
python tools/mlir/bootstrap.py
.\build.ps1 -Release -Jobs 4
.\target\naru.exe build examples\answer.nru --target exe -o target\answer.exe
& .\target\answer.exe
```

The first build prepares a pinned MLIR SDK, LLD and logging dependencies. Use `-Jobs 1` on machines with limited memory.

## Libraries and the archive

- [dialects/](dialects/): base language, ownership, closures, coroutines, C11, B, Pascal, BASIC and shared libraries.
- [Composition example](examples/emergence/): several libraries used in one language.
- [Package manager](docs/packages.md): JSON registries, Git sources, dialect templates and dependency locks.
- [historical/](historical/): language versions, bibliographies and research notes.

Create a dialect library:

```powershell
.\naru.ps1 pkg init target\my-language --name my-language
.\naru.ps1 build --project target\my-language
```

## Development

```powershell
python tests/run.py
python tests/rules.py
python tests/iteration.py
```

See [tests/README.md](tests/README.md), [compiler architecture](docs/implementation.md) and [contribution guidance](CONTRIBUTING.md).

## License

Original Naru code, rules, examples and documentation use [MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE). See [THIRD_PARTY.md](THIRD_PARTY.md) for dependency and historical-material licenses. Source previews include archive cards and notes, but omit third-party historical originals.
