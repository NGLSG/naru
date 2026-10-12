/* §4.1.3 octal constants: 0100 is 64; 077 is 63 */
main() {
    auto x;
    x = 077;
    if (x != 63) return (1);
    return (0100);
}
