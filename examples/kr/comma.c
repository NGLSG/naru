/* comma.c - the comma operator (K&R Appendix A): left to right,
   value of the right operand; classic use in for loops */
main()
{
    int i, j, n;
    int a[5];

    n = 0;
    for (i = 0, j = 5; i < j; i++, j--)
        n++;
    /* n = 3 (three iterations), i = 3, j = 2 */
    n = n * 10 + i;         /* 33 */
    n = n * 10 + j;         /* 332 */
    a[0] = 5;
    a[1] = 6;
    n += (1, 2, 3);         /* 335: value is the last operand */
    n += (i = 7, i + 1);    /* 343: sequence point between them */
    n += a[0] + a[1];       /* 354 */
    return n % 256;         /* 354 mod 256 = 98 */
}
