/* 8.1-8.2: strings are EOT-terminated; char(s,n) reads the n-th character.
   The walk prints the string one character at a time. */
main() {
    auto s;
    auto i;
    s = "Hi*n";
    i = 0;
    while (char(s, i) != '*e') {
        putchar(char(s, i));
        i =+ 1;
    }
}
