/* Host filesystem identity and executable path. No process launching APIs. */
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <wchar.h>
const char *naru_exe_path(void) {
    static char utf8[131072];
    wchar_t path[32768];
    DWORD n = GetModuleFileNameW(NULL, path, 32768);
    if (!n || n >= 32768) return "";
    WideCharToMultiByte(CP_UTF8, 0, path, -1, utf8, sizeof(utf8), NULL, NULL);
    return utf8;
}
/* Vyx strings can be unterminated slices. Filesystem interfaces therefore
 * accept explicit byte lengths and never let embedded NULs truncate a path. */
static wchar_t *wide_path(const char *s, int64_t len) {
    if (!s || len <= 0 || len > INT_MAX || memchr(s, 0, (size_t)len)) return NULL;
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s, (int)len, NULL, 0);
    if (!n) return NULL;
    wchar_t *out = (wchar_t *)calloc((size_t)n + 1, sizeof(wchar_t));
    if (!out) return NULL;
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s, (int)len, out, n)) {
        free(out);
        return NULL;
    }
    return out;
}
int32_t naru_same_file(const char *first, int64_t first_len, const char *second, int64_t second_len) {
    wchar_t *a = wide_path(first, first_len);
    wchar_t *b = wide_path(second, second_len);
    if (!a || !b) { free(a); free(b); return 0; }
    DWORD share = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE;
    HANDLE x = CreateFileW(a, FILE_READ_ATTRIBUTES, share, NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    HANDLE y = CreateFileW(b, FILE_READ_ATTRIBUTES, share, NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    free(a); free(b);
    int32_t same = 0;
    if (x != INVALID_HANDLE_VALUE && y != INVALID_HANDLE_VALUE) {
        FILE_ID_INFO xi, yi;
        if (GetFileInformationByHandleEx(x, FileIdInfo, &xi, sizeof(xi))
            && GetFileInformationByHandleEx(y, FileIdInfo, &yi, sizeof(yi))) {
            same = xi.VolumeSerialNumber == yi.VolumeSerialNumber
                && memcmp(&xi.FileId, &yi.FileId, sizeof(xi.FileId)) == 0;
        } else {
            /* Fallback for filesystems without the extended 128-bit ID API. */
            BY_HANDLE_FILE_INFORMATION xa, ya;
            if (GetFileInformationByHandle(x, &xa) && GetFileInformationByHandle(y, &ya))
                same = xa.dwVolumeSerialNumber == ya.dwVolumeSerialNumber
                    && xa.nFileIndexHigh == ya.nFileIndexHigh && xa.nFileIndexLow == ya.nFileIndexLow;
        }
    }
    if (x != INVALID_HANDLE_VALUE) CloseHandle(x);
    if (y != INVALID_HANDLE_VALUE) CloseHandle(y);
    return same;
}
int32_t naru_atomic_text(const char *path, int64_t path_len, const char *text, int64_t text_len) {
    if (text_len < 0 || (text_len && !text)) return 1;
    wchar_t *name = wide_path(path, path_len);
    if (!name) return 1;
    wchar_t parent[32768], temporary[32768];
    if (wcslen(name) >= 32768) { free(name); return 1; }
    wcscpy(parent, name);
    wchar_t *slash = wcsrchr(parent, L'\\'), *forward = wcsrchr(parent, L'/');
    if (!slash || (forward && forward > slash)) slash = forward;
    if (!slash) { free(name); return 1; }
    slash[1] = 0;
    if (!GetTempFileNameW(parent, L"nru", 0, temporary)) { free(name); return 1; }
    HANDLE file = CreateFileW(temporary, GENERIC_WRITE, 0, NULL, TRUNCATE_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    int failed = file == INVALID_HANDLE_VALUE;
    int64_t position = 0;
    while (!failed && position < text_len) {
        DWORD written = 0, count = (DWORD)((text_len - position) > 1048576 ? 1048576 : text_len - position);
        if (!WriteFile(file, text + position, count, &written, NULL) || written != count) failed = 1;
        position += written;
    }
    if (file != INVALID_HANDLE_VALUE) { if (!FlushFileBuffers(file)) failed = 1; CloseHandle(file); }
    if (!failed && !MoveFileExW(temporary, name, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) failed = 1;
    if (failed) DeleteFileW(temporary);
    free(name);
    return failed;
}
#else
#include <unistd.h>
#include <sys/stat.h>
static char *copy_path(const char *path, int64_t len) {
    if (!path || len <= 0 || (uint64_t)len >= SIZE_MAX || memchr(path, 0, (size_t)len)) return NULL;
    char *copy = (char *)malloc((size_t)len + 1);
    if (!copy) return NULL;
    memcpy(copy, path, (size_t)len);
    copy[len] = 0;
    return copy;
}
int32_t naru_same_file(const char *first, int64_t first_len, const char *second, int64_t second_len) {
    char *a = copy_path(first, first_len), *b = copy_path(second, second_len);
    if (!a || !b) { free(a); free(b); return 0; }
    struct stat x, y;
    int32_t same = stat(a, &x) == 0 && stat(b, &y) == 0 && x.st_dev == y.st_dev && x.st_ino == y.st_ino;
    free(a); free(b);
    return same;
}
const char *naru_exe_path(void) {
    static char path[4096];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path)-1);
    if (n < 0) return "";
    path[n] = 0;
    return path;
}
int32_t naru_atomic_text(const char *path, int64_t path_len, const char *text, int64_t text_len) {
    char *name = copy_path(path, path_len);
    if (!name || text_len < 0 || (text_len && !text)) { free(name); return 1; }
    char *temporary = malloc((size_t)path_len + 16);
    if (!temporary) { free(name); return 1; }
    sprintf(temporary, "%s.naru-XXXXXX", name);
    int fd = mkstemp(temporary), failed = fd < 0;
    int64_t offset = 0;
    while (!failed && offset < text_len) { ssize_t n = write(fd, text + offset, text_len - offset); if (n <= 0) failed = 1; else offset += n; }
    if (fd >= 0) { if (fsync(fd)) failed = 1; close(fd); }
    if (!failed && rename(temporary, name)) failed = 1;
    if (failed) unlink(temporary);
    free(name); free(temporary); return failed;
}
#endif
