#ifndef NARU_NATIVE_PLUGIN_H
#define NARU_NATIVE_PLUGIN_H
// Include this before MLIR headers. prepare_headers.py creates a local header
// overlay for Windows data imports, including TypeID<void> itself.
#ifdef _WIN32
#define NARU_MLIR_TYPEID_IMPORT __declspec(dllimport)
#endif
#include "mlir/Support/TypeID.h"
#if defined(_WIN32) && !defined(NARU_MLIR_PLUGIN_HEADERS)
#error Build native plugins with the prepared Naru header overlay
#endif
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/Builders.h"
#include "mlir/IR/ExtensibleDialect.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Pass/PassRegistry.h"
#include "mlir/Transforms/Passes.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Tools/Plugins/DialectPlugin.h"
#ifdef _WIN32
#undef NARU_MLIR_TYPEID_IMPORT
#define NARU_MLIR_TYPEID_IMPORT
#endif
// Plugin-owned types declared after this header have ordinary local TypeIDs.
// Link naru_mlir_backend.lib rather than another copy of MLIR static libraries.
#endif
