import json

names = {}

with open(r'E:\chinese_translation\soufiane_prompts\prompts\responses\exec\pays_ville_exec_output.json', 'r') as f:
    with open(r'E:\chinese_translation\soufiane_prompts\prompts\responses\exec\ yh' ,'w') as out:
        for i, line in enumerate(f):
            record = json.loads(line)
            job = record['job_name']
            country = record['country_name']
            out.write(f"{job} - {country} \n")
            if i==1:
                break