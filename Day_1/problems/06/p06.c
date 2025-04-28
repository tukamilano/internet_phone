/* 
 * p06.c
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

#include <fcntl.h>
#include <stdio.h>

# include <sys/types.h>
# include <sys/uio.h>
# include <unistd.h>

int main()
{
  int fd = open("p06.c", O_RDONLY);
  char buf[100];
  while (1) {
    int n = read(fd, buf, 100);
    if (n == 0) break;
    if (n < 0) {
      perror("read");
      break;
    }
    write(1, buf, n);
  }
  close(fd);
  return 0;
}
