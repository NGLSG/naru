# Third-party components and historical materials

Original Naru work uses MIT OR Apache-2.0. The following components retain their own licenses and notices.

| Component | Use | License and notice |
| --- | --- | --- |
| Vyx runtime and standard logger | Frontend and `packages/vyx-logger/` adaptation | MIT OR Apache-2.0; logger notices in that directory, SDK notices in binary `licenses/Vyx*` |
| LLVM, MLIR, Clang and LLD | Backend, resource headers and target passes | Apache-2.0 WITH LLVM-exception; binary `licenses/LLVM.txt` |
| spdlog 1.14.1 | Logging | MIT; binary `licenses/spdlog.txt` |
| fmt | Bundled with spdlog | Binary `licenses/fmt.txt` |
| TinyExpr | Real-project tests | Zlib; `tests/c11/projects/tinyexpr/LICENSE` |
| cJSON | Real-project tests | MIT; `tests/c11/projects/cjson/LICENSE` |

Build dependencies are excluded from source previews. Binary packages include the relevant notices. MSVC/Windows SDK libraries are read from the user's installation.

## Historical materials

`historical/**/INDEX.md` records authorship, version and provenance. Original manuals, downloaded pages and extracted copies retain their original rights.

The public source contains archive cards and research notes. Historical originals and extracted copies are managed separately.
