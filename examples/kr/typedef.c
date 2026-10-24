struct point { int x; int y; };
typedef int length;
typedef struct point Point;
typedef unsigned long ulong;

area(p)
Point *p;
{
    return p->x * p->y;
}

main()
{
    length a;
    Point pt;
    ulong u;
    length *lp;

    a = 6;
    pt.x = 7;
    pt.y = 8;
    u = 0;
    u = u - 1;
    lp = &a;
    *lp = *lp + 1;
    /* a=7, area=56, u wraps to 4294967295 (sizeof 4) */
    printf("%d %d %u %d\n", a, area(&pt), u, (int)sizeof(ulong));
    return a + area(&pt);
}
