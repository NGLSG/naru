#include <stdbool.h>
typedef unsigned long long Counter;
int twice(int value) { return value * 2; }
int main(void) {
    Counter n = 4;
    int values[4] = {2, 4, 6, 9};
    int sum = 0;
    for (int i = 0; i < n; i++) { sum += values[i]; }
    bool okay = sum == 21;
    if (okay) { return twice(sum); }
    return 1;
}
