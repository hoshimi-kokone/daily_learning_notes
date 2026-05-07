# 1、PyTorch安装
# 1.1、cuda安装
1. 打开任务管理器，点击性能，查看GPU型号，确认拥有nvidia显卡。

![](../assets/2026-05-08-00-46-25.png)

2. 确认拥有nvidia显卡后，打开cmd，输入nvidia-smi,查看支持cuda的最高版本。

![](../assets/2026-05-08-00-46-47.png)

![](../assets/2026-05-08-00-46-52.png)

3. 打开cuda官网（https://developer.nvidia.com/cuda-toolkit-archive），选择对应版本，开始下载

![](../assets/2026-05-08-00-47-07.png)

![](../assets/2026-05-08-00-47-12.png)

![](../assets/2026-05-08-00-47-17.png)

![](../assets/2026-05-08-00-47-27.png)

![](../assets/2026-05-08-00-47-32.png)

![](../assets/2026-05-08-00-47-37.png)

![](../assets/2026-05-08-00-47-43.png)

![](../assets/2026-05-08-00-47-47.png)

4. 下载cuda完成后，打开cmd，输入nvcc --version查看cuda

![](../assets/2026-05-08-00-47-57.png)

## 1.2、minicoda安装
1. 打开[清华园镜像网站]（https://mirrors.tuna.tsinghua.edu.cn/），搜索Anaconda并点击anaconda

![](../assets/2026-05-08-00-48-13.png)

2. 点击Miniconda

![](../assets/2026-05-08-00-48-23.png)

3. 选择你想要下载的版本，我一般下载

![](../assets/2026-05-08-00-48-32.png)

4. 安装miniconda

![](../assets/2026-05-08-00-48-40.png)

![](../assets/2026-05-08-00-48-45.png)

![](../assets/2026-05-08-00-48-50.png)

选择下载的地方，然后继续

![](../assets/2026-05-08-00-49-04.png)

![](../assets/2026-05-08-00-49-10.png)

![](../assets/2026-05-08-00-50-09.png)

![](../assets/2026-05-08-00-50-25.png)

5. miniconda的环境配置

右键“我的电脑”，选择“属性”

![](../assets/2026-05-08-00-50-41.png)

点击“高级系统设置”

![](../assets/2026-05-08-00-50-52.png)

点击“环境变量”

![](../assets/2026-05-08-00-51-01.png)

在“系统变量”中找到“Path”,双击打开

![](../assets/2026-05-08-00-51-11.png)

以我安装的位置“D:\codes\tool\miniconda”为例，添加：

- D:\codes\tool\miniconda\
- D:\codes\tool\Miniconda3\condabin\

![](../assets/2026-05-08-00-51-33.png)

在cmd中输入conda init，初始化

![](../assets/2026-05-08-00-51-42.png)

在cmd中执行conda info，返回信息后安装成功。

![](../assets/2026-05-08-00-51-50.png)

执行“conda config --set show_channel_urls yes”创建".condarc"文件

![](../assets/2026-05-08-00-51-59.png)

![](../assets/2026-05-08-00-52-05.png)

使用记事本打开".condarc"文件，将以下内容复制到该文件，并保存。

```python
channels:
  - defaults
show_channel_urls: true
default_channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
custom_channels:
  conda-forge: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  pytorch: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
```

![](../assets/2026-05-08-00-52-32.png)

然后执行"conda clean -i"，清除之前的安装渠道

![](../assets/2026-05-08-00-52-41.png)

配置成功。

6. conda 的常用指令
- conda env list：查看已经创建的虚拟环境

![](../assets/2026-05-08-00-52-59.png)

- conda list：查看该环境中已经安装的第三方库

![](../assets/2026-05-08-00-53-09.png)

- conda create -n 环境名 python=版本 -y：创建虚拟环境，-y表示确定，也可以不加，之后单独确认

![](../assets/2026-05-08-00-53-24.png)

![](../assets/2026-05-08-00-53-32.png)

- conda activate 环境名：激活虚拟环境，默认情况下使用的时base环境，非常不建议使用base环境，base环境作为创建环境的模板，非常不建议修改。

![](../assets/2026-05-08-00-53-42.png)

