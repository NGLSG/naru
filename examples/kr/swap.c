/* swap.c - K&R §5.2: pointers as arguments, & and * */
main()
{
    int x, y;

    x = 1;
    y = 2;
    swap(&x, &y);
    return x * 10 + y;
}

swap(px, py)
int *px;
int *py;
{
    int temp;

    temp = *px;
    *px = *py;
    *py = temp;
}
