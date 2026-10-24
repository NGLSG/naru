/* arrinit.c - external array initializers (K&R 8.x), char[] from strings,
   local char arrays initialized by strings */
int powers[6] = { 1, 2, 4, 8, 16, 32 };
int partial[5] = { 10, 20 };
char msg[] = "K&R";
char spaced[8] = "ab";

main()
{
    int i, sum;
    char local[6];

    sum = 0;
    for (i = 0; i < 6; i++)
        sum += powers[i];       /* 63 */
    sum += partial[2];          /* zero-filled: +0 */
    sum += msg[0] + msg[1] + msg[2];    /* K=75 &=38 R=82: +195 → 258 */
    sum += spaced[2];           /* NUL-filled: +0 */
    local[0] = 'o';
    local[1] = 'k';
    local[2] = 0;
    sum += local[0] + local[1]; /* o=111 k=107: +218 → 476 */
    putchar(msg[0]);
    putchar(msg[1]);
    putchar(msg[2]);
    putchar(10);
    return sum % 256;           /* 476 mod 256 = 220 */
}
