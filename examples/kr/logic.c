/* logic.c - && || short-circuit evaluation guards a division;
   ?: and comparisons of mixed widths */
main()
{
    int a, b, r;

    a = 10;
    b = 0;
    r = 0;
    if (b != 0 && a / b > 2)
        r = 1;
    if (b == 0 || a / b > 2)
        r += 2;             /* taken: 2 */
    r += b ? 100 : 40;      /* 42 */
    r += (a > 5) + (a < 5); /* 43 */
    a = 300;
    b = a > 255 ? 255 : a;  /* b = 255 */
    r += b - 250;           /* 48 */
    return r;
}
