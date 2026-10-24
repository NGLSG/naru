#ifndef NARU_TARGET_TOOLCHAIN_H
#define NARU_TARGET_TOOLCHAIN_H
#include <string>
#include <vector>

// Installation facts are shared by rule frontends and native linking. This
// layer has no source-language parser, declarations or predefined macros.
struct NaruToolchain {
  std::string triple, vcTools, sdkDir, sdkVersion, ucrtDir, ucrtVersion, resourceIncludes;
  std::vector<std::string> includes, libraries;
};
bool naruDiscoverToolchain(NaruToolchain &result, std::string &error);
#endif
