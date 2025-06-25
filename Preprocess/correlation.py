
estimate_delay_list = []
for _ in range(100):
    text = input()
    a = text.find("相関:")
    if a != -1:
        estimate_delay_list.append(float(text[a+4:a+9]))

print(f'平均: {sum(estimate_delay_list) / len(estimate_delay_list)}')

import matplotlib.pyplot as plt
import numpy as np

x = np.array(estimate_delay_list)
plt.figure(figsize=(8, 6))  # 図のサイズを設定（オプション）
plt.grid()  # 横線ラインを入れる
plt.ylabel("correlation")
plt.ylim(0, 1)  # 縦軸の範囲を0~1に設定
plt.boxplot(x)

# ファイルとして保存
plt.savefig('correlation_boxplot.png', dpi=300, bbox_inches='tight')

plt.show()