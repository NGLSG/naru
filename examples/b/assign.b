/* §4.12 the assignment operators (prefix order: x =* 10 is x = x*10) */
main() {
    auto x;
    x = 10;
    x =+ 5;    /* 15 */
    x =- 3;    /* 12 */
    x =* 2;    /* 24 */
    x =/ 4;    /* 6 */
    x =% 4;    /* 2 */
    x =<< 3;   /* 16 */
    x =>> 2;   /* 4 */
    x =| 3;    /* 7 */
    x =& 6;    /* 6 */
    x =^ 5;    /* 3 */
    return (x);
}
