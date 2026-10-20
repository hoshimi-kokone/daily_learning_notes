from math import floor
from collections import defaultdict

n = int(input())
# 使用不存在的key不需要先判断，defaultdict(bool)会自动给不存在的key-value填充False
# 避免使用 at=[False] * 2000010 内存爆出，大量无用内存
at = defaultdict(bool)
for _ in range(n):
    a, t = input().split()
    a = float(a)
    t = int(t)
    for i in range(1, t+1):
        at[floor(i * a)] = not at[floor(i * a)]

for key, value in at.items():
    if value:
        print(key)
        break