typedef int (*opfn)();

apply(f, a, b)
int (*f)();
int a;
int b;
{
    return (*f)(a, b);
}

add(x, y)
int x;
int y;
{
    return x + y;
}

mul(x, y)
int x;
int y;
{
    return x * y;
}

main()
{
    opfn op;
    int (*same)();
    int r;

    op = &add;
    r = apply(op, 2, 3);        /* 5 via pointer param */
    op = mul;
    r = r + apply(op, 4, 5);    /* +20 = 25 */
    same = &add;
    r = r + (*same)(1, 1);      /* +2 = 27 */
    return r;
}
