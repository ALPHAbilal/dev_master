raw = [
    "  NAME = John Doe  ",
    "# a comment line",
    "CITY=New York",
    "  name = jane  ",
    "",
]


for line in raw:
    line = line.strip()
    if line and not line.startswith('#'):
        key, value= line.split('=',1)
        print(f"{key.strip().lower()}: {value.strip()}")



    