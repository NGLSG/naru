/* longs.c - long/unsigned arithmetic, sizeof, L suffix, shifts on long */
main()
{
    long big;
    unsigned u;
    int small;

    big = 2147483647L;          /* INT_MAX */
    big = big + 1L;             /* 2147483648: overflows int, fine on long */
    u = 0;
    u = u - 1;                  /* wraps to 4294967295 */
    small = sizeof(big);        /* 8 */
    printf("%lld %u %d\n", big, u, small);
    printf("%d %d\n", sizeof(int), sizeof(char *));
    big = 1L << 40;
    return small + (big > 0);
}
