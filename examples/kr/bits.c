struct mix { unsigned u : 3; int s : 4; int pad : 2; unsigned z0 : 0; unsigned d : 2; };

main()
{
    struct mix m;
    int i;

    m.u = 5;
    m.s = -3;
    m.pad = 1;
    m.d = 2;
    printf("%u %d %u\n", m.u, m.s, m.d);       /* 5 -3 2 */
    m.s = 7;
    printf("%d\n", m.s);                        /* 7 */
    m.s = 8;                                    /* 4-bit signed: wraps to -8 */
    printf("%d\n", m.s);
    m.u += 4;                                   /* 5+4=9 wraps to 1 (3 bits) */
    printf("%u\n", m.u);
    i = m.s + m.u;                              /* -8 + 1 = -7 */
    return i + 7;                               /* 0 */
}
