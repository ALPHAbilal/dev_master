cities = ['Côte d’Ivoire', 'N’Djamena', 'Việt Trì']

with open('cities.txt', 'w', encoding='utf-8') as f:
    for line in cities:
        f.write(line + '\n')


with open('cities.txt', 'r', encoding='utf-8') as f:
    for counter, line in enumerate(f, start=1):
        print(f"{counter} {line}")
        