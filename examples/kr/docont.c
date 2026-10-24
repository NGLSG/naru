/* docont.c - do-while with continue: continue jumps to the CONDITION
   (K&R 3.7), so the test still runs */
main()
{
    int i, n;

    i = 0;
    n = 0;
    do {
        i++;
        if (i % 2 == 0)
            continue;       /* skips the accumulation, not the test */
        n += i;
    } while (i < 5);
    /* odd i: 1+3+5 = 9; loop exits when i=5 test fails */
    n = n * 10 + i;         /* 95 */
    /* continue on the LAST iteration must still re-test (exit!) */
    i = 0;
    do {
        i++;
        if (i < 3)
            continue;
    } while (i < 3);
    n += i;                 /* i reaches 3: 98 */
    return n;
}
