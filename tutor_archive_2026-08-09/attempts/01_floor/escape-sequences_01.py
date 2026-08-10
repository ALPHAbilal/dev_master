s= "a\n"

with open('test.txt', 'w', encoding='utf-8') as f:
    f.write(s)

with open('test_2.txt', 'w', encoding='utf-8') as f:
    f.write(s.strip())

with open('test.txt', 'r', encoding='utf-8') as f:
    for l in f:
        print(f"test 1 :{l}")

with open('test_2.txt', 'r', encoding='utf-8') as f:
    for l in f:
        print(f"test 2 :{l}")

print(s)
print(len(s))