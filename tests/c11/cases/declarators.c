typedef int (*Binary)(int, int);
static int add(int a, int b) { return a + b; }
static Binary const operations[1] = {add};
int main(void) {
    Binary selected = operations[0];
    return selected(20, 22);
}
