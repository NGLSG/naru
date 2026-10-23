#include "naru_plugin.h"
#include "mlir/Tools/Plugins/PassPlugin.h"
#include "llvm/ADT/DenseSet.h"

// Target ABI adaptation after upstream convert-async-to-llvm. Use MLIR's
// generic operation API so this plugin shares the host registry and TypeIDs.
struct CoroMsvcAllocationPass
    : mlir::PassWrapper<CoroMsvcAllocationPass, mlir::OperationPass<mlir::ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(CoroMsvcAllocationPass)
  llvm::StringRef getArgument() const override { return "naru-coro-msvc-allocation"; }
  llvm::StringRef getDescription() const override {
    return "Adapt upstream async coroutine frame allocation to the MSVC CRT";
  }
  void runOnOperation() override {
    auto module = getOperation();
    bool invalid = false;
    llvm::DenseSet<mlir::Value> alignedIds;
    module.walk([&](mlir::Operation *op) {
      if (op->getName().getStringRef() != "llvm.intr.coro.begin") return;
      auto *call = op->getOperand(1).getDefiningOp();
      if (!call || call->getName().getStringRef() != "llvm.call") return;
      auto callee = call->getAttrOfType<mlir::FlatSymbolRefAttr>("callee");
      if (!callee || callee.getValue() != "aligned_alloc") return;
      if (!module.lookupSymbol("_aligned_malloc")) {
        call->emitError("MSVC coroutine allocation requires _aligned_malloc declaration");
        invalid = true; return;
      }
      mlir::Value size = call->getOperand(1), alignment = call->getOperand(0);
      call->setOperands(mlir::ValueRange{size, alignment});
      call->setAttr("callee", mlir::FlatSymbolRefAttr::get(&getContext(), "_aligned_malloc"));
      alignedIds.insert(op->getOperand(0));
    });
    module.walk([&](mlir::Operation *op) {
      if (op->getName().getStringRef() != "llvm.call" || op->getNumOperands() != 1) return;
      auto callee = op->getAttrOfType<mlir::FlatSymbolRefAttr>("callee");
      if (!callee || callee.getValue() != "free") return;
      auto *memory = op->getOperand(0).getDefiningOp();
      if (!memory || memory->getName().getStringRef() != "llvm.intr.coro.free") return;
      if (!alignedIds.contains(memory->getOperand(0))) return;
      if (!module.lookupSymbol("_aligned_free")) {
        op->emitError("MSVC coroutine deallocation requires _aligned_free declaration");
        invalid = true; return;
      }
      op->setAttr("callee", mlir::FlatSymbolRefAttr::get(&getContext(), "_aligned_free"));
    });
    if (invalid) signalPassFailure();
  }
};

extern "C" mlir::PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "naru-coro-msvc", "0.2.0",
      [] { mlir::PassRegistration<CoroMsvcAllocationPass>(); }};
}
