/* 
 * p00.c
 */

/* 
 * usage:
 * 
 *   ./a.out
 *
 * Intented behavior:
 * It should print the content of this file.
 *
 */

 #include <stdio.h>
 #include <stdlib.h>
 #include <string.h>

int main()
{
  FILE *fp = fopen("p00.c", "rb");
  while (1) {
    int c = fgetc(fp);
    if (c == EOF) break;
    fputc(c, stdout);
  }
  return 0;
}
