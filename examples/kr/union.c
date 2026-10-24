struct point { int x; int y; };
union mix { int i; char c; };

bump(p)
struct point *p;
{
    p->x = p->x + 1;
    return p->x;
}

main()
{
    struct point p;
    union mix m;
    int r;

    p.x = 40;
    p.y = 2;
    r = bump(&p);           /* 41 */
    r = r + p.y;            /* 43 */
    m.i = 65;
    putchar(m.c);           /* A: union members share storage */
    return r + (m.c == 65);
}
