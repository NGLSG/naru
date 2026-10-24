/* goto.c - labels, goto, do-while, break, continue (K&R §3.8, §3.7) */
main()
{
    int i, j, n;

    n = 0;
    i = 0;
    do {
        j = i;
        while (j < 10) {
            if (j == 3)
                goto done;
            if (j % 2 == 0) {
                j++;
                continue;
            }
            n += j;
            j++;
        }
        i++;
    } while (i < 3);
done:
    /* inner: j=1 (1) then j=3 -> goto: n = 1 */
    return n * 10 + j;
}
