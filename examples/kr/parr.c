main()
{
    int mat[3];
    int (*row)[3];
    int i;

    for (i = 0; i < 3; i++)
        mat[i] = i * 10;
    row = &mat;
    (*row)[1] = 55;
    printf("%d %d %d\n", mat[0], mat[1], mat[2]);
    return (*row)[0] + (*row)[2];
}
