cities = ['Côte d’Ivoire', 'N’Djamena', 'Việt Trì']

with open('cities.txt', 'w', encoding='utf-8') as f:
    for line in cities:
        f.write(line + '\n')

count =0
with open('cities.txt', 'r', encoding='utf-8') as f:
    for line in f:
        print(f" {line}")
        count += 1
        print(count)