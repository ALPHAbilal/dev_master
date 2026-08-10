lines = ["line 1", "line 2", "line 3"]

with open('lines.txt', 'w') as f:
    for line in lines:
        f.write(line+'\n')

with open('lines.txt', 'r') as f:
    for line in f:
        print(line.strip())