- conda install 第三方库=版本 -i 源地址：安装第三方库，可以不指定版本名，源地址。
- pip install 第三方库=版本 -i 源地址：同样是安装第三方库，和conda install用法相同，但是pip install只安装python包，建议优先使用conda install，如果conda install安装不了在使用pip install

![](../assets/2026-05-08-00-53-51.png)

- conda uninstall 第三方库：删除已经安装的第三方库。
- pip uninstall：同上

![](../assets/2026-05-08-00-54-01.png)

- conda deactivate：退出虚拟环境

![](../assets/2026-05-08-00-54-11.png)

- conda remove -n 环境名 --all：删除虚拟环境

![](../assets/2026-05-08-00-54-26.png)

## 1.3、PyTorch安装
1. 打开Pytorch官网（https://pytorch.org/），选择对应版本

![](../assets/2026-05-08-00-54-42.png)

2. 在虚拟环境中安装pytorch
打开cmd，激活虚拟环境

```python
conda activate + 虚拟环境名
```

复制Run this Command,在cmd执行

![](../assets/2026-05-08-00-55-07.png)

安装完成。
# 2、Tensor
Tensor（张量）是Pytorch中使用的数据类型，是一个高维度的矩阵。
## 2.1、Tensor常用的数据类型

<table cellpadding="0" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 16px; font-family: system-ui, sans-serif; text-align: center;">
  <thead>
    <tr>
      <th style="padding: 16px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc; font-weight: 600;">Data type</th>
      <th style="padding: 16px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc; font-weight: 600;">dtype</th>
      <th style="padding: 16px; border-bottom: 1px solid #ccc; font-weight: 600;">tensor</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding: 12px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc;">32-bit floating point</td>
      <td style="padding: 12px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc;">torch.float</td>
      <td style="padding: 12px; border-bottom: 1px solid #ccc;">torch.FloatTensor</td>
    </tr>
    <tr>
      <td style="padding: 12px; border-right: 1px solid #ccc;">64-bit integer(signed)</td>
      <td style="padding: 12px; border-right: 1px solid #ccc;">torch.long</td>
      <td style="padding: 12px;">torch.LongTensor</td>
    </tr>
  </tbody>
</table>

## 2.2 Tensor的形状

![](../assets/2026-05-08-00-57-03.png)

<div style="background: #fff3e6; border-radius: 8px; padding: 1em; border: 1px solid #ffd7b3;">
  <p style="margin: 0; font-size: 16px;">
    <strong>PS：</strong><br>
    从左到右维度分别是第0维，第1维，第2维，...
  </p>
</div>

## 2.3、创建Tensor
1. 从`\text{list}`或`\text{Numpy array}`转换成`Tensor`

```python
//将list[[1,-1],[-1,1]转换成张量
x = torch.tensor([[1,-1],[-1,1]])
//将np数组[[1,-1],[-1,1]]转换成张量
x = torch.from_numpy(np.array([[1,-1],[-1,1]]))
```

2. 生成全0的Tensor

```python
//生成2行2列的全0张量
x = torch.zeros([2,2])
```

3. 生成全1的Tensor

```python
//生成1层2行3列的全1张量
x = torch.ones([1,2,3])
```

## 2.4、常见的Tensor计算
- 加法:

```python
z = x + y
```

- 减法

```python
z = x - y
```

- 乘方

```python
y = x.pow(2)
```

- 求和

```python
y = x.sum()
```

- 均值

```python
y = x.mean()
```

- 矩阵维度互换

```python
x = x.transpose(0,1)#将x第0维和第1维互换
```

- 矩阵维度移除

```python
x = torch.zeros([1,2,3])
x = x.squeeze(0)#将x的第0维移除,变成[2,3]
```

- 矩阵维度增加

```python
x = torch.zeros([2,3])
x = x.unsqueeze(1)#在x的第1维的位置增加一个维度，变成[2,1,3]
```

- 矩阵拼接

```python
x = torch.zeros([2,1,3])
y = torch.zeros([2,1,3])
z = torch.zeros([2,1,3])
w = torch.cat([x,y,z],dim=1)#将x,y,z三个矩阵沿着第1维拼接，变成[2,3,3]
```

## 2.5、PyTorch和NumPy的比较

