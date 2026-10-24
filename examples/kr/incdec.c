/* incdec.c - ++/-- prefix and postfix, compound pointer stepping */
main()
{
    int a[10];
    int i, sum;
    int *p;

    for (i = 0; i < 10; i++)
        a[i] = i * i;
    sum = 0;
    for (i = 0; i < 10; ++i)
        sum += a[i];
    /* sum of squares 0..9 = 285 */
    p = &a[2];
    sum += *p++;
    sum += *++p;
    /* 285 + 4 + 16 = 305 */
    i = 5;
    sum += i++ + ++i;
    /* 305 + 5 + 7 = 317 */
    return sum % 256;
}
