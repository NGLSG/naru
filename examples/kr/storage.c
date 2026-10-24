/* storage.c - static and extern data definitions (K&R 8.x):
   extern declaration + definition coexist; static keeps the file private */
static int counter = 100;
extern int shared;
int shared = 7;
extern int fwd;
int fwd = 3;

main()
{
    counter += shared;
    counter += fwd;
    return counter;         /* 110 */
}
