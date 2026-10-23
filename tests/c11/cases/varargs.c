#include <stdarg.h>
static int sum(int count, ...) {
    va_list ap;
    va_start(ap, count);
    int result = 0;
    for (int i = 0; i < count; ++i) result += va_arg(ap, int);
    va_end(ap);
    return result;
}
int main(void) { return sum(3, 10, 12, 20); }
