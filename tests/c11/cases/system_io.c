#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(void) {
    char *message = malloc(32);
    if (message == NULL) return 1;
    strcpy(message, "system CRT");
    printf("%s: %d\n", message, 42);
    free(message);
    return 42;
}
