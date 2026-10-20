money = 0
mum = 0
flag = True
for i in range(12):
    money += 300
    pay = int(input())
    money -= pay
    if money < 0:
        flag = False
        print(-i - 1)
        break
    if money >= 100 and money // 100 > 0:
        mum += money // 100 * 100
        money -= money // 100 * 100
if flag:
    print(int(money + mum * 1.2))