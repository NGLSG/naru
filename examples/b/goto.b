/* 5.5 goto and 6.3 labels: loop via goto; sum 1..10 = 55 */
main() {
    auto i;
    auto sum;
    i = 0;
    sum = 0;
loop:
    i =+ 1;
    sum =+ i;
    if (i < 10) goto loop;
    return (sum);
}
