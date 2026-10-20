K = int(input())
flag = True
for i in range(10000,30001):
    a = i // 100
    b = i % 10000 // 10
    c = i % 1000
    if a % K == 0 and b % K == 0 and c % K == 0:
        flag = False
        print(i)
if flag:
    print('No')