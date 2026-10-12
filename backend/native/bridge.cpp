#include "naru_mlir.h"
#include "toolchain.h"
#include "mlir/IR/AsmState.h"
#include "mlir/AsmParser/AsmParser.h"
#include "mlir/IR/Builders.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/Diagnostics.h"
#include "mlir/IR/Verifier.h"
#include "mlir/InitAllDialects.h"
#include "mlir/InitAllExtensions.h"
#include "mlir/InitAllPasses.h"
#include "mlir/Parser/Parser.h"
#include "mlir/Pass/PassManager.h"
#include "mlir/Pass/PassRegistry.h"
#include "mlir/Dialect/IRDL/IRDLLoading.h"
#include "mlir/Dialect/IRDL/IR/IRDL.h"
#include "mlir/Tools/Plugins/DialectPlugin.h"
#include "mlir/Tools/Plugins/PassPlugin.h"
#include "mlir/Target/LLVMIR/Export.h"
#include "mlir/Target/LLVMIR/Dialect/All.h"
#include "mlir/Target/LLVMIR/LLVMTranslationInterface.h"
#include "mlir/Target/LLVMIR/ModuleTranslation.h"
#include "mlir/Bytecode/BytecodeWriter.h"
#include "mlir/Conversion/ArithToLLVM/ArithToLLVM.h"
#include "mlir/Conversion/FuncToLLVM/ConvertFuncToLLVM.h"
#include "mlir/Conversion/ControlFlowToLLVM/ControlFlowToLLVM.h"
#include "mlir/Conversion/MemRefToLLVM/MemRefToLLVM.h"
#include "mlir/Conversion/MathToLLVM/MathToLLVM.h"
#include "mlir/Conversion/IndexToLLVM/IndexToLLVM.h"
#include "mlir/Conversion/VectorToLLVM/ConvertVectorToLLVM.h"
#include "mlir/Conversion/UBToLLVM/UBToLLVM.h"
#include "mlir/Conversion/ConvertToLLVM/ToLLVMPass.h"
#include "llvm/Config/llvm-config.h"
#include "llvm/ADT/SmallPtrSet.h"
#include "llvm/IR/LegacyPassManager.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/InlineAsm.h"
#include "llvm/IR/Verifier.h"
#include "llvm/MC/TargetRegistry.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/TargetParser/Host.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/SHA256.h"
#include "llvm/Support/VirtualFileSystem.h"
#include "llvm/WindowsDriver/MSVCPaths.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/TargetSelect.h"
#include "llvm/Target/TargetMachine.h"
#include <filesystem>
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <vector>
#ifdef NARU_WITH_LLD
#include "lld/Common/Driver.h"
LLD_HAS_DRIVER(coff)
#endif

