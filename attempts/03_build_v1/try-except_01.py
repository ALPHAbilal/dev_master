def load_guests(file_path):
    guests= []
    try :
        with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if line not in guests:
                            guests.append(line)
                guests.sort()

        return guests
    except FileNotFoundError:
         print(f"File '{file_path}' not found")
         return guests

guests = load_guests('guests.txt')

for i , guest in enumerate(guests, start=1):
    print(f"{i}. {guest}")

print(f"Total: {len(guests)} guests")

gueses_2 = load_guests('nope.txt')
for i , guest in enumerate(gueses_2, start=1):
    print(f"{i}. {guest}")
print(f"Total: {len(gueses_2)} guests")