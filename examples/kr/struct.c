struct point { int x; int y; };

main()
{
    struct point p;
    struct point *q;
    struct point arr[3];
    int i;

    p.x = 3;
    p.y = 4;
    q = &p;
    q->y = 10;
    for (i = 0; i < 3; i++) {
        arr[i].x = i;
        arr[i].y = i * i;
    }
    printf("%d %d %d\n", p.x, p.y, q->x + q->y);
    printf("%d %d %d\n", arr[0].y, arr[1].y, arr[2].x + arr[2].y);
    return p.x + p.y + arr[2].y;
}
