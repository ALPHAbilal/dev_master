records = [
    {'job_id': 3, 'prompt': '  write a bio  '},
    {'job_id': 7, 'prompt': '   '},
    {'job_id': 9, 'prompt': "  '2 lines'  "},
]

requests = []
count= 0
for line in records:
    if line['prompt'].strip():
        requests.append({'custom_id': line['job_id'], 'body': line['prompt'].strip()})
    else:
        count +=1


print(requests)
print(count)