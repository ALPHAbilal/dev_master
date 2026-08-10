count_list = []
count_dict = {}
with open('words.txt', 'r') as f:
    for line in f:
        line = line.strip()
        line_list = line.split()
        for n in line_list:
            if not n in count_list:
                count_list.append(n)
                count_dict[n] = 1 
            else:
                count_dict[n] +=1


count_list.sort()

for word, count in count_dict.items():
    print(f"{word}: {count}")


