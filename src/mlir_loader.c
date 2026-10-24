/* In-process MLIR bridge loader. The LLVM 24 C++ ABI stays inside its DLL. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#ifdef _WIN32
#include <windows.h>
#include <wchar.h>
static HMODULE backend_library;
#else
#include <dlfcn.h>
static void *backend_library;
extern const char *naru_exe_path(void);
#endif
static char backend_error[2048] = "MLIR backend is not loaded";
typedef const char *(*exact_eval_fn)(const char *, int64_t, const char *, int64_t, const char *, int64_t, int64_t);
typedef const char *(*exact_error_fn)(void);
typedef int32_t (*exact_flags_fn)(void);
static exact_eval_fn p_naru_exact_eval;
static exact_error_fn p_naru_exact_error;
static exact_flags_fn p_naru_exact_flags;
typedef const char *(*target_toolchain_fn)(const char *, int64_t);
static target_toolchain_fn p_naru_target_toolchain;
static exact_error_fn p_naru_target_error;
static exact_error_fn p_naru_host_clock_snapshot;
typedef void * (*naru_mlir_create_fn)(void);
static naru_mlir_create_fn p_naru_mlir_create;
typedef void (*naru_mlir_destroy_fn)(void *session);
static naru_mlir_destroy_fn p_naru_mlir_destroy;
typedef const char * (*naru_mlir_error_fn)(void *session);
static naru_mlir_error_fn p_naru_mlir_error;
typedef int32_t (*naru_mlir_configure_fn)(void *session, const char *json, int64_t len);
static naru_mlir_configure_fn p_naru_mlir_configure;
typedef int32_t (*naru_mlir_parse_fn)(void *session, const char *text, int64_t len, const char *source, int64_t source_len);
static naru_mlir_parse_fn p_naru_mlir_parse;
typedef int32_t (*naru_mlir_compile_fn)(void *session, const char *target, int64_t target_len, const char *output, int64_t output_len);
static naru_mlir_compile_fn p_naru_mlir_compile;
typedef const char * (*naru_mlir_print_fn)(void *session);
static naru_mlir_print_fn p_naru_mlir_print;
typedef int64_t (*naru_mlir_print_size_fn)(void *session);
static naru_mlir_print_size_fn p_naru_mlir_print_size;
typedef const char * (*naru_mlir_module_text_fn)(void *session, int32_t generic);
static naru_mlir_module_text_fn p_naru_mlir_module_text;
typedef int32_t (*naru_mlir_verify_fn)(void *session);
static naru_mlir_verify_fn p_naru_mlir_verify;
typedef void * (*naru_mlir_module_body_fn)(void *session);
static naru_mlir_module_body_fn p_naru_mlir_module_body;
typedef void * (*naru_mlir_location_fn)(void *session, const char *file, int64_t len, int64_t line, int64_t column);
static naru_mlir_location_fn p_naru_mlir_location;
typedef void * (*naru_mlir_type_parse_fn)(void *session, const char *text, int64_t len);
static naru_mlir_type_parse_fn p_naru_mlir_type_parse;
typedef void * (*naru_mlir_attr_string_fn)(void *session, const char *text, int64_t len);
static naru_mlir_attr_string_fn p_naru_mlir_attr_string;
typedef void * (*naru_mlir_attr_integer_fn)(void *session, void *type, const char *decimal, int64_t len);
static naru_mlir_attr_integer_fn p_naru_mlir_attr_integer;
typedef void * (*naru_mlir_attr_parse_fn)(void *session, const char *text, int64_t len);
static naru_mlir_attr_parse_fn p_naru_mlir_attr_parse;
typedef void * (*naru_mlir_region_create_fn)(void *session);
static naru_mlir_region_create_fn p_naru_mlir_region_create;
typedef void * (*naru_mlir_block_create_fn)(void *session, void *const *types, int64_t count, void *location);
static naru_mlir_block_create_fn p_naru_mlir_block_create;
typedef int32_t (*naru_mlir_region_append_block_fn)(void *session, void *region, void *block);
static naru_mlir_region_append_block_fn p_naru_mlir_region_append_block;
typedef void * (*naru_mlir_block_argument_fn)(void *session, void *block, int64_t index);
static naru_mlir_block_argument_fn p_naru_mlir_block_argument;
typedef void * (*naru_mlir_op_begin_fn)(void *session, const char *name, int64_t len, void *location);
static naru_mlir_op_begin_fn p_naru_mlir_op_begin;
typedef int32_t (*naru_mlir_op_add_operand_fn)(void *session, void *state, void *value);
static naru_mlir_op_add_operand_fn p_naru_mlir_op_add_operand;
typedef int32_t (*naru_mlir_op_add_type_fn)(void *session, void *state, void *type);
static naru_mlir_op_add_type_fn p_naru_mlir_op_add_type;
typedef int32_t (*naru_mlir_op_add_attribute_fn)(void *session, void *state, const char *name, int64_t len, void *attribute);
static naru_mlir_op_add_attribute_fn p_naru_mlir_op_add_attribute;
typedef int32_t (*naru_mlir_op_add_region_fn)(void *session, void *state, void *region);
static naru_mlir_op_add_region_fn p_naru_mlir_op_add_region;
typedef int32_t (*naru_mlir_op_add_successor_fn)(void *session, void *state, void *block);
static naru_mlir_op_add_successor_fn p_naru_mlir_op_add_successor;
typedef void * (*naru_mlir_op_finish_fn)(void *session, void *state, void *parent_block);
static naru_mlir_op_finish_fn p_naru_mlir_op_finish;
typedef void * (*naru_mlir_op_result_fn)(void *session, void *operation, int64_t index);
static naru_mlir_op_result_fn p_naru_mlir_op_result;
typedef int32_t (*abi_version_fn)(void);
int32_t naru_mlir_open(const char *path, int64_t length);
static void *find_symbol(const char *name) {
#ifdef _WIN32
    return (void *)GetProcAddress(backend_library, name);
#else
    return dlsym(backend_library, name);
#endif
}
const char *naru_file_sha256(const char *path, int64_t length) {
    typedef const char *(*hash_fn)(const char *, int64_t);
    if (naru_mlir_open(NULL, 0)) return "";
    hash_fn function = (hash_fn)find_symbol("naru_file_sha256");
    return function ? function(path, length) : "";
}
int32_t naru_mlir_open(const char *path, int64_t length) {
    if (backend_library) return 0;
    if (length < 0 || length > INT_MAX || (length && (!path || memchr(path, 0, (size_t)length)))) {
        snprintf(backend_error, sizeof(backend_error), "Invalid MLIR backend library path");
        return 1;
    }
#ifdef _WIN32
    wchar_t *library_path = NULL;
    wchar_t default_path[32768];
    if (!length) {
        const char *override = getenv("NARU_MLIR_BACKEND");
        if (override && *override) { path = override; length = (int64_t)strlen(override); }
    }
    if (length) {
        int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, (int)length, NULL, 0);
        if (!count) return 1;
        library_path = (wchar_t *)calloc((size_t)count + 1, sizeof(wchar_t));
        if (!library_path) return 1;
        MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, (int)length, library_path, count);
    } else {
        DWORD count = GetModuleFileNameW(NULL, default_path, 32768);
        if (!count || count >= 32768) return 1;
        wchar_t *slash = wcsrchr(default_path, L'\\');
        if (!slash || (size_t)(slash - default_path) + 32 >= 32768) return 1;
        wcscpy(slash + 1, L"naru_mlir_backend.dll");
        library_path = default_path;
    }
    backend_library = LoadLibraryExW(library_path, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (library_path != default_path) free(library_path);
    if (!backend_library) {
        snprintf(backend_error, sizeof(backend_error), "Cannot load naru_mlir_backend.dll (Windows error %lu). Build the native backend with build.ps1.", (unsigned long)GetLastError());
        return 1;
    }
#else
    char local[4096];
    if (!length) {
        const char *override = getenv("NARU_MLIR_BACKEND");
        if (override && *override) { path = override; length = (int64_t)strlen(override); }
        else {
            snprintf(local, sizeof(local), "%s", naru_exe_path());
            char *slash = strrchr(local, '/');
            if (!slash) return 1;
            snprintf(slash + 1, sizeof(local) - (size_t)(slash + 1 - local), "libnaru_mlir_backend.so");
            path = local; length = (int64_t)strlen(path);
        }
    }
    char *name = (char *)calloc((size_t)length + 1, 1);
    if (!name) return 1;
    memcpy(name, path, (size_t)length);
    backend_library = dlopen(name, RTLD_NOW | RTLD_LOCAL);
    free(name);
    if (!backend_library) { snprintf(backend_error, sizeof(backend_error), "Cannot load MLIR backend: %s", dlerror()); return 1; }
#endif
    abi_version_fn version = (abi_version_fn)find_symbol("naru_mlir_abi_version");
    if (!version || version() != 1) { snprintf(backend_error, sizeof(backend_error), "Incompatible MLIR bridge ABI: expected 1"); goto failure; }
    p_naru_mlir_create = (naru_mlir_create_fn)find_symbol("naru_mlir_create");
    if (!p_naru_mlir_create) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_create"); goto failure; }
    p_naru_mlir_destroy = (naru_mlir_destroy_fn)find_symbol("naru_mlir_destroy");
    if (!p_naru_mlir_destroy) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_destroy"); goto failure; }
    p_naru_mlir_error = (naru_mlir_error_fn)find_symbol("naru_mlir_error");
    if (!p_naru_mlir_error) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_error"); goto failure; }
    p_naru_mlir_configure = (naru_mlir_configure_fn)find_symbol("naru_mlir_configure");
    if (!p_naru_mlir_configure) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_configure"); goto failure; }
    p_naru_mlir_parse = (naru_mlir_parse_fn)find_symbol("naru_mlir_parse");
    if (!p_naru_mlir_parse) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_parse"); goto failure; }
    p_naru_mlir_compile = (naru_mlir_compile_fn)find_symbol("naru_mlir_compile");
    if (!p_naru_mlir_compile) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_compile"); goto failure; }
    p_naru_mlir_print = (naru_mlir_print_fn)find_symbol("naru_mlir_print");
    if (!p_naru_mlir_print) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_print"); goto failure; }
    p_naru_mlir_print_size = (naru_mlir_print_size_fn)find_symbol("naru_mlir_print_size");
    if (!p_naru_mlir_print_size) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_print_size"); goto failure; }
    p_naru_mlir_module_text = (naru_mlir_module_text_fn)find_symbol("naru_mlir_module_text");
    if (!p_naru_mlir_module_text) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_module_text"); goto failure; }
    p_naru_mlir_verify = (naru_mlir_verify_fn)find_symbol("naru_mlir_verify");
    if (!p_naru_mlir_verify) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_verify"); goto failure; }
    p_naru_mlir_module_body = (naru_mlir_module_body_fn)find_symbol("naru_mlir_module_body");
    if (!p_naru_mlir_module_body) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_module_body"); goto failure; }
    p_naru_mlir_location = (naru_mlir_location_fn)find_symbol("naru_mlir_location");
    if (!p_naru_mlir_location) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_location"); goto failure; }
    p_naru_mlir_type_parse = (naru_mlir_type_parse_fn)find_symbol("naru_mlir_type_parse");
    if (!p_naru_mlir_type_parse) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_type_parse"); goto failure; }
    p_naru_mlir_attr_string = (naru_mlir_attr_string_fn)find_symbol("naru_mlir_attr_string");
    if (!p_naru_mlir_attr_string) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_attr_string"); goto failure; }
    p_naru_mlir_attr_integer = (naru_mlir_attr_integer_fn)find_symbol("naru_mlir_attr_integer");
    if (!p_naru_mlir_attr_integer) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_attr_integer"); goto failure; }
    p_naru_mlir_attr_parse = (naru_mlir_attr_parse_fn)find_symbol("naru_mlir_attr_parse");
    if (!p_naru_mlir_attr_parse) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_attr_parse"); goto failure; }
    p_naru_mlir_region_create = (naru_mlir_region_create_fn)find_symbol("naru_mlir_region_create");
    if (!p_naru_mlir_region_create) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_region_create"); goto failure; }
    p_naru_mlir_block_create = (naru_mlir_block_create_fn)find_symbol("naru_mlir_block_create");
    if (!p_naru_mlir_block_create) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_block_create"); goto failure; }
    p_naru_mlir_region_append_block = (naru_mlir_region_append_block_fn)find_symbol("naru_mlir_region_append_block");
    if (!p_naru_mlir_region_append_block) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_region_append_block"); goto failure; }
    p_naru_mlir_block_argument = (naru_mlir_block_argument_fn)find_symbol("naru_mlir_block_argument");
    if (!p_naru_mlir_block_argument) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_block_argument"); goto failure; }
    p_naru_mlir_op_begin = (naru_mlir_op_begin_fn)find_symbol("naru_mlir_op_begin");
    if (!p_naru_mlir_op_begin) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_op_begin"); goto failure; }
    p_naru_mlir_op_add_operand = (naru_mlir_op_add_operand_fn)find_symbol("naru_mlir_op_add_operand");
    if (!p_naru_mlir_op_add_operand) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_op_add_operand"); goto failure; }
    p_naru_mlir_op_add_type = (naru_mlir_op_add_type_fn)find_symbol("naru_mlir_op_add_type");
    if (!p_naru_mlir_op_add_type) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_op_add_type"); goto failure; }
    p_naru_mlir_op_add_attribute = (naru_mlir_op_add_attribute_fn)find_symbol("naru_mlir_op_add_attribute");
    if (!p_naru_mlir_op_add_attribute) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_op_add_attribute"); goto failure; }
    p_naru_mlir_op_add_region = (naru_mlir_op_add_region_fn)find_symbol("naru_mlir_op_add_region");
    if (!p_naru_mlir_op_add_region) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_op_add_region"); goto failure; }
    p_naru_mlir_op_add_successor = (naru_mlir_op_add_successor_fn)find_symbol("naru_mlir_op_add_successor");
    if (!p_naru_mlir_op_add_successor) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_op_add_successor"); goto failure; }
    p_naru_mlir_op_finish = (naru_mlir_op_finish_fn)find_symbol("naru_mlir_op_finish");
    if (!p_naru_mlir_op_finish) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_op_finish"); goto failure; }
    p_naru_mlir_op_result = (naru_mlir_op_result_fn)find_symbol("naru_mlir_op_result");
    if (!p_naru_mlir_op_result) { snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing naru_mlir_op_result"); goto failure; }
    backend_error[0] = 0;
    p_naru_exact_eval = (exact_eval_fn)find_symbol("naru_exact_eval");
    p_naru_exact_error = (exact_error_fn)find_symbol("naru_exact_error");
    p_naru_exact_flags = (exact_flags_fn)find_symbol("naru_exact_flags");
    if (!p_naru_exact_eval || !p_naru_exact_error || !p_naru_exact_flags) {
        snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing the exact-number toolkit"); goto failure;
    }
    return 0;
failure:
#ifdef _WIN32
    FreeLibrary(backend_library);
#else
    dlclose(backend_library);
#endif
    backend_library = NULL;
    return 1;
}
void * naru_mlir_create(void) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_create();
}
void naru_mlir_destroy(void *session) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return;
    p_naru_mlir_destroy(session);
}
const char * naru_mlir_error(void *session) {
    if (!session || !backend_library) return backend_error;
    return p_naru_mlir_error(session);
}
int32_t naru_mlir_configure(void *session, const char *json, int64_t len) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_configure(session, json, len);
}
int32_t naru_mlir_parse(void *session, const char *text, int64_t len, const char *source, int64_t source_len) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_parse(session, text, len, source, source_len);
}
int32_t naru_mlir_compile(void *session, const char *target, int64_t target_len, const char *output, int64_t output_len) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_compile(session, target, target_len, output, output_len);
}
const char * naru_mlir_print(void *session) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_print(session);
}
int64_t naru_mlir_print_size(void *session) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 0;
    return p_naru_mlir_print_size(session);
}
const char * naru_mlir_module_text(void *session, int32_t generic) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_module_text(session, generic);
}
int32_t naru_mlir_verify(void *session) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_verify(session);
}
void * naru_mlir_module_body(void *session) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_module_body(session);
}
void * naru_mlir_location(void *session, const char *file, int64_t len, int64_t line, int64_t column) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_location(session, file, len, line, column);
}
void * naru_mlir_type_parse(void *session, const char *text, int64_t len) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_type_parse(session, text, len);
}
void * naru_mlir_attr_string(void *session, const char *text, int64_t len) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_attr_string(session, text, len);
}
void * naru_mlir_attr_integer(void *session, void *type, const char *decimal, int64_t len) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_attr_integer(session, type, decimal, len);
}
void * naru_mlir_attr_parse(void *session, const char *text, int64_t len) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_attr_parse(session, text, len);
}
void * naru_mlir_region_create(void *session) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_region_create(session);
}
void * naru_mlir_block_create(void *session, void *const *types, int64_t count, void *location) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_block_create(session, types, count, location);
}
int32_t naru_mlir_region_append_block(void *session, void *region, void *block) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_region_append_block(session, region, block);
}
void * naru_mlir_block_argument(void *session, void *block, int64_t index) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_block_argument(session, block, index);
}
void * naru_mlir_op_begin(void *session, const char *name, int64_t len, void *location) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_op_begin(session, name, len, location);
}
int32_t naru_mlir_op_add_operand(void *session, void *state, void *value) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_op_add_operand(session, state, value);
}
int32_t naru_mlir_op_add_type(void *session, void *state, void *type) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_op_add_type(session, state, type);
}
int32_t naru_mlir_op_add_attribute(void *session, void *state, const char *name, int64_t len, void *attribute) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_op_add_attribute(session, state, name, len, attribute);
}
int32_t naru_mlir_op_add_region(void *session, void *state, void *region) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_op_add_region(session, state, region);
}
int32_t naru_mlir_op_add_successor(void *session, void *state, void *block) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return 1;
    return p_naru_mlir_op_add_successor(session, state, block);
}
void * naru_mlir_op_finish(void *session, void *state, void *parent_block) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_op_finish(session, state, parent_block);
}
void * naru_mlir_op_result(void *session, void *operation, int64_t index) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_mlir_op_result(session, operation, index);
}
const char *naru_exact_eval(const char *op, int64_t op_len, const char *a, int64_t a_len, const char *b, int64_t b_len, int64_t option) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    return p_naru_exact_eval(op, op_len, a, a_len, b, b_len, option);
}
const char *naru_exact_error(void) {
    if (!backend_library) return backend_error;
    return p_naru_exact_error();
}
int32_t naru_exact_flags(void) { return backend_library ? p_naru_exact_flags() : 0; }

const char *naru_target_toolchain(const char *json, int64_t len) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    if (!p_naru_target_toolchain) {
        p_naru_target_toolchain = (target_toolchain_fn)find_symbol("naru_target_toolchain");
        p_naru_target_error = (exact_error_fn)find_symbol("naru_target_error");
        if (!p_naru_target_toolchain || !p_naru_target_error) {
            snprintf(backend_error, sizeof(backend_error), "Native backend lacks target discovery; rebuild with build.ps1");
            return NULL;
        }
    }
    return p_naru_target_toolchain(json, len);
}
const char *naru_target_error(void) {
    return p_naru_target_error ? p_naru_target_error() : backend_error;
}
const char *naru_host_clock_snapshot(void) {
    if (!backend_library && naru_mlir_open(NULL, 0)) return NULL;
    if (!p_naru_host_clock_snapshot) {
        p_naru_host_clock_snapshot = (exact_error_fn)find_symbol("naru_host_clock_snapshot");
        p_naru_target_error = (exact_error_fn)find_symbol("naru_target_error");
        if (!p_naru_host_clock_snapshot || !p_naru_target_error) {
            snprintf(backend_error, sizeof(backend_error), "MLIR bridge is missing the host clock toolkit");
            p_naru_target_error = NULL;
            return NULL;
        }
    }
    return p_naru_host_clock_snapshot();
}
