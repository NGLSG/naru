/* expr.c - precedence, octal/hex/long constants, compound assignment */
main()
{
    int a;

    a = 2 + 8 * 5;            /* 42 */
    a = a - 077;              /* 42 - 63 = -21 */
    a = a + 0x2A;             /* -21 + 42 = 21 */
    a = a * 2;                /* 42 */
    a += 8;                   /* 50 */
    a -= 20;                  /* 30 */
    a <<= 1;                  /* 60 */
    a |= 3;                   /* 63 */
    a ^= 1;                   /* 62 */
    a %= 10;                  /* 2 */
    a = a << 4 | 10;          /* 42 */
    a = (1 << 5) | (1 << 3) | 2;  /* 42 */
    return a;
}
