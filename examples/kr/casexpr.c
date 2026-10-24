main()
{
    int n;
    n = 2;
    switch (n) {
    case 1 + 1:
        n = 20;
        break;
    case (1 << 3) | 1:
        n = 99;
        break;
    default:
        n = 0;
    }
    /* case 1+1 == 2 hits: n = 20; 'A' + 1 = 66 would not */
    switch (65) {
    case 'A':
        n += 3;
        break;
    }
    return n + (5 > 3) * (7 == 7);
}