<table cellpadding="0" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 16px; font-family: system-ui, sans-serif; text-align: center;">
  <thead>
    <tr>
      <th style="padding: 16px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc; font-weight: 600;">Pytorch</th>
      <th style="padding: 16px; border-bottom: 1px solid #ccc; font-weight: 600;">Numpy</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding: 12px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc;">x.shape</td>
      <td style="padding: 12px; border-bottom: 1px solid #ccc;">x.shape</td>
    </tr>
    <tr>
      <td style="padding: 12px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc;">x.dtype</td>
      <td style="padding: 12px; border-bottom: 1px solid #ccc;">x.dtype</td>
    </tr>
    <tr>
      <td style="padding: 12px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc;">x.reshape / x.view</td>
      <td style="padding: 12px; border-bottom: 1px solid #ccc;">x.reshape</td>
    </tr>
    <tr>
      <td style="padding: 12px; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc;">x.squeeze()</td>
      <td style="padding: 12px; border-bottom: 1px solid #ccc;">x.squeeze()</td>
    </tr>
    <tr>
      <td style="padding: 12px; border-right: 1px solid #ccc;">x.unsqueeze(1)</td>
      <td style="padding: 12px;">np.expand_dims(x,1)</td>
    </tr>
  </tbody>
</table>

## 2.6、Tensor选择运算硬件
- CPU

```python
x = x.to('cpu')
```

- GPU

```python
x = x.to('cuda')
```

## 2.7、Tensor梯度计算

```python
x = torch.tensor([[1.,0.],[-1.,1.]], requires_grad=True)#requires_grad=True需要计算梯度
z = x.pow(2).sum()
z.backward()#反向传播计算梯度
print(x.grad)
```

![](../assets/2026-05-08-01-03-44.png)

# 3、PyTorch导入Dataset

```python
from torch.utils.data import DataLoader, Dataset

class MyDataset():
    def __init__(self,file):
        self.data = ...
    def __getitem__(self,index):
        return self.data[index]
    def __len__(self):
        return len(self.data)

dataset = MyDataset(file)
dataloader = DataLoader(dataset, batch_size=5,shuffle=True)#shuffle=True：随机打乱,训练True，测试False
```

# 4、使用PyTorch定义神经网络

```python
layer = torch.nn.Linear(32,64)#定义一个输入为32维，输出为64维的线性神经网络
print(layer.weight.shape)#torch.Size([64,32])，layer的weight
print(layer.bias.shape)#torch.Size([64,32])，layer的bias
```

# 5、非线性激活函数
- Sigmoid Activation

```python
nn.Sigmoid()
```

- ReLU Activation

```python
nn.ReLU()
```

# 6、建立神经网络

```python
import torch.nn as nn

class MyModel(nn.Module):#所有 PyTorch 模型都必须继承nn.Module这个基类
    def __init__(self):
        super().__init__()#调用父类的初始化方法
        #nn.Sequential() 是 PyTorch 里用来按顺序堆叠网络层的容器，是构建简单前馈模型最常用的工具之一。
        self.net = nn.Sequential(
            nn.Linear(10,32),#第一层是输入10，输出32的Linear函数
            nn.Sigmoid(),#第二层是Sigmoid函数
            nn.Linear(32,1)#第三层是输入32，输出1的Linear函数
        )
    def forward(self, x):#前向传播，输入x，自动按照sequential的顺序计算，输出结果
        return self.net(x)
```

以下代码与上面等价

```python
import torch.nn as nn

class MyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer1 = nn.Linear(10,32)
        self.layer2 = nn.Sigmoid()
        self.layer3 = nn.Linear(32,1)
    def forward(self, x):
        out = self.layer1(x)
        out = self.layer2(out)
        out = self.layer3(out)
        return out
```

# 7、定义Loss Functions
- MSE(Mean Squared Error,均方误差)，用于回归任务

```python
criterion = nn.MSELoss()
loss = criterion(model_output,expected_value)
```

- Cross Entropy(交叉熵)，用于分类任务

```python
criterion = nn.CrossEntropyLoss()
loss = criterion(model_output,expected_value)
```

# 8、选择optimization的演算法
- SGD(Stochastic Gradient Descent,随机梯度下降)

