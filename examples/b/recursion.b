/* §7.3 function definitions, call by value, recursion: fact(5) = 120 */
fact(n) {
    if (n <= 1) return (1);
    return (n * fact(n - 1));
}

main() {
    return (fact(5));
}
