struct wide { char c : 3; long l : 40; unsigned u : 10; };

main()
{
    struct wide w;

    w.c = -2;               /* 3-bit signed container */
    w.l = 549755814881L;      /* 2^39-15: fits 40 bits */    /* 40 bits of a long */
    w.u = 1000;
    printf("%d %lld %u\n", w.c, w.l, w.u);
    w.l = w.l + 1;          /* RMW on a 40-bit field */
    printf("%lld\n", w.l);
    /* w.l = 2^39+994 as a 40-bit signed field = -(2^40 - 2^39 - 994) */
    return (w.c == -2) + (w.l == -549755812894L);
}
