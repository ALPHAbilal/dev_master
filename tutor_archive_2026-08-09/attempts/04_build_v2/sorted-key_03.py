word_counts= {}
with open('words.txt', 'r') as f:
    temp_list =[]
    for line in f:
        if line !='':
            temp_list = line.split()
            for word in temp_list:
                word_counts[word] = word_counts.get(word, 0) + 1

sorted_counts = sorted(word_counts.items(), key=lambda items: items[1], reverse= True)
temp_count = []
for name, count in sorted_counts:
    if count == 2:
        temp_count.append(name)

temp_count.sort()
for name, count in sorted_counts:
    if name == temp_count[1]:
        print(f"{name}: {count}") 



