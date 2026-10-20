n, k = map(int, input().split())
def chouyan(n, k):
    if n // k > 0:
        return  n - n % k + chouyan(n % k + n // k, k)
    else:
        return n % k

print(chouyan(n, k))