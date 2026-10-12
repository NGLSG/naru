#ifndef NARU_MLIR_BACKEND_H
#define NARU_MLIR_BACKEND_H
#include <stdint.h>
#ifdef _WIN32
#define NARU_API __declspec(dllexport)
#else
#define NARU_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
/* ABI v1: all strings are UTF-8 with explicit byte lengths. All status returns
 * use 0=success, 1=failure. Opaque handles belong to their session. The session
 * owns all MLIR objects, builders and returned strings. No LLVM C++ objects
 * cross into the Vyx LLVM 22 runtime. */
NARU_API int32_t naru_mlir_abi_version(void);
NARU_API void *naru_mlir_create(void);
NARU_API void naru_mlir_destroy(void *session);
NARU_API const char *naru_mlir_error(void *session);
NARU_API int32_t naru_mlir_configure(void *session, const char *json, int64_t len);
NARU_API int32_t naru_mlir_parse(void *session, const char *text, int64_t len, const char *source, int64_t source_len);
NARU_API int32_t naru_mlir_compile(void *session, const char *target, int64_t target_len, const char *output, int64_t output_len);
NARU_API const char *naru_mlir_print(void *session);
NARU_API const char *naru_mlir_module_text(void *session, int32_t generic);
NARU_API int32_t naru_mlir_verify(void *session);
NARU_API int64_t naru_mlir_print_size(void *session);
NARU_API void *naru_mlir_module_body(void *session);
NARU_API void *naru_mlir_location(void *session, const char *file, int64_t len, int64_t line, int64_t column);
NARU_API void *naru_mlir_type_parse(void *session, const char *text, int64_t len);
NARU_API void *naru_mlir_attr_string(void *session, const char *text, int64_t len);
NARU_API void *naru_mlir_attr_integer(void *session, void *type, const char *decimal, int64_t len);
NARU_API void *naru_mlir_attr_parse(void *session, const char *text, int64_t len);
NARU_API void *naru_mlir_region_create(void *session);
NARU_API void *naru_mlir_block_create(void *session, void *const *types, int64_t count, void *location);
NARU_API int32_t naru_mlir_region_append_block(void *session, void *region, void *block);
NARU_API void *naru_mlir_block_argument(void *session, void *block, int64_t index);
NARU_API void *naru_mlir_op_begin(void *session, const char *name, int64_t len, void *location);
NARU_API int32_t naru_mlir_op_add_operand(void *session, void *state, void *value);
NARU_API int32_t naru_mlir_op_add_type(void *session, void *state, void *type);
NARU_API int32_t naru_mlir_op_add_attribute(void *session, void *state, const char *name, int64_t len, void *attribute);
NARU_API int32_t naru_mlir_op_add_region(void *session, void *state, void *region);
NARU_API int32_t naru_mlir_op_add_successor(void *session, void *state, void *block);
NARU_API void *naru_mlir_op_finish(void *session, void *state, void *parent_block);
NARU_API void *naru_mlir_op_result(void *session, void *operation, int64_t index);
/* Exact metaprogramming arithmetic. Result/error strings are thread-local and
 * borrowed until the next call. No source-language types are hardcoded here. */
NARU_API const char *naru_exact_eval(const char *op, int64_t op_len, const char *a, int64_t a_len, const char *b, int64_t b_len, int64_t option);
NARU_API const char *naru_exact_error(void);
NARU_API int32_t naru_exact_flags(void);
/* Native target/SDK facts shared by all rule frontends and the linker. No
 * subprocess and no source-language parsing. Pair-list text is thread-local. */
NARU_API const char *naru_target_toolchain(const char *json, int64_t len);
NARU_API const char *naru_target_error(void);
/* Optional tooling helper: no MLIR session is created. Returns a thread-local
 * lowercase SHA256, or an empty string when the input cannot be read. */
NARU_API const char *naru_file_sha256(const char *path, int64_t len);
#ifdef __cplusplus
}
#endif
#endif