```python
optimizer = torch.optim.SGD(model.parameters(),lr,momentum=0)
#model.parameters()：模型中所有可以训练的参数
#lr：学习率，超参数
#momentum：超参数
```

# 9、训练神经网络
1. 定义网络

```python
dataset = MyDataset(file)#导入数据
tr_set = DataLoader(dataset,16,shuffle=true)#将数据随机打乱，分成16个batch
model = MyModel().to(device)#将模型在device上运算
criterion = nn.MSELoss()#使用MSE作为Loss函数
optimizer = torch.optim.SGD(model.parameters(),0.1)#使用SGD迭代参数theta
```

2. 训练网络

```python
for epoch in range(n_epochs):#将整个数据集训练n_epochs次
    model.train()#把模型调到训练模式
    for x, y in tr_set:
        optimizer.zero_grad()#将参数初始化为0
        x, y = x.to(device), y.to(device)#将x, y转移至device运算
        pred = model(x)#使用model对x进行预测
        loss = criterion(pred,y)#计算预测值和真实值的Loss
        loss.backward()#使用反向传播计算梯度
        optimizer.step()#使用optimizer更新一次参数
```

3. 验证网络

```python
model.eval()#将模型调到测试模式
total_loss = 0#初始化总Loss
for x, y in dv_set:
    x, y = x.to(device), y.to(device)
    with torch.no_grad():#不计算梯度
        pred = model(x)
        loss = criterion(pred,y)
    total_loss += loss.cpu().item() * len(x)#将loss转移至cpu后使用item（）变成普通数字，然后才能进行乘法，计算该batch的总损失
    avg_loss = total_loss / len(dv_set.dataset)#求整个验证集平均误差
```

4. 测试网络

```python
model.eval()
preds = []
for x in tt_set:
    x = x.to(device)
    with torch.no_grad():
        pred = model(x)
        preds.append(pred.cpu())
```

<div style="background: #fff3e6; border-radius: 8px; padding: 1em; border: 1px solid #ffd7b3;">
  <p style="margin: 0; font-size: 16px;">
    <strong>PS：</strong><br>
    <strong>问：为什么要调到测试模式？</strong><br>
    答：不是所有模型的训练和测试所做的事是相同的，如：
  </p>
  <ul style="margin: 0.5em 0 0 1.5em; padding: 0; font-size: 16px;">
    <li><strong>Dropout（随机丢弃层）</strong>
      <ul style="margin: 0.2em 0 0 1.5em; padding: 0;">
        <li>训练模式：随机关闭一些神经元，防止过拟合；</li>
        <li>测试模式：不关闭神经元，全部参与计算。</li>
      </ul>
    </li>
    <li><strong>BatchNorm（批量归一化层）</strong>
      <ul style="margin: 0.2em 0 0 1.5em; padding: 0;">
        <li>训练模式：用当前批次数据的均值、方差归一化，同时累计全局均值和方差；</li>
        <li>测试模式：使用训练好的全局固定均值、方差，不再按当前批次计算。</li>
      </ul>
    </li>
  </ul>
</div>

<div style="background: #fff3e6; border-radius: 8px; padding: 1em; border: 1px solid #ffd7b3;">
  <p style="margin: 0; font-size: 16px;">
    <strong>PS：</strong><br>
    <strong>问：为什么要在验证和测试时不计算梯度？</strong><br>
    答：
  </p>
  <ol style="margin: 0.5em 0 0 1.5em; padding: 0; font-size: 16px;">
    <li>验证时不需要反向传播、更新参数，只做前向传播算损失、看效果，不用更新模型任何参数</li>
    <li>省显存、省内存、运行更快，一旦计算梯度，PyTorch 会保存计算图，把所有中间张量都存起来占显存。</li>
    <li>防止累积梯度、干扰后续训练，如果验证时一直保留梯度，梯度会累加到下一轮训练里，导致训练梯度错乱、收敛变差、模型训歪。</li>
  </ol>
</div>

# 10、保存和读取训练model
1. 保存模型

```python
torch.save(model.state_dict(),path)
```

2. 读取模型

```python
ckpt = torch.load(path)
model.load_state_dict(ckpt)
```