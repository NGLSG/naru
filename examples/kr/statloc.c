counter()
{
    static int n = 0;
    n = n + 1;
    return n;
}

main()
{
    counter();
    counter();
    return counter();       /* 3: storage persists across calls */
}
