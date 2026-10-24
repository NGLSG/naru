/* fahr.c - K&R §1.2 temperature table (integer form) */
main()
{
    int fahr;

    for (fahr = 0; fahr <= 300; fahr = fahr + 20)
        printf("%d %6d\n", fahr, 5 * (fahr - 32) / 9);
    return 0;
}
