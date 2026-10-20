huixin = input()
team = input()
h, t = 1, 1
for i in huixin:
    h *= ord(i) - 64
for i in team:
    t *= ord(i) - 64
if h % 47 == t % 47:
    print('GO')
else:
    print('STAY')