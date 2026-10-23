# Naru · Windows x86_64 preview

Naru is an AOT compiler with composable language rules and an in-process MLIR/LLVM/LLD backend.

Naru 是使用可组合语言规则的 AOT 编译器，后端在进程内运行。

## Run / 运行

```powershell
.\naru.exe build --project .\Naru.toml --target exe -o .\target\answer.exe
& .\target\answer.exe
$LASTEXITCODE # 42
```

Keep the DLL, rules, plugins and runtime directories together. System CRT linking requires installed MSVC/Windows SDK libraries. Package tooling needs Python 3.11+ and Git for Git sources.

保留 DLL、规则、插件和运行库目录。编译入口无需 Python；系统 CRT 链接需要本机 MSVC/Windows SDK 库。包管理器需要 Python 3.11+，获取 Git 包还需 Git。

- [Project configuration / 项目配置](docs/projects.md)
- [Package manager / 包管理](docs/packages.md)
- [Rule system / 规则系统](docs/rule-system.md)
- [Status and known issues / 状态与已知问题](docs/status.md)
- [Coroutines / 协程](docs/coro.md)

`naru-distribution.json` records the version and native artifacts. `SHA256SUMS` lists file hashes. Original Naru work uses MIT OR Apache-2.0; dependency notices are in `licenses/`. See [THIRD_PARTY.md](THIRD_PARTY.md).
