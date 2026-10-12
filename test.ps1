param([switch]$Aot, [switch]$ComposedAot, [switch]$C11Stress, [switch]$FrontendAot, [switch]$C11Aot)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath 'target\naru.exe')) {
        throw 'Build the compiler first: .\build.ps1 -Release'
    }
    & python tests/freeze_driver.py
    if ($LASTEXITCODE -ne 0) { throw 'Freeze build driver checks failed' }
    & (Join-Path $PSScriptRoot 'backend\native\plugins\build.ps1')
    $naruSuites = @(
        'tests/run.py',
        'tests/rules.py',
        'tests/exact_float.py',
        'tests/storage.py',
        'tests/base_flow.py',
        'tests/emergence.py',
        'tests/operators.py',
        'tests/externc.py',
        'tests/projects.py',
        'tests/packages.py',
        'tests/modules.py',
        'tests/entry_files.py',
        'tests/c11_declarations.py',
        'tests/c11_conformance.py',
        'tests/c11_scopes.py',
        'tests/c11_composition.py',
        'tests/c11_layout.py',
        'tests/dialect_debug.py',
        'tests/rule_tools.py',
        'tests/tree_perf.py',
        'tests/frontend_infra.py',
        'tests/invariants.py',
        'tests/backend.py',
        'tools/mlir/test_backend.py',
        'tests/native_backend.py'
    )
    foreach ($naruSuite in $naruSuites) {
        & python $naruSuite
        if ($LASTEXITCODE -ne 0) { throw "Test suite failed: $naruSuite" }
    }
    if ($C11Stress) {
        & python tests/c11_stress.py
        if ($LASTEXITCODE -ne 0) { throw 'C11 acceptance remains incomplete; see target/c11-stress.json' }
    }
    if ($Aot -or $C11Aot) {
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/c11.stx --jobs 1 --output target/specialized-c11
        if ($LASTEXITCODE -ne 0) { throw 'C11 rule specialization failed' }
        & python tests/c11_conformance.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-conformance-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 conformance checks failed' }
        & python tests/c11_scopes.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-scopes-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 scope checks failed' }
        & python tests/c11_composition.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-composition-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C rule composition checks failed' }
    }
    if ($Aot -or $FrontendAot) {
        & python tools/freeze/build.py --core target/naru.exe --rules tests/fixtures/rule_tools.stx --rules dialects/tree.stx --rules dialects/layout.stx --rules dialects/cfg.stx --rules dialects/base.stx --output target/specialized-rule-tools
        if ($LASTEXITCODE -ne 0) { throw 'Shared rule tool specialization failed' }
        & python tests/rule_tools.py --compiler target/specialized-rule-tools/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen shared rule tool checks failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/parse.stx --rules tests/fixtures/frontend_choices.stx --rules tests/fixtures/contextual_frontend.stx --rules tests/fixtures/frontend_infra.stx --rules tests/fixtures/frontend_cache.stx --rules dialects/headers.stx --output target/specialized-frontend-infra
        if ($LASTEXITCODE -ne 0) { throw 'Frontend infrastructure specialization failed' }
        & python tests/frontend_infra.py --compiler target/specialized-frontend-infra/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen frontend infrastructure checks failed' }
    }
    if ($Aot -or $ComposedAot) {
        & python tools/freeze/build.py --core target/naru.exe --project examples/emergence --locked --output target/specialized-emergence
        if ($LASTEXITCODE -ne 0) { throw 'Composed language specialization failed' }
        & python tests/emergence.py --compiler target/specialized-emergence/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen composed language checks failed' }
        & python tests/operators.py --compiler target/specialized-emergence/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen operator and overlay checks failed' }
    }
    if ($Aot) {
        # These isolated outputs are acceptance fixtures. A normal project can
        # freeze one aggregate such as dialects/standard.stx instead.
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/base.stx --output target/specialized-base
        if ($LASTEXITCODE -ne 0) { throw 'Base rule specialization failed' }
        & python tests/base_flow.py --compiler target/specialized-base/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen base control-flow rules failed' }
        & python tools/freeze/build.py --core target/naru.exe --project examples/ffi --locked --output target/specialized-externc
        if ($LASTEXITCODE -ne 0) { throw 'Extern C rule specialization failed' }
        & python tests/externc.py --compiler target/specialized-externc/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen extern C rules failed' }
        & python tests/projects.py --compiler target/specialized-externc/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen project references failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/ownership.stx --rules dialects/unless.stx --rules dialects/loops.stx --output target/specialized-ownership
        if ($LASTEXITCODE -ne 0) { throw 'Ownership rule specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/base.stx --rules tools/freeze/semantics.stx --output target/specialized-tests
        if ($LASTEXITCODE -ne 0) { throw 'Effect rule specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/control_flow.stx --output target/specialized-control-flow
        if ($LASTEXITCODE -ne 0) { throw 'Control-flow rule specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules tests/fixtures/rule_contract.stx --output target/specialized-rule-contract
        if ($LASTEXITCODE -ne 0) { throw 'Rule contract specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/resources.stx --output target/specialized-resources
        if ($LASTEXITCODE -ne 0) { throw 'Resource ownership specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/money.stx --output target/specialized-money
        if ($LASTEXITCODE -ne 0) { throw 'Custom type specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/standard.stx --output target/specialized-standard
        if ($LASTEXITCODE -ne 0) { throw 'Composed standard dialect specialization failed' }
        & target/specialized-standard/target/naru.exe check examples/ownership/unless_valid.nru --relation ownership.analyze
        if ($LASTEXITCODE -ne 0) { throw 'Composed standard dialect check failed' }
        & target/specialized-standard/target/naru.exe check tests/fixtures/composed.nru --relation standard.analyze --unit program
        if ($LASTEXITCODE -ne 0) { throw 'Composed mixed-program facade check failed' }
        & python tests/rules.py --frozen target/specialized-base/target/naru.exe --frozen-rules target/specialized-rule-contract/target/naru.exe --frozen-resources target/specialized-resources/target/naru.exe --frozen-money target/specialized-money/target/naru.exe
        if ($LASTEXITCODE -ne 0) { throw 'Dynamic/AOT rule and type contract failed' }
        & python tests/parity.py
        if ($LASTEXITCODE -ne 0) { throw 'Dynamic/AOT source parity failed' }
        & python tools/freeze/test_frozen.py --core target/naru.exe --frozen target/specialized-tests/target/naru.exe --rules dialects/base.stx --rules tools/freeze/semantics.stx --report tools/freeze/verification.json
        if ($LASTEXITCODE -ne 0) { throw 'Dynamic/AOT effect parity failed' }
        & python tests/native_backend.py --frozen target/specialized-base/target/naru.exe --frozen-cfg target/specialized-control-flow/target/naru.exe
        if ($LASTEXITCODE -ne 0) { throw 'Frozen in-process backend verification failed' }
    }
} finally { Pop-Location }
