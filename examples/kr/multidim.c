int grid[2][3] = { 1, 2, 3, 4, 5, 6 };

main()
{
    int m[2][3];
    int i, j;

    for (i = 0; i < 2; i++)
        for (j = 0; j < 3; j++)
            m[i][j] = i * 10 + j;
    /* row-major: grid[1][2] = 6, m[1][2] = 12 */
    printf("%d %d %d\n", grid[1][0], grid[1][2], m[1][2]);
    printf("%d %d\n", sizeof grid, sizeof m);
    return grid[1][2] + m[1][2];
}
