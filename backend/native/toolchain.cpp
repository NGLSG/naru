#include "naru_mlir.h"
#include "toolchain.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/VirtualFileSystem.h"
#include "llvm/TargetParser/Host.h"
#include "llvm/TargetParser/Triple.h"
#include "llvm/WindowsDriver/MSVCPaths.h"
#include <algorithm>
#include <cstdlib>
#include <filesystem>

namespace fs = std::filesystem;
namespace {
thread_local std::string resultText, errorText;
void addDirectory(std::vector<std::string> &paths, const std::string &name) {
  if (name.empty()) return;
  std::error_code ec;
  auto path = fs::absolute(fs::u8path(name), ec).lexically_normal();
  if (ec || !fs::is_directory(path, ec)) return;
  auto text = path.u8string();
  if (std::find(paths.begin(), paths.end(), text) == paths.end()) paths.push_back(text);
}
bool options(NaruToolchain &out, const llvm::json::Object &object,
             const std::string &base = "") {
  for (auto entry : {std::make_pair("triple", &out.triple),
      {"vc_tools_dir", &out.vcTools}, {"windows_sdk_dir", &out.sdkDir},
      {"windows_sdk_version", &out.sdkVersion}}) {
    auto *field = object.get(entry.first);
    if (!field) continue;
    auto value = field->getAsString();
    if (!value || value->contains('\0')) { errorText = "invalid target option: " + std::string(entry.first); return false; }
    *entry.second = value->str();
    if (!base.empty() && (entry.second == &out.vcTools || entry.second == &out.sdkDir)
        && !value->empty() && fs::u8path(*entry.second).is_relative())
      *entry.second = (fs::u8path(base) / fs::u8path(*entry.second)).u8string();
  }
  return true;
}
llvm::json::Array strings(const std::vector<std::string> &values) {
  llvm::json::Array out; for (const auto &value : values) out.push_back(value); return out;
}
}

bool naruDiscoverToolchain(NaruToolchain &out, std::string &error) {
  if (out.triple.empty()) out.triple = llvm::sys::getDefaultTargetTriple();
  out.triple = llvm::Triple::normalize(out.triple);
  llvm::Triple triple(out.triple);
  if (!triple.isOSWindows()) return true; // Other targets may supply explicit sysroots.
  auto vfs = llvm::vfs::getRealFileSystem();
  llvm::ToolsetLayout layout = llvm::ToolsetLayout::VS2017OrNewer;
  if (out.vcTools.empty()) {
    if (!llvm::findVCToolChainViaEnvironment(*vfs, out.vcTools, layout))
      if (!llvm::findVCToolChainViaSetupConfig(*vfs, std::nullopt, out.vcTools, layout))
        llvm::findVCToolChainViaRegistry(out.vcTools, layout);
  } else {
    std::error_code ec;
    if (!fs::is_directory(fs::u8path(out.vcTools), ec)) { error = "VC tools directory does not exist: " + out.vcTools; return false; }
  }
  if (!out.vcTools.empty()) {
    addDirectory(out.includes, llvm::getSubDirectoryPath(llvm::SubDirectoryType::Include, layout, out.vcTools, triple.getArch()));
    addDirectory(out.libraries, llvm::getSubDirectoryPath(llvm::SubDirectoryType::Lib, layout, out.vcTools, triple.getArch()));
  }
  // Driver APIs borrow these views; preserve the override strings throughout
  // both SDK queries. Discovery must not invalidate a view by changing out.
  const std::string sdkOverride = out.sdkDir, versionOverride = out.sdkVersion;
  std::optional<llvm::StringRef> directory, version;
  if (!sdkOverride.empty()) directory = sdkOverride;
  if (!versionOverride.empty()) version = versionOverride;
  std::string sdk, includeVersion, libraryVersion;
  int major = 0;
  if (llvm::getWindowsSDKDir(*vfs, directory, version, std::nullopt,
                            sdk, major, includeVersion, libraryVersion)) {
    out.sdkDir = sdk; out.sdkVersion = libraryVersion;
    for (const auto *part : {"shared", "um", "winrt"})
      addDirectory(out.includes, (fs::u8path(sdk) / "Include" / includeVersion / part).u8string());
    addDirectory(out.libraries, (fs::u8path(sdk) / "Lib" / libraryVersion / "um" / llvm::archToWindowsSDKArch(triple.getArch())).u8string());
  } else if (!sdkOverride.empty() || !versionOverride.empty()) {
    error = "Windows SDK override cannot be resolved: " + sdkOverride + " " + versionOverride; return false;
  }
  if (llvm::getUniversalCRTSdkDir(*vfs, directory, version, std::nullopt, out.ucrtDir, out.ucrtVersion)) {
    // UCRT headers precede platform headers; VC's compiler-specific headers
    // stay first, exactly as in the native compiler's search order.
    std::vector<std::string> ucrt;
    addDirectory(ucrt, (fs::u8path(out.ucrtDir) / "Include" / out.ucrtVersion / "ucrt").u8string());
    auto pos = out.includes.empty() || out.vcTools.empty() ? out.includes.begin() : out.includes.begin() + 1;
    out.includes.insert(pos, ucrt.begin(), ucrt.end());
    addDirectory(out.libraries, (fs::u8path(out.ucrtDir) / "Lib" / out.ucrtVersion / "ucrt" / llvm::archToWindowsSDKArch(triple.getArch())).u8string());
  }
  return true;
}

