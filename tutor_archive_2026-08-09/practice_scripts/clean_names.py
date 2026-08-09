names = []
with open('names.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if  line !='':
            names.append(line)


for i , name in enumerate(names, start=1):
    print(f"{i}. {name}")