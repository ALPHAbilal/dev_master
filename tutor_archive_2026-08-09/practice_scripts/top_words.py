word_counts= {}
with open('words.txt', 'r') as f:
    temp_list =[]
    for line in f:
        if line !='':
            temp_list = line.split()
            for word in temp_list:
                word_counts[word] = word_counts.get(word, 0) + 1

for word, count in sorted(word_counts.items(), key=lambda items: items[1], reverse= True):
    print(f"{word}: {count}")