const char *naru_target_toolchain(const char *json, int64_t length) {
  resultText.clear(); errorText.clear();
  if (length < 0 || (length && !json)) { errorText = "invalid target configuration"; return nullptr; }
  auto parsed = llvm::json::parse(llvm::StringRef(json ? json : "", static_cast<size_t>(length)));
  if (!parsed) { errorText = llvm::toString(parsed.takeError()); return nullptr; }
  auto *object = parsed->getAsObject();
  if (!object) { errorText = "target configuration must be an object"; return nullptr; }
  NaruToolchain info;
  if (auto target = object->getString("target")) {
    if (*target != "mlir" && *target != "llvm-ir" && *target != "object" && *target != "exe" && *target != "bytecode") {
      auto file = llvm::MemoryBuffer::getFile(*target);
      if (!file) { errorText = "cannot read target profile: " + target->str(); return nullptr; }
      auto profile = llvm::json::parse((*file)->getBuffer());
      if (!profile) { errorText = llvm::toString(profile.takeError()); return nullptr; }
      auto *config = profile->getAsObject();
      if (!config) { errorText = "target profile must be an object"; return nullptr; }
      if (!options(info, *config, fs::u8path(target->str()).parent_path().u8string())) return nullptr;
    }
  }
  if (!options(info, *object) || !naruDiscoverToolchain(info, errorText)) return nullptr;
  llvm::Triple triple(info.triple);
  // Pair lists are a neutral wire format understood by the rule term parser.
  llvm::json::Array pairs;
  pairs.push_back(llvm::json::Array{"triple", info.triple});
  pairs.push_back(llvm::json::Array{"architecture", triple.getArchName().str()});
  pairs.push_back(llvm::json::Array{"os", triple.getOSName().str()});
  pairs.push_back(llvm::json::Array{"pointer_bits", triple.isArch64Bit() ? 64 : triple.isArch32Bit() ? 32 : 16});
  pairs.push_back(llvm::json::Array{"little_endian", triple.isLittleEndian() ? 1 : 0});
  pairs.push_back(llvm::json::Array{"include_paths", strings(info.includes)});
  pairs.push_back(llvm::json::Array{"library_paths", strings(info.libraries)});
  pairs.push_back(llvm::json::Array{"vc_tools_dir", info.vcTools});
  pairs.push_back(llvm::json::Array{"windows_sdk_dir", info.sdkDir});
  pairs.push_back(llvm::json::Array{"windows_sdk_version", info.sdkVersion});
  pairs.push_back(llvm::json::Array{"ucrt_dir", info.ucrtDir});
  pairs.push_back(llvm::json::Array{"ucrt_version", info.ucrtVersion});
  resultText = llvm::formatv("{0}", llvm::json::Value(std::move(pairs))).str();
  return resultText.c_str();
}
const char *naru_target_error(void) { return errorText.c_str(); }
