#include "naru_mlir.h"
#include "mlir/AsmParser/AsmParser.h"
#include "mlir/IR/BuiltinAttributes.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Diagnostics.h"
#include "llvm/ADT/APInt.h"
#include "llvm/ADT/APFloat.h"
#include "llvm/ADT/APSInt.h"
#include "llvm/ADT/SmallString.h"
#include <algorithm>
#include <string>

namespace {
// This is a resource limit on one primitive, not a source integer width.
constexpr unsigned maxBits = 1048576;
thread_local std::string exactResult, exactError;
thread_local int32_t exactFlags;
bool input(const char *p, int64_t n, std::string &out) {
  if (n < 0 || n > maxBits || (n && !p)) { exactError = "invalid exact-number input length"; return false; }
  out.assign(p ? p : "", static_cast<size_t>(n));
  if (out.find('\0') != std::string::npos) { exactError = "NUL in exact-number input"; return false; }
  return true;
}
int digit(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}
bool integer(llvm::StringRef raw, llvm::APInt &magnitude, bool &negative) {
  negative = raw.consume_front("-");
  if (!negative) raw.consume_front("+");
  unsigned radix = 10;
  if (raw.consume_front("0x") || raw.consume_front("0X")) radix = 16;
  else if (raw.consume_front("0b") || raw.consume_front("0B")) radix = 2;
  else if (raw.consume_front("0o") || raw.consume_front("0O")) radix = 8;
  std::string digits;
  for (size_t i = 0; i < raw.size(); ++i) {
    if (raw[i] == '_') {
      if (!i || i + 1 == raw.size() || digit(raw[i - 1]) < 0 || digit(raw[i + 1]) < 0) {
        exactError = "invalid integer digit separator"; return false;
      }
      continue;
    }
    int d = digit(raw[i]);
    if (d < 0 || static_cast<unsigned>(d) >= radix) { exactError = "invalid integer literal"; return false; }
    digits.push_back(raw[i]);
  }
  if (digits.empty() || llvm::StringRef(digits).getAsInteger(radix, magnitude)) {
    exactError = "invalid integer literal"; return false;
  }
  if (magnitude.getActiveBits() > maxBits) { exactError = "exact-number resource limit exceeded"; return false; }
  if (magnitude.isZero()) negative = false;
  return true;
}
std::string decimal(const llvm::APInt &bits, bool isSigned) {
  llvm::SmallString<64> text;
  bits.toString(text, 10, isSigned);
  return text.str().str();
}
bool floating(llvm::StringRef raw, llvm::StringRef typeName, int64_t rounding) {
  // Builtin floating formats are queried through MLIR, rather than enumerating
  // a language's source type names. Custom types can supply their own rules.
  mlir::MLIRContext context;
  mlir::ScopedDiagnosticHandler diagnostics(&context, [](mlir::Diagnostic &) { return mlir::success(); });
  auto type = llvm::dyn_cast_or_null<mlir::FloatType>(mlir::parseType(typeName, &context));
  if (!type) { exactError = "floating primitive requires an MLIR floating type"; return false; }
  if (rounding < 0 || rounding > 4) { exactError = "unknown floating rounding mode"; return false; }
  llvm::APFloat::roundingMode modes[] = {llvm::APFloat::rmNearestTiesToEven, llvm::APFloat::rmTowardZero,
      llvm::APFloat::rmTowardPositive, llvm::APFloat::rmTowardNegative, llvm::APFloat::rmNearestTiesToAway};
  std::string clean;
  for (size_t i = 0; i < raw.size(); ++i) {
    if (raw[i] == '_') {
      if (!i || i + 1 == raw.size() || raw[i - 1] < '0' || raw[i - 1] > '9' || raw[i + 1] < '0' || raw[i + 1] > '9') {
        exactError = "invalid floating digit separator"; return false;
      }
    } else clean.push_back(raw[i]);
  }
  llvm::APFloat value(type.getFloatSemantics());
  auto status = value.convertFromString(clean, modes[rounding]);
  if (!status) { exactError = llvm::toString(status.takeError()); return false; }
  exactFlags = static_cast<int32_t>(*status);
  auto attr = mlir::FloatAttr::get(type, value);
  llvm::raw_string_ostream stream(exactResult);
  attr.print(stream);
  return true;
}

// These operations work on typed MLIR attributes, preserving the source
// format's bits rather than passing through the host's double precision.
// Status flags are facts; source-language rules choose their error policy.
bool floatingOperation(llvm::StringRef op, llvm::StringRef aText,
                       llvm::StringRef bText, int64_t option) {
  mlir::MLIRContext context;
  mlir::ScopedDiagnosticHandler diagnostics(&context, [](mlir::Diagnostic &) { return mlir::success(); });
  llvm::APFloat::roundingMode modes[] = {llvm::APFloat::rmNearestTiesToEven, llvm::APFloat::rmTowardZero,
      llvm::APFloat::rmTowardPositive, llvm::APFloat::rmTowardNegative, llvm::APFloat::rmNearestTiesToAway};
  bool rounded = op != "float.to_int" && op != "float.compare" && op != "float.neg";
  if (rounded && (option < 0 || option > 4)) { exactError = "unknown floating rounding mode"; return false; }
  auto print = [&](mlir::FloatType type, const llvm::APFloat &value) {
    llvm::raw_string_ostream stream(exactResult);
    mlir::FloatAttr::get(type, value).print(stream);
  };
  if (op == "float.from_int") {
    auto type = llvm::dyn_cast_or_null<mlir::FloatType>(mlir::parseType(bText, &context));
    if (!type) { exactError = "floating primitive requires an MLIR floating type"; return false; }
    llvm::APInt bits(1, 0); bool negative = false;
    if (!integer(aText, bits, negative)) return false;
    unsigned width = bits.getActiveBits() + 1;
    if (width > maxBits) { exactError = "exact-number resource limit exceeded"; return false; }
    bits = bits.zextOrTrunc(width);
    if (negative) bits = -bits;
    llvm::APFloat value(type.getFloatSemantics());
    exactFlags = static_cast<int32_t>(value.convertFromAPInt(bits, true, modes[option]));
    print(type, value); return true;
  }
  auto attr = llvm::dyn_cast_or_null<mlir::FloatAttr>(mlir::parseAttribute(aText, &context));
  if (!attr) { exactError = "floating primitive requires a typed MLIR floating attribute"; return false; }
  auto type = llvm::cast<mlir::FloatType>(attr.getType());
  llvm::APFloat value = attr.getValue();
  if (op == "float.to_int") {
    llvm::APInt widthBits(1, 0); bool negative = false;
    if (!integer(bText, widthBits, negative)) return false;
    if (negative || widthBits.getActiveBits() > 21 || widthBits.isZero() || widthBits.getZExtValue() > maxBits) {
      exactError = "integer width exceeds exact-number resource limit or is zero"; return false;
    }
    if (option != 0 && option != 1) { exactError = "signedness must be 0 or 1"; return false; }
    llvm::APSInt result(static_cast<unsigned>(widthBits.getZExtValue()), option == 0);
    bool exact = false;
    exactFlags = static_cast<int32_t>(value.convertToInteger(result, llvm::APFloat::rmTowardZero, &exact));
    exactResult = decimal(result, option == 1); return true;
  }
  if (op == "float.convert") {
    auto target = llvm::dyn_cast_or_null<mlir::FloatType>(mlir::parseType(bText, &context));
    if (!target) { exactError = "floating primitive requires an MLIR floating type"; return false; }
    bool losesInfo = false;
    exactFlags = static_cast<int32_t>(value.convert(target.getFloatSemantics(), modes[option], &losesInfo));
    print(target, value); return true;
  }
  if (op == "float.neg") { value.changeSign(); print(type, value); return true; }
  auto other = llvm::dyn_cast_or_null<mlir::FloatAttr>(mlir::parseAttribute(bText, &context));
  if (!other || other.getType() != type) { exactError = "floating operands require the same MLIR format"; return false; }
  if (op == "float.compare") {
    auto comparison = value.compare(other.getValue());
    exactResult = comparison == llvm::APFloat::cmpLessThan ? "-1" :
        comparison == llvm::APFloat::cmpEqual ? "0" : comparison == llvm::APFloat::cmpGreaterThan ? "1" : "2";
    return true;
  }
  if (op == "float.add") exactFlags = value.add(other.getValue(), modes[option]);
  else if (op == "float.sub") exactFlags = value.subtract(other.getValue(), modes[option]);
  else if (op == "float.mul") exactFlags = value.multiply(other.getValue(), modes[option]);
  else if (op == "float.div") exactFlags = value.divide(other.getValue(), modes[option]);
  else { exactError = "unknown floating operation"; return false; }
  print(type, value); return true;
}
}

