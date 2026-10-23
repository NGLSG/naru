#include <stddef.h>
#include <stdint.h>
struct Data { char tag; uint32_t value; uint64_t count; };
_Static_assert(offsetof(struct Data, value) == 4, "field layout");
_Static_assert(sizeof(struct Data) == 16, "aggregate layout");
int main(void) {
    _Alignas(16) struct Data data = {.value = 42};
    return data.value;
}
