def first_question(s):
    for char in s:
        if char == '?':
            return len(s)


record = {'prompt': 'what is your name?'}

name1 = first_question(record['prompt'])
name2 = first_question('what is your name')

print(name1)
print(name2)


print(name1 is None)
print(name2 is None)

result = record.get('temperature', None)

print(result is None)
print(result == False)