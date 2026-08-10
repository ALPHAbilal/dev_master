counts = {}
guests = []

with open('guests.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if line != '' and not line.startswith('#'):
            if line not in guests:
                guests.append(line)
            counts[line] = counts.get(line, 0) + 1

guests.sort()

print("Guests:")
for i, guest in enumerate(guests, start= 1):
    print(f"{i}. {guest}")

print("\nCounts:")
for guest, count in counts.items():
    print(f"{guest}: {count}")