import numpy as np
l, m = map(int, input().split())
tree = np.array([1 for _ in range(l + 1)])
for _ in range(m):
    u, v = map(int, input().split())
    tree[u:v+1] = 0

print(sum(tree))