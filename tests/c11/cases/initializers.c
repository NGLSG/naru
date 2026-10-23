struct Value { int n; int data[3]; };
int main(void) {
    struct Value value = {.data = {[2] = 22, [0] = 20}, .n = 3};
    struct Value *pointer = &(struct Value){.n = 42};
    if (value.data[0] + value.data[2] == pointer->n) return pointer->n;
    return 1;
}
