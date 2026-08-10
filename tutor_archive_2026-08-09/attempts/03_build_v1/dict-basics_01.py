counter = {}

with open('guests.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            counter[line] = counter.get(line, 0) + 1

for guest, count in counter.items():
    print(f"{guest}: {count}")