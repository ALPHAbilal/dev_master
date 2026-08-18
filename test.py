def count_up():
    yield 1
    yield 2
    yield 3

result = count_up()
for num in result:
    print(num)