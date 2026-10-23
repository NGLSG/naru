#define kind(value) _Generic((value), int: 42, double: 1, default: 2)
int main(void) { return kind(7); }
