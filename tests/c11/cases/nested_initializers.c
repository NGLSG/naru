// Recursive aggregate initializer fixture.  It intentionally uses no
// designated fields so it can isolate the compositional brace rules from the
// separate designated-initializer layer.
struct Pair { int left; int right; };
static struct Pair table[2] = { { 20, 1 }, { 21, 0 } };
static int matrix[2][2] = { { 0, 20 }, { 22, 0 } };

int main(void) {
    struct Pair local[2] = { { 1, 2 }, { 3, 36 } };
    return table[1].left + matrix[0][1] + local[0].left;
}
