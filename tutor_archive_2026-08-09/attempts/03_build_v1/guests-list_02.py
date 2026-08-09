guests= []

with open ('guests.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            if line not in guests:
                guests.append(line)
                guests.sort()

for i , guest in enumerate(guests, start=1):
    print(f"{i}. {guest}")

print(f"Total: {len(guests)} guests")