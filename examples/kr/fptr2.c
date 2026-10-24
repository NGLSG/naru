typedef int (*opfn)();

struct node { int val; opfn emit; };
opfn table_op = &add2;

add2(a, b)
int a;
int b;
{
    return a + b;
}

main()
{
    struct node n;
    n.val = 10;
    n.emit = &add2;
    return (*n.emit)(n.val, 5) + (*table_op)(1, 2);   /* 15 + 3 = 18 */
}
