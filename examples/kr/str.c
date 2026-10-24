/* str.c - string literals are char arrays; pointer walk, char arithmetic */
main()
{
    char *s;
    int n;

    s = "hello";
    n = 0;
    while (s[n] != 0)
        ++n;
    printf("%d\n", n);
    putchar(s[0]);
    putchar(115);
    putchar(10);
    return n;
}
