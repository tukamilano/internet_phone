#no_echo_conversation.txt
estimate_delay_list = []
for _ in range(112):
    text = input()
    a = text.find("推定遅延(FFT):")
    if a != -1:
        estimate_delay_list.append(float(text[a+11:a+16]))


print(f'平均: {sum(estimate_delay_list) / len(estimate_delay_list)}')

import matplotlib.pyplot as plt
import numpy as np

x = np.array(estimate_delay_list)
plt.grid() # 横線ラインを入れることができます。
plt.ylabel("delay time[s]")

plt.boxplot(x)
plt.show()