namespace fs = std::filesystem;
namespace {
// LLVM's initializer translator rejects an instruction-valued result, but an
// unattached instruction can retain a symbol use during failure cleanup and
// abort LLVM's module destructor. Inspect actual translated values, rather than
// maintaining a source-language or operation-name whitelist.
constexpr llvm::StringLiteral initializerGuard = "naru_backend.require_constant";
struct InitializerTranslation : mlir::LLVMTranslationDialectInterface {
  using LLVMTranslationDialectInterface::LLVMTranslationDialectInterface;
  mlir::LogicalResult amendOperation(mlir::Operation *op,
      mlir::ArrayRef<llvm::Instruction *> instructions, mlir::NamedAttribute attr,
      mlir::LLVM::ModuleTranslation &translation) const override {
    if (attr.getName().getValue() != initializerGuard ||
        !mlir::isa<mlir::LLVM::GlobalOp, mlir::LLVM::AliasOp>(op->getParentOp()))
      return mlir::success();
    llvm::SmallPtrSet<llvm::Instruction *, 8> detached;
    llvm::SmallVector<llvm::Instruction *> pending;
    bool constant = true;
    for (auto result : op->getResults()) {
      auto *value = translation.lookupValue(result);
      if (llvm::isa_and_nonnull<llvm::Constant>(value)) continue;
      constant = false;
      if (auto *instruction = llvm::dyn_cast_or_null<llvm::Instruction>(value))
        pending.push_back(instruction);
    }
    if (constant) return mlir::success();
    llvm::append_range(pending, instructions);
    while (!pending.empty()) {
      auto *instruction = pending.pop_back_val();
      if (instruction->getParent() || !detached.insert(instruction).second) continue;
      for (auto &operand : instruction->operands())
        if (auto *dependency = llvm::dyn_cast<llvm::Instruction>(operand.get()))
          pending.push_back(dependency);
    }
    for (auto *instruction : detached) instruction->dropAllReferences();
    for (auto *instruction : detached) instruction->deleteValue();
    return op->emitError("global initializer did not lower to an LLVM constant; operation: ")
        << op->getName();
  }
};
class InitializerSafetyDialect : public mlir::Dialect {
public:
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(InitializerSafetyDialect)
  static llvm::StringRef getDialectNamespace() { return "naru_backend"; }
  explicit InitializerSafetyDialect(mlir::MLIRContext *context)
      : Dialect(getDialectNamespace(), context, mlir::TypeID::get<InitializerSafetyDialect>()) {
    addInterfaces<InitializerTranslation>();
  }
};
struct InitializerGuards {
  llvm::SmallVector<std::pair<mlir::Operation *, mlir::Attribute>> saved;
  ~InitializerGuards() {
    for (auto [op, previous] : saved) {
      if (previous) op->setAttr(initializerGuard, previous);
      else op->removeAttr(initializerGuard);
    }
  }
  bool install(mlir::ModuleOp module) {
    module.getContext()->getOrLoadDialect<InitializerSafetyDialect>();
    bool valid = true;
    module.walk([&](mlir::Operation *owner) {
      if (!mlir::isa<mlir::LLVM::GlobalOp, mlir::LLVM::AliasOp>(owner)) return;
      for (auto &region : owner->getRegions()) for (auto &block : region)
        for (auto &op : block.without_terminator()) {
          if (op.getNumResults() != 1 || op.getNumRegions() || op.getNumSuccessors()) {
            op.emitError("LLVM global initializer operation requires one constant result and no regions or successors");
            valid = false; continue;
          }
          saved.emplace_back(&op, op.getAttr(initializerGuard));
          op.setAttr(initializerGuard, mlir::UnitAttr::get(module.getContext()));
        }
    });
    return valid;
  }
};
struct Session {
  mlir::DialectRegistry registry;
  std::unique_ptr<mlir::MLIRContext> context;
  mlir::OwningOpRef<mlir::ModuleOp> module;
  std::unique_ptr<mlir::ScopedDiagnosticHandler> diagnostics;
  std::string error, printed;
  std::string pipeline = "builtin.module(canonicalize,cse)";
  std::string lowering = "builtin.module(convert-scf-to-cf,convert-to-llvm,reconcile-unrealized-casts)";
  std::string opt = "3", entry = "main", triple, cpu, features, report, profile, artifact = "mlir";
  std::string runtime = "freestanding", subsystem = "console", vcTools, sdkDir, sdkVersion;
  std::vector<std::string> linkObjects, linkLibraries, libraryPaths, resolvedLibraries;
  std::vector<std::string> protectedFiles;
  std::vector<mlir::DialectPlugin> dialectPlugins;
  std::vector<mlir::PassPlugin> passPlugins;
  std::vector<std::string> dialectPluginPaths, passPluginPaths, irdlPaths;
  std::map<mlir::Region *, std::unique_ptr<mlir::Region>> looseRegions;
  std::map<mlir::Block *, std::unique_ptr<mlir::Block>> looseBlocks;
  std::map<mlir::OperationState *, std::unique_ptr<mlir::OperationState>> states;
  // Opaque handles in the C ABI are session-owned.  Keep ownership sets for
  // graph objects so a handle from another session is rejected before MLIR
  // dereferences it.  Types, attributes and SSA values are context-owned and
  // are checked through their MLIR context at the call site.
  std::set<mlir::Region *> regions;
  std::set<mlir::Block *> blocks;
  std::set<mlir::Operation *> operations;
  bool configured = false;
  bool genericOutput = false;
  int fail(llvm::Twine message) { if (error.empty()) error = message.str(); return 1; }
  Session() {
    mlir::registerAllDialects(registry);
    registry.insert<InitializerSafetyDialect>();
    mlir::registerAllExtensions(registry);
    mlir::arith::registerConvertArithToLLVMInterface(registry);
    mlir::registerConvertFuncToLLVMInterface(registry);
    mlir::cf::registerConvertControlFlowToLLVMInterface(registry);
    mlir::registerConvertMemRefToLLVMInterface(registry);
    mlir::registerConvertMathToLLVMInterface(registry);
    mlir::index::registerConvertIndexToLLVMInterface(registry);
    mlir::vector::registerConvertVectorToLLVMInterface(registry);
    mlir::ub::registerConvertUBToLLVMInterface(registry);
    mlir::registerConvertToLLVMDependentDialectLoading(registry);
    mlir::registerAllToLLVMIRTranslations(registry);
    context = std::make_unique<mlir::MLIRContext>(registry);
    context->allowUnregisteredDialects(false);
    diagnostics = std::make_unique<mlir::ScopedDiagnosticHandler>(context.get(), [this](mlir::Diagnostic &d) {
      llvm::raw_string_ostream stream(error);
      d.getLocation().print(stream); stream << ": ";
      d.print(stream); stream << '\n';
      return mlir::success();
    });
    module = mlir::ModuleOp::create(mlir::UnknownLoc::get(context.get()));
    blocks.insert(module->getBody());
  }
};
std::once_flag initialize;
std::mutex registrationMutex;
std::mutex linkerMutex;
std::vector<std::string> registeredPassPluginPaths;
// Pass registration is process-global in MLIR.  Keep the corresponding
// dynamic-library handles alive for the lifetime of the backend, rather than
// only for the Session that first loaded them.  Without this ownership, a
// second session would see the path in registeredPassPluginPaths and skip
// loading it even though destroying the first session had already unloaded
// the DLL; its pipeline would then fail with an unknown pass.
std::vector<mlir::PassPlugin> registeredPassPlugins;
Session *session(void *p) { return static_cast<Session *>(p); }
bool stringArg(Session &s, const char *p, int64_t n, std::string &out, bool nul = false) {
  if (n < 0 || (n && !p)) { s.fail("invalid string pointer or length"); return false; }
  out.assign(p ? p : "", static_cast<size_t>(n));
  if (!nul && out.find('\0') != std::string::npos) { s.fail("embedded NUL in argument"); return false; }
  return true;
}
std::string absolute(const std::string &name, const std::string &base = "") {
  std::error_code ec;
  fs::path p = fs::u8path(name);
  if (p.is_relative() && !base.empty()) p = fs::u8path(base) / p;
  auto abs = fs::absolute(p, ec);
  return ec ? name : abs.lexically_normal().u8string();
}
bool sameFile(const std::string &a, const std::string &b) {
  if (a.empty() || b.empty()) return false;
  std::error_code ec;
  if (fs::equivalent(fs::u8path(a), fs::u8path(b), ec) && !ec) return true;
  auto x = absolute(a), y = absolute(b);
#ifdef _WIN32
  for (auto &c : x) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
  for (auto &c : y) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
#endif
  return x == y;
}
bool protect(Session &s, const std::string &output) {
  for (const auto &input : s.protectedFiles)
    if (sameFile(output, input)) { s.fail("output would overwrite an input: " + input); return false; }
  if (!s.report.empty()) {
    if (sameFile(s.report, output)) { s.fail("report would overwrite the output"); return false; }
    for (const auto &input : s.protectedFiles)
      if (sameFile(s.report, input)) { s.fail("report would overwrite an input: " + input); return false; }
  }
  return true;
}
bool writeBytes(Session &s, const std::string &path, llvm::StringRef bytes) {
  std::error_code ec;
  auto parent = fs::u8path(path).parent_path();
  if (!parent.empty()) fs::create_directories(parent, ec);
  if (ec) { s.fail("cannot create output directory: " + ec.message()); return false; }
  llvm::SmallString<256> temp;
  int fd = -1;
  ec = llvm::sys::fs::createUniqueFile(path + ".naru-%%%%%%", fd, temp);
  if (ec) { s.fail("cannot create output: " + ec.message()); return false; }
  { llvm::raw_fd_ostream stream(fd, true); stream << bytes; stream.flush();
    if (stream.has_error()) { s.fail("cannot write output"); llvm::sys::fs::remove(temp); return false; } }
  ec = llvm::sys::fs::rename(temp, path);
  if (ec) { llvm::sys::fs::remove(temp); s.fail("cannot replace output: " + ec.message()); return false; }
  return true;
}
bool runPipeline(Session &s, llvm::StringRef pipeline) {
  if (pipeline.empty()) return mlir::succeeded(mlir::verify(*s.module));
  llvm::raw_string_ostream errors(s.error);
  auto parsed = mlir::parsePassPipeline(pipeline, errors);
  if (mlir::failed(parsed)) return false;
  if (parsed->getOpAnchorName() != mlir::ModuleOp::getOperationName()) {
    s.fail("top-level pass pipeline must be anchored at builtin.module"); return false;
  }
  mlir::PassManager manager(s.context.get(), mlir::ModuleOp::getOperationName());
  // The full pipeline overload returns its root manager. Adding that root to
  // another manager would run passes only on nested modules, silently doing no
  // work for the normal Naru module.
  static_cast<mlir::OpPassManager &>(manager) = std::move(*parsed);
  manager.enableVerifier(true);
  return mlir::succeeded(manager.run(*s.module));
}
bool stringField(Session &s, llvm::json::Object &o, llvm::StringRef key, std::string &value) {
  if (auto *field = o.get(key)) {
    auto text = field->getAsString();
    if (!text) { s.fail("config field must be a string: " + key); return false; }
    if (text->contains('\0')) { s.fail("embedded NUL in config field: " + key); return false; }
    value = text->str();
  }
  return true;
}
bool collectInputs(Session &s, llvm::json::Object &o, const std::string &base) {
  for (llvm::StringRef key : {"source_inputs", "dialect_plugins", "pass_plugins", "irdl", "link_objects", "link_libraries"}) {
    auto *field = o.get(key); if (!field) continue;
    auto *paths = field->getAsArray();
    if (!paths) { s.fail("config field must be an array: " + key); return false; }
    for (auto &value : *paths) {
      auto str = value.getAsString();
      if (!str) { s.fail("config paths must be strings"); return false; }
      if (key == "link_libraries" && str->find_first_of("/\\:") == llvm::StringRef::npos) continue;
      s.protectedFiles.push_back(absolute(str->str(), base));
    }
  }
  return stringField(s, o, "report", s.report);
}
bool applyConfig(Session &s, llvm::json::Object &o, const std::string &base) {
  if (auto *generic = o.get("generic_output")) {
    auto value = generic->getAsBoolean();
    if (!value) { s.fail("generic_output must be a boolean"); return false; }
    s.genericOutput = *value;
  }
  for (auto entry : {std::make_pair("pipeline", &s.pipeline), {"lowering_pipeline", &s.lowering},
       {"opt_level", &s.opt}, {"entry", &s.entry}, {"native_entry", &s.entry}, {"triple", &s.triple},
       {"cpu", &s.cpu}, {"features", &s.features}, {"report", &s.report}, {"artifact", &s.artifact},
       {"runtime", &s.runtime}, {"subsystem", &s.subsystem}, {"vc_tools_dir", &s.vcTools},
       {"windows_sdk_dir", &s.sdkDir}, {"windows_sdk_version", &s.sdkVersion}})
    if (!stringField(s, o, entry.first, *entry.second)) return false;
  if (s.runtime != "freestanding" && s.runtime != "crt-static" && s.runtime != "crt-dynamic") {
    s.fail("runtime must be freestanding, crt-static or crt-dynamic"); return false;
  }
  if (s.subsystem != "console" && s.subsystem != "windows") { s.fail("subsystem must be console or windows"); return false; }
  for (llvm::StringRef key : {"link_objects", "link_libraries", "library_paths"}) {
    auto *field = o.get(key); if (!field) continue;
    auto *array = field->getAsArray();
    if (!array) { s.fail("config field must be an array: " + key); return false; }
    auto &destination = key == "link_objects" ? s.linkObjects : key == "link_libraries" ? s.linkLibraries : s.libraryPaths;
    for (auto &value : *array) {
      auto text = value.getAsString();
      if (!text || text->empty() || text->contains('\0')) { s.fail("link input must be nonempty text: " + key); return false; }
      bool named = key == "link_libraries" && text->find_first_of("/\\:") == llvm::StringRef::npos;
      if (named && (text->starts_with("-") || text->starts_with("@"))) { s.fail("invalid library name: " + *text); return false; }
      auto path = named ? text->str() : absolute(text->str(), base);
      if (std::find(destination.begin(), destination.end(), path) == destination.end()) destination.push_back(path);
      if (key == "link_objects" || (key == "link_libraries" && !named)) s.protectedFiles.push_back(path);
    }
  }
  if (!s.vcTools.empty()) s.vcTools = absolute(s.vcTools, base);
  if (!s.sdkDir.empty()) s.sdkDir = absolute(s.sdkDir, base);
  if (o.get("emit")) { s.fail("external emitter commands are unsupported by the in-process backend; select a native target or MLIR artifact"); return false; }
  for (llvm::StringRef key : {"source_inputs", "dialect_plugins", "pass_plugins", "irdl"}) {
    auto *field = o.get(key);
    if (!field) continue;
    auto *paths = field->getAsArray();
    if (!paths) { s.fail("config field must be an array: " + key); return false; }
    for (auto &value : *paths) {
      auto str = value.getAsString();
      if (!str) { s.fail("config paths must be strings"); return false; }
      auto path = absolute(str->str(), base);
      s.protectedFiles.push_back(path);
      if (key == "source_inputs") continue;
      auto &loaded = key == "irdl" ? s.irdlPaths : key == "pass_plugins" ? s.passPluginPaths : s.dialectPluginPaths;
      bool seen = false;
      for (const auto &prior : loaded) if (sameFile(prior, path)) { seen = true; break; }
      if (seen) continue;
      if (key == "dialect_plugins") {
        auto plugin = mlir::DialectPlugin::load(path);
        if (!plugin) { s.fail(llvm::toString(plugin.takeError())); return false; }
        plugin->registerDialectRegistryCallbacks(s.registry);
        s.context->appendDialectRegistry(s.registry);
        s.dialectPlugins.push_back(std::move(*plugin));
      } else if (key == "pass_plugins") {
        bool registered = false;
        for (const auto &prior : registeredPassPluginPaths)
          if (sameFile(prior, path)) { registered = true; break; }
        if (registered) { loaded.push_back(path); continue; }
        auto plugin = mlir::PassPlugin::load(path);
        if (!plugin) { s.fail(llvm::toString(plugin.takeError())); return false; }
        plugin->registerPassRegistryCallbacks();
        registeredPassPlugins.push_back(std::move(*plugin));
        registeredPassPluginPaths.push_back(path);
      } else {
        auto definition = mlir::parseSourceFile<mlir::ModuleOp>(path, s.context.get());
        if (!definition) return false;
        std::set<std::string> declared;
        auto available = s.context->getAvailableDialects();
        definition->walk([&](mlir::irdl::DialectOp dialect) {
          auto name = dialect.getSymName().str();
          if (!declared.insert(name).second || llvm::is_contained(available, name) || s.context->getLoadedDialect(name))
            s.fail("IRDL dialect is already registered: " + name);
        });
        if (!s.error.empty() || mlir::failed(mlir::irdl::loadDialects(*definition))) return false;
      }
      loaded.push_back(path);
    }
  }
  return true;
}
void report(Session &s, bool success, const std::string &target, const std::string &output) {
  if (s.report.empty()) return;
  llvm::json::Object object{{"backend", "in-process"}, {"processes_spawned", 0},
      {"llvm_version", LLVM_VERSION_STRING}, {"success", success}, {"target", target},
      {"output", output}, {"pipeline", s.pipeline}, {"lowering_pipeline", s.lowering},
      {"opt_level", s.opt}, {"error", s.error}};
  llvm::json::Array objects, libraries, directories;
  for (const auto &path : s.linkObjects) objects.push_back(path);
  for (const auto &path : s.resolvedLibraries) libraries.push_back(path);
  for (const auto &path : s.libraryPaths) directories.push_back(path);
  object["link"] = llvm::json::Object{{"runtime", s.runtime}, {"subsystem", s.subsystem},
      {"objects", std::move(objects)}, {"libraries", std::move(libraries)}, {"library_paths", std::move(directories)},
      {"vc_tools_dir", s.vcTools}, {"windows_sdk_dir", s.sdkDir}, {"windows_sdk_version", s.sdkVersion}};
  std::string encoded; llvm::raw_string_ostream stream(encoded);
  stream << llvm::formatv("{0:2}", llvm::json::Value(std::move(object))) << '\n';
  writeBytes(s, s.report, encoded);
}
bool prepareLink(Session &s) {
  llvm::Triple triple(s.triple.empty() ? llvm::sys::getDefaultTargetTriple() : s.triple);
  if (!triple.isOSWindows() || !triple.isOSBinFormatCOFF()) { s.fail("executable linking requires a Windows COFF target"); return false; }
  auto addPath = [&](const std::string &path) {
    if (!path.empty() && std::find(s.libraryPaths.begin(), s.libraryPaths.end(), path) == s.libraryPaths.end())
      s.libraryPaths.push_back(path);
  };
  if (const char *lib = std::getenv("LIB")) {
    llvm::SmallVector<llvm::StringRef> paths;
    llvm::StringRef(lib).split(paths, ';', -1, false);
    for (auto path : paths) addPath(absolute(path.str()));
  }
  // Discover installed libraries through LLVM's native Windows driver APIs.
  // These query the environment/registry/Setup Configuration COM interface;
  // neither vswhere nor a compiler/linker subprocess is required.
  bool needSDK = s.runtime != "freestanding";
  for (const auto &name : s.linkLibraries) if (name.find_first_of("/\\:") == std::string::npos) needSDK = true;
  if (needSDK) {
    NaruToolchain info;
    info.triple = triple.str(); info.vcTools = s.vcTools;
    info.sdkDir = s.sdkDir; info.sdkVersion = s.sdkVersion;
    std::string error;
    if (!naruDiscoverToolchain(info, error)) { s.fail(error); return false; }
    s.vcTools = info.vcTools; s.sdkDir = info.sdkDir; s.sdkVersion = info.sdkVersion;
    for (const auto &path : info.libraries) addPath(path);
  }
  auto libraries = s.linkLibraries;
  if (s.runtime == "crt-static") {
    for (auto lib : {"libcmt.lib", "libvcruntime.lib", "libucrt.lib", "oldnames.lib", "kernel32.lib"}) libraries.emplace_back(lib);
  } else if (s.runtime == "crt-dynamic") {
    for (auto lib : {"msvcrt.lib", "vcruntime.lib", "ucrt.lib", "oldnames.lib", "kernel32.lib"}) libraries.emplace_back(lib);
  }
  std::vector<std::string> objects;
  for (const auto &path : s.linkObjects) {
    std::error_code ec;
    if (!fs::is_regular_file(fs::u8path(path), ec)) { s.fail("link object not found: " + path); return false; }
    bool seen = false;
    for (const auto &prior : objects) if (sameFile(prior, path)) { seen = true; break; }
    if (!seen) objects.push_back(path);
  }
  s.linkObjects = std::move(objects);
  for (auto name : libraries) {
    std::string resolved;
    if (name.find_first_of("/\\:") != std::string::npos) resolved = absolute(name);
    else {
      if (!llvm::StringRef(name).ends_with_insensitive(".lib")) name += ".lib";
      for (const auto &directory : s.libraryPaths) {
        auto candidate = (fs::u8path(directory) / fs::u8path(name)).u8string();
        std::error_code ec;
        if (fs::is_regular_file(fs::u8path(candidate), ec)) { resolved = absolute(candidate); break; }
      }
    }
    std::error_code ec;
    if (resolved.empty() || !fs::is_regular_file(fs::u8path(resolved), ec)) {
      s.fail("link library not found: " + name + "; configure library_paths or install the target Windows SDK/MSVC libraries"); return false;
    }
    bool seen = false;
    for (const auto &prior : s.resolvedLibraries) if (sameFile(prior, resolved)) { seen = true; break; }
    if (!seen) { s.resolvedLibraries.push_back(resolved); s.protectedFiles.push_back(resolved); }
  }
  return true;
}
// Windows x64 passes the allocation size in RAX and expects it preserved.
// Probe each page without changing the caller's stack pointer. The naked
// helper must not acquire a compiler-generated prologue or another probe.
// Adapted from LLVM compiler-rt/lib/builtins/x86_64/chkstk.S (Apache-2.0
// WITH LLVM-exception), https://github.com/llvm/llvm-project/blob/main/compiler-rt/lib/builtins/x86_64/chkstk.S.
void addFreestandingStackProbe(llvm::Module &module) {
  if (module.getFunction("__chkstk")) return;
  auto &context = module.getContext();
  auto *type = llvm::FunctionType::get(llvm::Type::getVoidTy(context), false);
  auto *function = llvm::Function::Create(type, llvm::GlobalValue::WeakODRLinkage, "__chkstk", module);
  function->addFnAttr(llvm::Attribute::Naked);
  function->addFnAttr(llvm::Attribute::NoUnwind);
  function->addFnAttr(llvm::Attribute::NoInline);
  llvm::IRBuilder<> builder(llvm::BasicBlock::Create(context, "entry", function));
  auto *assembly = llvm::InlineAsm::get(type,
      "pushq %rcx\n\tpushq %rax\n\tleaq 24(%rsp), %rcx\n\t"
      "cmpq $$4096, %rax\n\tjb 2f\n1:\n\tsubq $$4096, %rcx\n\t"
      "testq %rcx, (%rcx)\n\tsubq $$4096, %rax\n\tcmpq $$4096, %rax\n\tja 1b\n"
      "2:\n\tsubq %rax, %rcx\n\ttestq %rcx, (%rcx)\n\tpopq %rax\n\tpopq %rcx\n\tretq",
      "", true);
  builder.CreateCall(assembly);
  builder.CreateUnreachable();
}
// The LLVM dialect currently has no DLL-storage-class property. Preserve this
// target fact as a namespaced symbol attribute and apply it before LLVM passes.
// Any language library can attach it; no C AST or source spelling reaches here.
bool applySymbolTargetFacts(Session &s, llvm::Module &module, const llvm::Triple &triple) {
  bool valid = true;
  s.module->walk([&](mlir::Operation *op) {
    auto raw = op->getAttr("naru.llvm.dll_storage_class");
    if (!raw || !valid) return;
    auto value = mlir::dyn_cast<mlir::StringAttr>(raw);
    auto name = op->getAttrOfType<mlir::StringAttr>("sym_name");
    auto kind = op->getName().getStringRef();
    if (!value || !name || (kind != "llvm.func" && kind != "llvm.mlir.global" && kind != "llvm.mlir.alias")) {
      s.fail("naru.llvm.dll_storage_class requires a string on an LLVM global symbol"); valid = false; return;
    }
    auto storage = value.getValue();
    if (storage != "export" && storage != "import") {
      s.fail("naru.llvm.dll_storage_class must be export or import"); valid = false; return;
    }
    auto *symbol = module.getNamedValue(name.getValue());
    if (!triple.isOSWindows() || !symbol || symbol->hasLocalLinkage() || (storage == "import" && !symbol->isDeclaration())) {
      s.fail("DLL storage requires a Windows external symbol; imports must be declarations"); valid = false; return;
    }
    symbol->setDLLStorageClass(storage == "export" ? llvm::GlobalValue::DLLExportStorageClass : llvm::GlobalValue::DLLImportStorageClass);
  });
  return valid;
}
bool emitCPU(Session &s, const std::string &target, const std::string &output) {
  if (!runPipeline(s, s.lowering)) return false;
  InitializerGuards initializerGuards;
  if (!initializerGuards.install(*s.module)) return false;
  llvm::LLVMContext context;
  auto module = mlir::translateModuleToLLVMIR(*s.module, context);
  if (!module) return false;
  std::string triple = s.triple.empty() ? llvm::sys::getDefaultTargetTriple() : s.triple;
  std::string error;
  auto *targetInfo = llvm::TargetRegistry::lookupTarget(llvm::Triple(triple), error);
  if (!targetInfo) { s.fail(error); return false; }
  llvm::TargetOptions options;
  llvm::CodeGenOptLevel cg = s.opt == "0" ? llvm::CodeGenOptLevel::None : s.opt == "1" ? llvm::CodeGenOptLevel::Less
      : s.opt == "3" ? llvm::CodeGenOptLevel::Aggressive : llvm::CodeGenOptLevel::Default;
  std::unique_ptr<llvm::TargetMachine> machine(targetInfo->createTargetMachine(
      llvm::Triple(triple), s.cpu.empty() ? "generic" : s.cpu, s.features, options, std::nullopt, std::nullopt, cg));
  if (!machine) { s.fail("target machine creation failed"); return false; }
  module->setTargetTriple(llvm::Triple(triple));
  module->setDataLayout(machine->createDataLayout());
  if (!applySymbolTargetFacts(s, *module, llvm::Triple(triple))) return false;
  if (target == "exe" && s.runtime == "freestanding" && llvm::Triple(triple).isOSWindows()
      && llvm::Triple(triple).getArch() == llvm::Triple::x86_64) addFreestandingStackProbe(*module);
  // LLVM 24 expresses size preferences on each function; its optimization
  // level enum now contains only O0-O3.
  if (s.opt == "s" || s.opt == "z") {
    for (auto &function : *module) {
      function.addFnAttr(llvm::Attribute::OptimizeForSize);
      if (s.opt == "z") function.addFnAttr(llvm::Attribute::MinSize);
    }
  }
  llvm::LoopAnalysisManager loops;
  llvm::FunctionAnalysisManager functions;
  llvm::CGSCCAnalysisManager scc;
  llvm::ModuleAnalysisManager modules;
  llvm::PassBuilder builder(machine.get());
  builder.registerModuleAnalyses(modules); builder.registerCGSCCAnalyses(scc);
  builder.registerFunctionAnalyses(functions); builder.registerLoopAnalyses(loops);
  builder.crossRegisterProxies(loops, functions, scc, modules);
  auto level = s.opt == "0" ? llvm::OptimizationLevel::O0 : s.opt == "1" ? llvm::OptimizationLevel::O1
      : s.opt == "3" ? llvm::OptimizationLevel::O3 : llvm::OptimizationLevel::O2;
  auto pipeline = level == llvm::OptimizationLevel::O0 ? builder.buildO0DefaultPipeline(level) : builder.buildPerModuleDefaultPipeline(level);
  pipeline.run(*module, modules);
  llvm::raw_string_ostream errors(s.error);
  if (llvm::verifyModule(*module, &errors)) return false;
  if (target == "llvm-ir") {
    std::string ir; llvm::raw_string_ostream stream(ir); module->print(stream, nullptr);
    return writeBytes(s, output, ir);
  }
  llvm::SmallVector<char, 0> bytes;
  llvm::raw_svector_ostream stream(bytes);
  llvm::legacy::PassManager codegen;
  if (machine->addPassesToEmitFile(codegen, stream, nullptr, llvm::CodeGenFileType::ObjectFile)) {
    s.fail("target cannot emit an object file"); return false;
  }
  codegen.run(*module);
  if (target == "object") return writeBytes(s, output, llvm::StringRef(bytes.data(), bytes.size()));
#ifdef NARU_WITH_LLD
  if (!llvm::Triple(triple).isOSWindows()) {
    s.fail("executable linking currently requires a Windows target; use object for this target"); return false;
  }
  llvm::SmallString<256> obj, exe;
  int fd;
  auto ec = llvm::sys::fs::createTemporaryFile("naru-native", "obj", fd, obj);
  if (ec) { s.fail(ec.message()); return false; }
  { llvm::raw_fd_ostream file(fd, true); file.write(bytes.data(), bytes.size()); }
  ec = llvm::sys::fs::createTemporaryFile("naru-native", "exe", fd, exe);
  if (ec) { llvm::sys::fs::remove(obj); s.fail(ec.message()); return false; }
  { llvm::raw_fd_ostream file(fd, true); }
  std::vector<std::string> values = {"lld-link", "/subsystem:" + s.subsystem, "/out:" + exe.str().str(), obj.str().str()};
  if (s.runtime == "freestanding") { values.push_back("/entry:" + s.entry); values.push_back("/nodefaultlib"); }
  for (const auto &path : s.libraryPaths) values.push_back("/libpath:" + path);
  for (const auto &path : s.linkObjects) values.push_back(path);
  for (const auto &path : s.resolvedLibraries) values.push_back(path);
  std::vector<const char *> arguments; for (auto &value : values) arguments.push_back(value.c_str());
  std::string log; llvm::raw_string_ostream diagnostic(log);
  bool linked;
  { std::lock_guard<std::mutex> lock(linkerMutex);
    auto result = lld::lldMain(arguments, diagnostic, diagnostic, {{lld::WinLink, &lld::coff::link}});
    linked = result.retCode == 0;
    if (!result.canRunAgain) { s.fail("LLD encountered an unrecoverable native linking failure"); linked = false; }
  }
  bool ok = false;
  if (!linked) s.fail(log);
  else if (auto executable = llvm::MemoryBuffer::getFile(exe)) ok = writeBytes(s, output, (*executable)->getBuffer());
  else s.fail("native linker did not produce an executable");
  llvm::sys::fs::remove(obj); llvm::sys::fs::remove(exe);
  return ok;
#else
  s.fail("this backend was built without the in-process LLD COFF library"); return false;
#endif
}
mlir::Location location(Session &s, void *p) {
  return p ? mlir::Location::getFromOpaquePointer(p) : mlir::UnknownLoc::get(s.context.get());
}
mlir::OperationState *state(Session &s, void *p) {
  auto *value = static_cast<mlir::OperationState *>(p);
  if (!s.states.count(value)) { s.fail("invalid or consumed operation builder"); return nullptr; }
  return value;
}
} // namespace

