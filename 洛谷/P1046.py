apples = list(map(int, input().split()))
taotao = int(input()) + 30
count = 0
for apple in apples:
    if apple <= taotao:
        count += 1
print(count)