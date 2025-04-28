/* 
* p05.c
*/

/* 
* usage:
*   ./a.out
* 
* Intended behavior
*   It reads the contents of this file and print it.
*/

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main()
{
  FILE * fp = fopen("p05.c", "rb");
  if (fp == NULL) {
    perror("File open failed");
    return 1;
  }

  char buf[100];
  while (1) {
    int n = fread(buf, 1, 100, fp);
    if (n == 0) {
      if (feof(fp)) {
        break;  // EOFに到達した場合はループを終了
      } else {
        perror("Error reading file");
        fclose(fp);
        return 1;  // 読み取りエラーの場合はエラーメッセージを出して終了
      }
    }
    fwrite(buf, 1, n, stdout);
  }

  fclose(fp);  // ファイルを閉じる
  return 0;
}