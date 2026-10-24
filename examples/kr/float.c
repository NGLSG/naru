/* float.c - float/double arithmetic, int conversions, K&R §4 promotion */
main()
{
    double d;
    float f;
    int i;

    d = 2.5;
    d = d * 2.0;            /* 5.0 */
    d = d + 1;              /* int converts: 6.0 */
    f = 1.5;
    d = d + f;              /* float promotes to double: 7.5 */
    i = d;                  /* truncates toward zero: 7 */
    d = 1.0 / 4.0;          /* 0.25 - real division */
    printf("%g %d %g\n", d, i, f * 2.0);
    i = 7 / 2;              /* integer division: 3 */
    d = 7 / 2;              /* still integer division then convert: 3.0 */
    printf("%d %g\n", i, d);
    d = 3.0e2;              /* exponent literal: 300 */
    return i + d;           /* 3 + 300 */
}
