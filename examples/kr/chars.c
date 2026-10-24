/* chars.c - char constants, escapes, old-style char params (K&R: the
   argument is passed as int and truncated into the char parameter) */
f(c)
char c;
{
    return c;
}

main()
{
    char c;
    int r;

    c = 'a';
    r = c + 1;              /* 98 */
    r += '\n';              /* 108 */
    r += '\\';              /* 200 */
    r += '\'';              /* 239 */
    r += '\0';              /* 239 */
    r += '\101';            /* octal 65: 304 */
    putchar(c);
    putchar('\n');
    r += f(1000);           /* 1000 & 0xff = 232, as signed char: -24; 280 */
    r += f('A');            /* 65: 345; exit code = 345 mod 256 = 89 */
    return r;
}
