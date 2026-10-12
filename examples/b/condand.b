/* 12.4: & in conditions is logical (both nonzero); bitwise would give 0 */
main() {
    if (1 & 2) return (42);
    return (13);
}
