word_counts= {}
with open('words.txt', 'r') as f:
    temp_list =[]
    for line in f:
        if line !='':
            temp_list = line.split()
            for word in temp_list:
                word_counts[word] = word_counts.get(word, 0) + 1

for word, count in word_counts.items():
    print(f"{word}: {count}")