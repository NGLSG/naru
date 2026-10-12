#include "naru_plugin.h"

extern "C" mlir::DialectPluginLibraryInfo mlirGetDialectPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "naru-native-device", "0.2.0",
    [](mlir::DialectRegistry *registry) {
      registry->insertDynamic("naru_native", [](mlir::MLIRContext *context, mlir::DynamicDialect *dialect) {
        auto operation = mlir::DynamicOpDefinition::get("launch", dialect,
          [](mlir::Operation *op) -> mlir::LogicalResult {
            if (op->getNumOperands() || op->getNumResults() || op->getNumRegions())
              return op->emitOpError("requires no operands, results or regions");
            auto count = llvm::dyn_cast_or_null<mlir::IntegerAttr>(op->getAttr("workgroups"));
            if (!count || count.getInt() <= 0)
              return op->emitOpError("requires a positive integer workgroups attribute");
            return mlir::success();
          }, [](mlir::Operation *) { return mlir::success(); });
        dialect->registerDynamicOp(std::move(operation));
      });
    }};
}
