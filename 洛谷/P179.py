l, r = map(int, input().split())
count_2 = 0
for i in range(l, r+1):
    s = str(i)
    count_2 += s.count('2')
print(count_2)