int32_t naru_mlir_abi_version() { return 1; }
const char *naru_file_sha256(const char *path, int64_t len) {
  thread_local std::string result;
  result.clear();
  if (!path || len <= 0 || std::memchr(path, 0, static_cast<size_t>(len))) return result.c_str();
  auto file = llvm::MemoryBuffer::getFile(llvm::StringRef(path, len));
  if (!file) return result.c_str();
  llvm::SHA256 hash; hash.update((*file)->getBuffer());
  auto digest = hash.final();
  const char *hex = "0123456789abcdef";
  for (auto byte : digest) { result += hex[byte >> 4]; result += hex[byte & 15]; }
  return result.c_str();
}
void *naru_mlir_create() {
  std::call_once(initialize, [] { mlir::registerAllPasses(); llvm::InitializeAllTargetInfos(); llvm::InitializeAllTargets();
    llvm::InitializeAllTargetMCs(); llvm::InitializeAllAsmPrinters(); llvm::InitializeAllAsmParsers(); });
  return new Session();
}
void naru_mlir_destroy(void *p) { delete session(p); }
const char *naru_mlir_error(void *p) { return p ? session(p)->error.c_str() : "MLIR session is null"; }
int32_t naru_mlir_configure(void *p, const char *json, int64_t len) {
  if (!p) return 1; auto &s = *session(p); s.error.clear();
  if (s.configured) return s.fail("MLIR session is already configured");
  std::string text; if (!stringArg(s, json, len, text)) return 1;
  auto config = llvm::json::parse(text);
  if (!config) return s.fail(llvm::toString(config.takeError()));
  auto *o = config->getAsObject(); if (!o) return s.fail("backend configuration must be an object");
  std::lock_guard<std::mutex> lock(registrationMutex);
  std::optional<llvm::json::Value> profileConfig;
  std::string profileBase;
  if (auto target = o->getString("target")) {
    if (*target != "mlir" && *target != "llvm-ir" && *target != "object" && *target != "exe" && *target != "bytecode") {
      s.profile = absolute(target->str()); s.protectedFiles.push_back(s.profile);
      auto file = llvm::MemoryBuffer::getFile(s.profile);
      if (!file) return s.fail("cannot read target profile: " + file.getError().message());
      auto profile = llvm::json::parse((*file)->getBuffer());
      if (!profile) return s.fail(llvm::toString(profile.takeError()));
      profileConfig = std::move(*profile);
      auto *object = profileConfig->getAsObject(); if (!object) return s.fail("target profile must be an object");
      profileBase = fs::u8path(s.profile).parent_path().u8string();
      if (!collectInputs(s, *object, profileBase)) return 1;
    }
  }
  if (!collectInputs(s, *o, "")) return 1;
  if (auto output = o->getString("output"))
    if (!output->empty() && !protect(s, output->str())) return 1;
  if (profileConfig && !applyConfig(s, *profileConfig->getAsObject(), profileBase)) return 1;
  if (!applyConfig(s, *o, "")) return 1;
  if (s.opt != "0" && s.opt != "1" && s.opt != "2" && s.opt != "3" && s.opt != "s" && s.opt != "z") return s.fail("invalid optimization level");
  s.configured = true; return 0;
}
int32_t naru_mlir_parse(void *p, const char *text, int64_t len, const char *source, int64_t sourceLen) {
  if (!p) return 1; auto &s = *session(p); s.error.clear(); std::string ir, filename;
  if (!stringArg(s, text, len, ir) || !stringArg(s, source, sourceLen, filename)) return 1;
  if (!filename.empty()) s.protectedFiles.push_back(absolute(filename));
  llvm::SourceMgr manager;
  manager.AddNewSourceBuffer(llvm::MemoryBuffer::getMemBufferCopy(ir, filename), llvm::SMLoc());
  llvm::raw_string_ostream errors(s.error);
  mlir::SourceMgrDiagnosticHandler sourceDiagnostics(manager, s.context.get(), errors);
  auto module = mlir::parseSourceFile<mlir::ModuleOp>(manager, s.context.get());
  if (!module) return s.fail("MLIR parsing failed");
  // Parsing replaces the module.  Any handles created for the previous
  // graph become invalid and must not remain reachable through this session.
  s.looseRegions.clear(); s.looseBlocks.clear(); s.states.clear();
  s.regions.clear(); s.blocks.clear(); s.operations.clear();
  s.module = std::move(module); s.blocks.insert(s.module->getBody()); return 0;
}
int32_t naru_mlir_verify(void *p) {
  if (!p) return 1; auto &s = *session(p); return mlir::succeeded(mlir::verify(*s.module)) ? 0 : 1;
}
const char *naru_mlir_module_text(void *p, int32_t generic) {
  if (!p) return nullptr; auto &s = *session(p); s.printed.clear();
  llvm::raw_string_ostream stream(s.printed); mlir::OpPrintingFlags flags;
  if (generic) flags.printGenericOpForm();
  s.module->print(stream, flags); stream << '\n'; return s.printed.c_str();
}
const char *naru_mlir_print(void *p) { return naru_mlir_module_text(p, 0); }
int64_t naru_mlir_print_size(void *p) { return p ? static_cast<int64_t>(session(p)->printed.size()) : 0; }
int32_t naru_mlir_compile(void *p, const char *targetData, int64_t targetLen, const char *outputData, int64_t outputLen) {
  if (!p) return 1; auto &s = *session(p); s.error.clear(); std::string target, output;
  if (!stringArg(s, targetData, targetLen, target) || !stringArg(s, outputData, outputLen, output) || output.empty()) return s.fail("invalid compile output");
  output = absolute(output); if (!protect(s, output)) return 1;
  if (!s.profile.empty() && sameFile(target, s.profile)) target = s.artifact;
  bool ok = target != "exe" || prepareLink(s);
  if (ok) ok = protect(s, output);
  if (ok) ok = mlir::succeeded(mlir::verify(*s.module)) && runPipeline(s, s.pipeline);
  if (ok && target == "mlir") { const char *text = naru_mlir_module_text(p, s.genericOutput ? 1 : 0); ok = writeBytes(s, output, text); }
  else if (ok && target == "bytecode") { std::string bytes; llvm::raw_string_ostream out(bytes); ok = mlir::succeeded(mlir::writeBytecodeToFile(*s.module, out)) && writeBytes(s, output, bytes); }
  else if (ok && (target == "llvm-ir" || target == "object" || target == "exe")) ok = emitCPU(s, target, output);
  else if (ok) { s.fail("unknown native backend target: " + target); ok = false; }
  if (!ok && s.error.empty()) s.fail("MLIR compilation failed");
  report(s, ok, target, output); return ok && s.error.empty() ? 0 : 1;
}
void *naru_mlir_module_body(void *p) { return p ? session(p)->module->getBody() : nullptr; }
void *naru_mlir_location(void *p, const char *file, int64_t len, int64_t line, int64_t column) {
  if (!p) return nullptr; auto &s = *session(p); std::string name;
  if (!stringArg(s, file, len, name) || line < 0 || column < 0) return nullptr;
  return const_cast<void *>(mlir::FileLineColLoc::get(s.context.get(), name, line, column).getAsOpaquePointer());
}
void *naru_mlir_type_parse(void *p, const char *text, int64_t len) {
  if (!p) return nullptr; auto &s = *session(p); std::string value;
  if (!stringArg(s, text, len, value)) return nullptr;
  auto type = mlir::parseType(value, s.context.get()); if (!type) { s.fail("invalid MLIR type"); return nullptr; }
  return const_cast<void *>(type.getAsOpaquePointer());
}
void *naru_mlir_attr_string(void *p, const char *text, int64_t len) {
  if (!p) return nullptr; auto &s = *session(p); std::string value;
  if (!stringArg(s, text, len, value, true)) return nullptr;
  return const_cast<void *>(mlir::StringAttr::get(s.context.get(), value).getAsOpaquePointer());
}
void *naru_mlir_attr_integer(void *p, void *typePtr, const char *text, int64_t len) {
  if (!p || !typePtr) return nullptr; auto &s = *session(p); std::string value;
  if (!stringArg(s, text, len, value)) return nullptr;
  auto type = mlir::Type::getFromOpaquePointer(typePtr);
  if (!type || type.getContext() != s.context.get()) { s.fail("integer attribute type belongs to another MLIR session"); return nullptr; }
  auto integer = llvm::dyn_cast<mlir::IntegerType>(type);
  unsigned width = integer ? integer.getWidth() : (llvm::isa<mlir::IndexType>(type) ? 64 : 0);
  if (!width) { s.fail("integer attribute requires integer or index type"); return nullptr; }
  std::string typed = value + " : "; llvm::raw_string_ostream stream(typed); type.print(stream);
  auto attr = mlir::parseAttribute(typed, s.context.get());
  if (!attr || !llvm::isa<mlir::IntegerAttr>(attr)) {
    s.fail("invalid or out-of-range integer attribute decimal"); return nullptr;
  }
  return const_cast<void *>(attr.getAsOpaquePointer());
}
void *naru_mlir_attr_parse(void *p, const char *text, int64_t len) {
  if (!p) return nullptr; auto &s = *session(p); std::string value;
  if (!stringArg(s, text, len, value)) return nullptr;
  auto attr = mlir::parseAttribute(value, s.context.get()); if (!attr) { s.fail("invalid MLIR attribute"); return nullptr; }
  return const_cast<void *>(attr.getAsOpaquePointer());
}
void *naru_mlir_region_create(void *p) {
  if (!p) return nullptr; auto &s = *session(p); auto region = std::make_unique<mlir::Region>(); auto *handle = region.get();
  s.looseRegions.emplace(handle, std::move(region)); s.regions.insert(handle); return handle;
}
void *naru_mlir_block_create(void *p, void *const *types, int64_t count, void *loc) {
  if (!p || count < 0 || (count && !types)) return nullptr; auto &s = *session(p);
  auto block = std::make_unique<mlir::Block>();
  for (int64_t i = 0; i < count; ++i) { if (!types[i]) { s.fail("null block argument type"); return nullptr; }
    auto type = mlir::Type::getFromOpaquePointer(types[i]);
    if (!type || type.getContext() != s.context.get()) { s.fail("block argument type belongs to another MLIR session"); return nullptr; }
    block->addArgument(type, location(s, loc)); }
  auto *handle = block.get(); s.looseBlocks.emplace(handle, std::move(block)); s.blocks.insert(handle); return handle;
}
int32_t naru_mlir_region_append_block(void *p, void *r, void *b) {
  if (!p || !r || !b) return 1; auto &s = *session(p); auto *region = static_cast<mlir::Region *>(r); auto *block = static_cast<mlir::Block *>(b);
  if (!s.regions.count(region)) return s.fail("region belongs to another MLIR session");
  if (!s.blocks.count(block)) return s.fail("block belongs to another MLIR session");
  auto found = s.looseBlocks.find(block); if (found == s.looseBlocks.end()) return s.fail("block already owned or invalid");
  region->push_back(found->second.release()); s.looseBlocks.erase(found); return 0;
}
void *naru_mlir_block_argument(void *p, void *b, int64_t index) {
  if (!p || !b) return nullptr; auto &s = *session(p); auto *block = static_cast<mlir::Block *>(b);
  if (!s.blocks.count(block)) { s.fail("block belongs to another MLIR session"); return nullptr; }
  if (index < 0 || static_cast<uint64_t>(index) >= block->getNumArguments()) { s.fail("block argument index out of range"); return nullptr; }
  return block->getArgument(index).getAsOpaquePointer();
}
void *naru_mlir_op_begin(void *p, const char *name, int64_t len, void *loc) {
  if (!p) return nullptr; auto &s = *session(p); std::string value;
  if (!stringArg(s, name, len, value)) return nullptr;
  auto qualified = llvm::StringRef(value);
  auto separator = qualified.find('.');
  if (separator == llvm::StringRef::npos || separator == 0 || separator + 1 == qualified.size()) {
    s.fail("MLIR operation name must be qualified: " + value); return nullptr;
  }
  // Registering a dialect makes it available; a direct builder must explicitly
  // load it before Operation::create. Unknown namespaces are a diagnostic,
  // rather than triggering MLIR's fatal unregistered-dialect assertion.
  if (!s.context->getOrLoadDialect(qualified.take_front(separator))) {
    s.fail("MLIR dialect is not registered: " + qualified.take_front(separator)); return nullptr;
  }
  auto builder = std::make_unique<mlir::OperationState>(location(s, loc), value);
  auto *handle = builder.get(); s.states.emplace(handle, std::move(builder)); return handle;
}
int32_t naru_mlir_op_add_operand(void *p, void *st, void *value) {
  if (!p || !value) return 1; auto &s = *session(p); auto *builder = state(s, st); if (!builder) return 1;
  auto operand = mlir::Value::getFromOpaquePointer(value);
  if (!operand || operand.getType().getContext() != s.context.get()) return s.fail("SSA value belongs to another MLIR session");
  builder->addOperands(operand); return 0;
}
int32_t naru_mlir_op_add_type(void *p, void *st, void *type) {
  if (!p || !type) return 1; auto &s = *session(p); auto *builder = state(s, st); if (!builder) return 1;
  auto resultType = mlir::Type::getFromOpaquePointer(type);
  if (!resultType || resultType.getContext() != s.context.get()) return s.fail("MLIR type belongs to another MLIR session");
  builder->addTypes(resultType); return 0;
}
int32_t naru_mlir_op_add_attribute(void *p, void *st, const char *name, int64_t len, void *attr) {
  if (!p || !attr) return 1; auto &s = *session(p); auto *builder = state(s, st); if (!builder) return 1;
  std::string value; if (!stringArg(s, name, len, value)) return 1;
  auto attribute = mlir::Attribute::getFromOpaquePointer(attr);
  if (!attribute || attribute.getContext() != s.context.get()) return s.fail("MLIR attribute belongs to another MLIR session");
  builder->addAttribute(value, attribute); return 0;
}
int32_t naru_mlir_op_add_region(void *p, void *st, void *r) {
  if (!p || !r) return 1; auto &s = *session(p); auto *builder = state(s, st); if (!builder) return 1;
  auto region = static_cast<mlir::Region *>(r);
  if (!s.regions.count(region)) return s.fail("region belongs to another MLIR session");
  auto found = s.looseRegions.find(region);
  if (found == s.looseRegions.end()) return s.fail("region already owned or invalid");
  builder->addRegion(std::move(found->second)); s.looseRegions.erase(found); return 0;
}
int32_t naru_mlir_op_add_successor(void *p, void *st, void *block) {
  if (!p || !block) return 1; auto &s = *session(p); auto *builder = state(s, st); if (!builder) return 1;
  if (!s.blocks.count(static_cast<mlir::Block *>(block))) return s.fail("successor block belongs to another MLIR session");
  builder->addSuccessors(static_cast<mlir::Block *>(block)); return 0;
}
void *naru_mlir_op_finish(void *p, void *st, void *parent) {
  if (!p || !parent) return nullptr; auto &s = *session(p); auto *builder = state(s, st); if (!builder) return nullptr;
  if (!s.blocks.count(static_cast<mlir::Block *>(parent))) { s.fail("parent block belongs to another MLIR session"); return nullptr; }
  auto *operation = mlir::Operation::create(*builder);
  static_cast<mlir::Block *>(parent)->push_back(operation); s.states.erase(builder); s.operations.insert(operation); return operation;
}
void *naru_mlir_op_result(void *p, void *operation, int64_t index) {
  if (!p || !operation) return nullptr; auto &s = *session(p); auto *op = static_cast<mlir::Operation *>(operation);
  if (!s.operations.count(op)) { s.fail("operation belongs to another MLIR session"); return nullptr; }
  if (index < 0 || static_cast<uint64_t>(index) >= op->getNumResults()) { s.fail("operation result index out of range"); return nullptr; }
  return op->getResult(index).getAsOpaquePointer();
}
