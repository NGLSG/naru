param([switch]$Aot, [switch]$ComposedAot, [switch]$C11Stress, [switch]$C11Full, [switch]$FrontendAot, [switch]$C11Aot, [switch]$CoroAot,
    [ValidateRange(1,64)][int]$Jobs = 4)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath 'target\naru.exe')) {
        throw 'Build the compiler first: .\build.ps1 -Release'
    }
    & python tests/freeze_driver.py
    if ($LASTEXITCODE -ne 0) { throw 'Freeze build driver checks failed' }
    & (Join-Path $PSScriptRoot 'backend\native\plugins\build.ps1')
    & (Join-Path $PSScriptRoot 'runtime\coro\build.ps1')
    $naruSuites = @(
        'tests/run.py',
        'tests/rules.py',
        'tests/exact_float.py',
        'tests/storage.py',
        'tests/collect.py',
        'tests/iteration.py',
        'tests/allocation.py',
        'tests/name_scope.py',
        'tests/cli_logging.py',
        'tests/process_guard.py',
        'tests/syntax_bind.py',
        'tests/frozen_snapshot_test.py',
        'tests/full_support_guard.py',
        'tests/base_flow.py',
        'tests/coro.py',
        'tests/tasks.py',
        'tests/coro_abi.py',
        'tests/emergence.py',
        'tests/operators.py',
        'tests/externc.py',
        'tests/projects.py',
        'tests/packages.py',
        'tests/modules.py',
        'tests/entry_files.py',
        'tests/c11_declarations.py',
        'tests/c11_conformance.py',
        'tests/c11_specifiers.py',
        'tests/c11_generic.py',
        'tests/c11_initializers.py',
        'tests/c11_declaration_model.py',
        'tests/c11_nonprototype_abi.py',
        'tests/rule_dependency_checks.py',
        'tests/c11_static_literals.py',
        'tests/c11_temporaries.py',
        'tests/c11_scopes.py',
        'tests/c11_tags.py',
        'tests/c11_composition.py',
        'tests/c11_layout.py',
        'tests/dialect_debug.py',
        'tests/rule_tools.py',
        'tests/frontend_infra.py',
        'tests/invariants.py',
        'tests/backend.py',
        'tools/mlir/test_backend.py',
        'tests/native_backend.py'
    )
    & python tools/test_parallel.py --jobs $Jobs @naruSuites
    if ($LASTEXITCODE -ne 0) { throw 'Acceptance suites failed; see target/parallel-tests.json' }
    & python tests/tree_perf.py
    if ($LASTEXITCODE -ne 0) { throw 'Rule interpreter traversal checks failed' }
    if ($C11Stress) {
        & python tests/c11_stress.py
        if ($LASTEXITCODE -ne 0) { throw 'C11 acceptance remains incomplete; see target/c11-stress.json' }
    }
    if ($Aot -or $C11Aot -or $C11Full) {
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/c11.stx --jobs $Jobs --output target/specialized-c11
        if ($LASTEXITCODE -ne 0) { throw 'C11 rule specialization failed' }
        & python tests/c11_conformance.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-conformance-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 conformance checks failed' }
        & python tests/c11_specifiers.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-specifiers-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 specifier checks failed' }
        & python tests/c11_generic.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-generic-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 generic selection checks failed' }
        & python tests/c11_initializers.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-initializers-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 initializer traversal checks failed' }
        & python tests/c11_declaration_model.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-declaration-model-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 declaration model checks failed' }
        & python tests/c11_nonprototype_abi.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-nonprototype-abi-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 no-prototype ABI checks failed' }
        & python tests/c11_static_literals.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-static-literals-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 static literal checks failed' }
        & python tests/c11_temporaries.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-temporaries-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 temporary checks failed' }
        & python tests/c11_scopes.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-scopes-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 scope checks failed' }
        & python tests/c11_tags.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-tags-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 tag and enum checks failed' }
        & python tests/c11_composition.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-composition-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen C rule composition checks failed' }
        & python tests/allocation.py --compiler target/specialized-c11/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen allocation rule composition checks failed' }
        & python tests/name_scope.py --compiler target/specialized-c11/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen name scope rule composition checks failed' }
        if ($C11Stress) {
            & python tests/c11_stress.py --compiler target/specialized-c11/target/naru.exe --frozen --report target/c11-stress-frozen.json
            if ($LASTEXITCODE -ne 0) { throw 'Frozen C11 real project checks failed' }
        }
    }
    if ($C11Full) {
        & python tests/c11_full_support.py --compiler target/naru.exe --frozen-compiler target/specialized-c11/target/naru.exe --jobs $Jobs
        if ($LASTEXITCODE -ne 0) { throw 'Full C11 support gate remains incomplete; see target/c11-full-support.json' }
    }
    if ($Aot -or $FrontendAot) {
        & python tools/freeze/build.py --core target/naru.exe --rules tests/fixtures/syntax_bind.stx --jobs $Jobs --output target/specialized-syntax-bind
        if ($LASTEXITCODE -ne 0) { throw 'Syntax binding rule specialization failed' }
        & python tests/syntax_bind.py --compiler target/specialized-syntax-bind/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen syntax binding checks failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules tests/fixtures/iteration_contract.stx --jobs $Jobs --output target/specialized-iteration
        if ($LASTEXITCODE -ne 0) { throw 'Iteration lifetime rule specialization failed' }
        & python tests/iteration.py --compiler target/specialized-iteration/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen iteration lifetime checks failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules tests/fixtures/rule_tools.stx --rules dialects/tree.stx --rules dialects/layout.stx --rules dialects/cfg.stx --rules dialects/base.stx --jobs $Jobs --output target/specialized-rule-tools
        if ($LASTEXITCODE -ne 0) { throw 'Shared rule tool specialization failed' }
        & python tests/rule_tools.py --compiler target/specialized-rule-tools/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen shared rule tool checks failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/parse.stx --rules tests/fixtures/frontend_choices.stx --rules tests/fixtures/contextual_frontend.stx --rules tests/fixtures/frontend_infra.stx --rules tests/fixtures/frontend_cache.stx --rules dialects/headers.stx --jobs $Jobs --output target/specialized-frontend-infra
        if ($LASTEXITCODE -ne 0) { throw 'Frontend infrastructure specialization failed' }
        & python tests/frontend_infra.py --compiler target/specialized-frontend-infra/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen frontend infrastructure checks failed' }
    }
    if ($Aot -or $CoroAot) {
        & python tools/freeze/build.py --core target/naru.exe --project examples/coro --locked --jobs $Jobs --output target/specialized-coro
        if ($LASTEXITCODE -ne 0) { throw 'Coroutine rule specialization failed' }
        & python tests/coro.py --compiler target/specialized-coro/target/naru.exe --frozen --report target/coro-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen coroutine checks failed' }
        & python tests/tasks.py --compiler target/specialized-coro/target/naru.exe --frozen --report target/tasks-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen async task checks failed' }
        & python tests/coro_abi.py --compiler target/specialized-coro/target/naru.exe --frozen --report target/coro-abi-frozen.json
        if ($LASTEXITCODE -ne 0) { throw 'Frozen coroutine module ABI checks failed' }
    }
    if ($Aot -or $ComposedAot) {
        & python tools/freeze/build.py --core target/naru.exe --project examples/emergence --locked --jobs $Jobs --output target/specialized-emergence
        if ($LASTEXITCODE -ne 0) { throw 'Composed language specialization failed' }
        & python tests/emergence.py --compiler target/specialized-emergence/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen composed language checks failed' }
        & python tests/operators.py --compiler target/specialized-emergence/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen operator and overlay checks failed' }
    }
    if ($Aot) {
        # These isolated outputs are acceptance fixtures. A normal project can
        # freeze one aggregate such as dialects/standard.stx instead.
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/base.stx --jobs $Jobs --output target/specialized-base
        if ($LASTEXITCODE -ne 0) { throw 'Base rule specialization failed' }
        & python tests/base_flow.py --compiler target/specialized-base/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen base control-flow rules failed' }
        & python tools/freeze/build.py --core target/naru.exe --project examples/ffi --locked --jobs $Jobs --output target/specialized-externc
        if ($LASTEXITCODE -ne 0) { throw 'Extern C rule specialization failed' }
        & python tests/externc.py --compiler target/specialized-externc/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen extern C rules failed' }
        & python tests/projects.py --compiler target/specialized-externc/target/naru.exe --frozen
        if ($LASTEXITCODE -ne 0) { throw 'Frozen project references failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/ownership.stx --rules dialects/unless.stx --rules dialects/loops.stx --jobs $Jobs --output target/specialized-ownership
        if ($LASTEXITCODE -ne 0) { throw 'Ownership rule specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/base.stx --rules tools/freeze/semantics.stx --jobs $Jobs --output target/specialized-tests
        if ($LASTEXITCODE -ne 0) { throw 'Effect rule specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/control_flow.stx --jobs $Jobs --output target/specialized-control-flow
        if ($LASTEXITCODE -ne 0) { throw 'Control-flow rule specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules tests/fixtures/rule_contract.stx --jobs $Jobs --output target/specialized-rule-contract
        if ($LASTEXITCODE -ne 0) { throw 'Rule contract specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/resources.stx --jobs $Jobs --output target/specialized-resources
        if ($LASTEXITCODE -ne 0) { throw 'Resource ownership specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/money.stx --jobs $Jobs --output target/specialized-money
        if ($LASTEXITCODE -ne 0) { throw 'Custom type specialization failed' }
        & python tools/freeze/build.py --core target/naru.exe --rules dialects/standard.stx --jobs $Jobs --output target/specialized-standard
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
