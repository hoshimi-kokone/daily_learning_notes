data = list(map(int, input().split()))
n = data[0]
lst = data[1:]
jolly = [0] * n
diff = [abs(lst[i] - lst[i + 1]) for i in range(len(lst) - 1)]
for i in diff:
    if 1 <= i <= n - 1:
        jolly[i] = 1
flag = False
for i in jolly[1:]:
    if i == 0:
        flag = True
        break
if flag:
    print('Not jolly')
else:
    print('Jolly')