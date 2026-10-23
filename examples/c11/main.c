/* The project selects the C frontend; the core treats this as a source path. */
#include <stdio.h>
#include <stdbool.h>
#include "xxx.c"

#define COUNT 4
#define CAT(a, b) a ## b
#define MESSAGE(x) #x
#define ANSWER(x) twice(x)

#if !defined(__STDC_VERSION__) || __STDC_VERSION__ < 201112L
#error This project selects the C11 dialect
#endif

struct Pair {
    int x;
    int y;
};

_Static_assert(sizeof(int) == 4, "LLP64 int layout");
_Static_assert(sizeof(long) == 4, "LLP64 long layout");
_Static_assert(sizeof(struct Pair) == 8, "record layout");

int main(void) {
    int CAT(va, lues)[COUNT] = { 2, 4, 6, 9 };
    int sum = 0;
    for (int i = 0; i < COUNT; i++) {
        sum += values[i];
    }
    struct Pair pair = { sum, ANSWER(sum) };
    bool correct = pair.y == 42;
    if (correct) {
        printf("%s: %d\n", MESSAGE(Naru C11 rules), pair.y);
    }
    return correct ? pair.y : 1;
}
