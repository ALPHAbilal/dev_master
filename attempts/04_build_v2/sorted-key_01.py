pairs = [('sara', 30), ('omar', 19), ('lina', 25)]

for name, age in sorted(pairs, key=lambda pair: pair[1], reverse=True):
    print(f"{name} is {age}")
