#define MODE 2
main()
{
    int r;
#ifdef MODE
    r = 10;
#else
    r = 99;
#endif
#ifndef MISSING
    r = r + 2;
#endif
#ifdef MISSING
    r = r + 100;
#else
    r = r + 1;
#endif
    return r;
}
