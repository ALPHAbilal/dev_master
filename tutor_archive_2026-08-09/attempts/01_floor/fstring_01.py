raw = [
    "  PROMPT_MODEL = 'gpt-4.1-nano'  ",
    "PROMPT_SYSTEM=reply: JSON only, no markdown",
    "   ",
    "# this line is a comment",
    'PROMPT_FILTER="a=b"',
]

config = {}
report= []

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


print("config:", config)
print("report:", report)