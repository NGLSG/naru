/* §3.0 rvalue/lvalue duality: *(&x) == x; word addressing: *(v+2) */
main() {
    auto x;
    auto v[3];
    x = 42;
    if (*(&x) != 42) return (1);
    v[0] = 41;
    v[1] = 42;
    v[2] = 43;
    if (v[1] != *(v + 1)) return (2);
    return (*(v + 2));
}
