
estimate_delay_list = []
time_list = []
for _ in range(100):
    text = input()
    a = text.find("相関:")
    if (a != -1) and (text.find("In") != -1):
        time_list.append(float(text[15:20]))
        print(text)

        estimate_delay_list.append(float(text[a+4:a+9]))

import matplotlib.pyplot as plt

# 時系列でソート
sorted_pairs = sorted(zip(time_list, estimate_delay_list))
time_list_sorted, estimate_delay_list_sorted = zip(*sorted_pairs)

# グラフ描画
plt.figure(figsize=(10, 5))
plt.plot(time_list_sorted, estimate_delay_list_sorted, marker='o', linestyle='-')

plt.xlabel('Time')
plt.ylabel('Estimate Delay')
plt.title('Estimate Delay over Time')
plt.grid(True)
plt.tight_layout()
plt.savefig('correlation_graph.png', dpi=300)
plt.show()