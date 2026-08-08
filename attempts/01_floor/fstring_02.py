raw = [
    "  PROMPT_MODEL = 'gpt-4.1-nano'  ",
    "PROMPT_SYSTEM=reply: JSON only, no markdown",
    "   ",
    "# this line is a comment",
    'PROMPT_FILTER="a=b"',
]

config = {}
report= []
counter = 0
for line in raw:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    else:
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        config[key] = value
        report.append(f"{key} -> {value}")
        counter += 1

print( config)

for i in range(len(report)):
    print(report[i])
    #
print(f"accepted {counter} skipped {len(raw) - counter}")