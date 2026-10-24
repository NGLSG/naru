/* switch.c - K&R §3.6: case labels, fallthrough, break, default */
classify(c)
int c;
{
    switch (c) {
    case ' ':
    case '\t':
    case '\n':
        return 0;
    case '0':
    case '1':
    case '2':
        return 1;
    default:
        return 2;
    }
}

main()
{
    int n, total;

    n = 2;
    switch (n) {
    case 1:
        total = 10;
        break;
    case 2:
        total = 20;
        /* fallthrough: no break */
    case 3:
        total += 3;
        break;
    default:
        total = 99;
    }
    /* total = 23 */
    total = total + classify(' ');      /* 23 */
    total = total + classify('\t');     /* 23 */
    total = total + classify('5');      /* 25 */
    total = total + classify('1');      /* 26 */
    total = total + classify('x');      /* 28 */
    total = total + classify('2');      /* 29 */
    return total;
}
