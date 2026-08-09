with open('notes.txt', 'r') as f:
    counter = 1
    for line in f:
        line = line.strip()
        if line !='':
            print(f"{counter}. {line}")
            counter += 1