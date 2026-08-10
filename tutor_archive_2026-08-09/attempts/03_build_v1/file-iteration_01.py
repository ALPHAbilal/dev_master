with open('nums.txt', 'a') as f:
    for i in [10, 20, 30]:
        f.write(i + '\n')


with open('nums.txt', 'r') as f:
    counter= 0
    for l in f:
        counter += int(l)
    print(counter)     