typedef int (*opfn)();

int add2(a, b)
int a;
int b;
{
    return a + b;
}

int mul2(a, b)
int a;
int b;
{
    return a * b;
}

main()
{
    opfn ops[2];
    ops[0] = &add2;
    ops[1] = &mul2;
    /* dispatch through the table */
    return (*ops[0])(3, 4) + (*ops[1])(2, 3);   /* 7 + 6 = 13 */
}
