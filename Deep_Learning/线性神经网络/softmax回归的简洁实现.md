> 该内容为《动手学深度学习》的笔记

# softmax回归的简洁实现

我们发现通过深度学习框架的高级 API 能够使实现线性回归变得更加容易。同样，通过深度学习框架的高级 API 也能更方便地实现 softmax 回归模型。本节将继续使用 Fashion-MNIST 数据集，并保持批量大小为 256。

```python
import torch
from torch import nn
from d2l import torch as d2l

batch_size = 256
train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size)
```

## 初始化模型参数

softmax回归地输出层是一个全连接层。因此，为了实现我们的模型，我们只需在 `Sequential` 中添加一个带有 10 个输出的全连接层。同样，在这里 `Sequential` 并不是必要的，但它是实现深度模型的基础。我们仍然以均值 0 和标准差 0.01 随机初始化权重。

```python
# 网络定义
# PyTorch 不会隐式地调整输入的形状。因此，
# 我们在线性层钱定义了展平层(flatten)，来调整网络输入的形状
net = nn.Sequential(
    nn.Flatten(), # 展平层，把多为输入压成一维，只保留 batch 维度不动（batch_size, 784）
    nn.Linear(784, 10) # 全连接层,输入784个特征，输出10个类别
)

# 权重初始化函数
def init_weights(m):
    if type(m) == nn.Linear: # 只对全连接层做初始化，Flatten 层跳过（无参数）
        nn.init.normal_(m.weight, std=0.01) # 权重从均值0，标准差0.01正态分布采样，偏置默认初始化为0

# 对网络里每一层应用初始化函数
net.apply(init_weights) # net.apply(func)：遍历网络所有层，每层实例 m 传给 func
```

## 重新审视softmax的实现

我们计算了模型的输出，然后将此输出送入交叉熵损失。从数学上讲，这是一件完全合理的事情。然而，从计算角度来看，指数可能会造成数值稳定性问题。

回想一下，softmax 函数 $\hat{y_j} = \frac{\exp (o_j)}{\sum_k \exp(o_k)}$ ，其中 $\hat{y_j}$ 是预测的概率分布。$o_j$ 是未规范化的预测 $\mathbf{o}$ 的第 $j$ 个元素。如果 $o_k$ 中的一些数值非常大，那么 $\exp(o_k)$ 可能大于数据类型容许的最大数字，即 **上溢(overflow)** 。这将使分母或分子变为 **inf(无穷大)** ，最后得到的是 0、inf 或 nan (不是数字) 的 $\hat{y_j}$ 。在这些情况下，我们无法得到一个明确定义的交叉熵值。

解决这个问题的一个技巧是：在继续 softmax 计算之前，先从所有 $o_k$ 中减去 $\max(o_k)$ 。这里可以看到每个 $o_k$ 按常数进行的的移动不会改变 softmax 的返回值：

