import numpy as np
import matplotlib.pyplot as plt

def sigmoid(correlation_strength, midpoint=0.2, steepness=10):
    sig = 1 - 1 / (1 + np.exp(-steepness * (correlation_strength - midpoint)))
    return sig

# データの準備
x = np.linspace(0, 1, 1000)
y = sigmoid(x)

# グラフの描画
plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', linewidth=2)
plt.title('Sigmoid Function')
plt.xlabel('Correlation Strength')
plt.ylabel('Sigmoid Output')
plt.grid(True, alpha=0.3)
plt.xlim(0, 1)
plt.ylim(0, 1)
plt.show()