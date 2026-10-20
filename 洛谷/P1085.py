import numpy as np
jj = np.zeros((7,), int)
flag = True
for i in range(7):
    a, b = map(int, input().split())
    if a + b > 8:
        flag = False
        jj[i] = a + b - 8
if flag:
    print(0)
else:
    print(np.argmax(jj) + 1)