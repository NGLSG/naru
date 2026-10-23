#include "tinyexpr.h"
int main(void) {
    int error = 0;
    double result = te_interp("sqrt(16) + 2 * (3 + 16)", &error);
    if (error || result < 41.999 || result > 42.001) return 1;
    return 42;
}
