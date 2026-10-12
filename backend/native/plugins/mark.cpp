#include "naru_plugin.h"
#include "mlir/IR/Builders.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Pass/PassRegistry.h"
#include "mlir/Tools/Plugins/PassPlugin.h"

struct MarkPass : mlir::PassWrapper<MarkPass, mlir::OperationPass<>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(MarkPass)
  llvm::StringRef getArgument() const override { return "naru-test-mark"; }
  llvm::StringRef getDescription() const override { return "Mark an operation to test native pass loading"; }
  void runOnOperation() override {
    if (!llvm::isa<mlir::ModuleOp>(getOperation())) {
      getOperation()->emitError("native plugin must share the host ModuleOp TypeID");
      signalPassFailure(); return;
    }
    auto count = mlir::IntegerAttr::get(mlir::IntegerType::get(&getContext(), 32), 1);
    if (!llvm::isa<mlir::IntegerAttr>(count)) {
      getOperation()->emitError("native plugin must share the host IntegerAttr TypeID");
      signalPassFailure(); return;
    }
    getOperation()->setAttr("naru.test_pass", mlir::StringAttr::get(&getContext(), "executed"));
  }
};

extern "C" mlir::PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "naru-test", "0.2.0", [] { mlir::PassRegistration<MarkPass>(); }};
}
