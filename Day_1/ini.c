#include <stdio.h>

int main (int argc, char **argv) {
    char *gn = argv[1];
    char *fn = argv[2];
    char g = gn[0];
    char f = fn[0];
    printf("initial of '%s %s' is %c%c. \n", gn, fn, g, f);
}