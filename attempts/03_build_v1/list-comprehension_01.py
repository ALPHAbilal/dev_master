nums = [3, 8, 1, 15, 6, 20, 4]
doubled = [num * 2 for num in nums]
print(doubled)
bigs = [num for num in nums if num > 5]
print(bigs)
big_doubled = [num * 2 for num in nums if num > 5]
print(big_doubled)