/* macro.c - #define/#undef at token level (K&R 11): object macros,
   function-like macros with argument substitution, rescanning, and the
   position semantics of #undef (uses BEFORE the #undef keep expanding) */
#define COUNT 10
#define SQ(x) ((x) * (x))
#define ADD(a, b) ((a) + (b))

main()
{
    int n;
    n = SQ(4) + COUNT;      /* ((4)*(4)) + 10 = 26 */
    n = n + ADD(2, 3);      /* ((2)+(3)) = 31 */
#undef COUNT
    return n;               /* 31 */
}
