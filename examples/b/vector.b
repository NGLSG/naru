/* §6.2 automatic vectors: v[i] == *(v+i); sum 1..10 = 55 */
main() {
    auto v[10];
    auto i;
    auto sum;
    i = 0;
    while (i < 10) {
        v[i] = i + 1;
        i =+ 1;
    }
    i = 0;
    sum = 0;
    while (i < 10) {
        sum =+ v[i];
        i =+ 1;
    }
    return (sum);
}