const char *naru_exact_eval(const char *opData, int64_t opLen, const char *aData, int64_t aLen,
                          const char *bData, int64_t bLen, int64_t option) {
  exactResult.clear(); exactError.clear(); exactFlags = 0;
  std::string op, aText, bText;
  if (!input(opData, opLen, op) || !input(aData, aLen, aText) || !input(bData, bLen, bText)) return nullptr;
  if (op == "float.attr") return floating(aText, bText, option) ? exactResult.c_str() : nullptr;
  if (llvm::StringRef(op).starts_with("float.")) return floatingOperation(op, aText, bText, option) ? exactResult.c_str() : nullptr;
  llvm::APInt a(1, 0), b(1, 0);
  bool an = false, bn = false;
  if (!integer(aText, a, an)) return nullptr;
  if (op == "parse" || op == "neg") {
    if (op == "neg" && !a.isZero()) an = !an;
    exactResult = (an ? "-" : "") + decimal(a, false); return exactResult.c_str();
  }
  if (!integer(bText, b, bn)) return nullptr;
  if (op == "fits") {
    if (bn || b.getActiveBits() > 21 || b.getZExtValue() == 0 || b.getZExtValue() > maxBits) {
      exactError = "integer width exceeds exact-number resource limit or is zero"; return nullptr;
    }
    unsigned width = static_cast<unsigned>(b.getZExtValue());
    bool fits = !an && a.getActiveBits() <= width;
    if (option == 1) {
      fits = an ? (a.getActiveBits() < width || (a.isPowerOf2() && a.getActiveBits() == width)) : a.getActiveBits() < width;
    } else if (option != 0) { exactError = "signedness must be 0 or 1"; return nullptr; }
    exactResult = fits ? "1" : "0"; return exactResult.c_str();
  }
  unsigned width = std::max(a.getActiveBits(), b.getActiveBits()) + 2;
  if (op == "mul") width = a.getActiveBits() + b.getActiveBits() + 2;
  if (op == "shl" || op == "shr") {
    if (bn || b.getActiveBits() > 21 || b.getZExtValue() > maxBits) { exactError = "invalid shift amount"; return nullptr; }
    width += static_cast<unsigned>(b.getZExtValue());
  }
  if (width > maxBits) { exactError = "exact-number resource limit exceeded"; return nullptr; }
  a = a.zextOrTrunc(width); b = b.zextOrTrunc(width);
  if (an) a = -a;
  if (bn) b = -b;
  llvm::APInt result(width, 0);
  if (op == "add") result = a + b;
  else if (op == "sub") result = a - b;
  else if (op == "mul") result = a * b;
  else if (op == "div" || op == "rem") {
    if (b.isZero()) { exactError = "exact integer division by zero"; return nullptr; }
    result = op == "div" ? a.sdiv(b) : a.srem(b);
  } else if (op == "and") result = a & b;
  else if (op == "or") result = a | b;
  else if (op == "xor") result = a ^ b;
  else if (op == "shl") result = a.shl(static_cast<unsigned>(b.getZExtValue()));
  else if (op == "shr") result = a.ashr(static_cast<unsigned>(b.getZExtValue()));
  else if (op == "lt") { exactResult = a.slt(b) ? "1" : "0"; return exactResult.c_str(); }
  else { exactError = "unknown exact integer operation"; return nullptr; }
  exactResult = decimal(result, true);
  return exactResult.c_str();
}
const char *naru_exact_error() { return exactError.c_str(); }
int32_t naru_exact_flags() { return exactFlags; }
