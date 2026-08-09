lines = [
    '  PROMPT_MODEL = "gpt-4.1-nano"  ',
    'PROMPT_TEMPERATURE=0.0',
    '# this is a comment',
    '',
    "  PROMPT_SYSTEM = 'be rigorous'  ",
]


config= {}

for line in lines:
    striped_line = line.strip()  # Remove leading and trailing whitespace
    if not striped_line or striped_line.startswith('#'):
        continue  # Skip empty lines and comments
    else:
        if '=' in striped_line:
            key, value = striped_line.split('=')
            config[key.strip()] = value.strip().replace('"', '').replace("'", "")
        else: 
            pass


print(config)