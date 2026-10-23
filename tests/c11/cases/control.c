enum Mode { First, Answer = 42 };
int main(void) {
    int count = 0;
    for (;;) {
        if (++count == 2) break;
        continue;
    }
    switch (count) {
        case 1: return First;
        case 2: goto result;
        default: return 1;
    }
result:
    return Answer;
}
