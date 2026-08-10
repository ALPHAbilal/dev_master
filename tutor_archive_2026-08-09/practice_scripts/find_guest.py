def find_guest(names, target):
    if target in names:
        return names.index(target)
    else:
        return None

ant_search = find_guest(["ant", "cat", "dog"], "ant")
dog_search = find_guest(["ant", "cat", "dog"], "dog")
zebra_search = find_guest(["ant", "cat", "dog"], "zebra")


if ant_search is None:
    print("not found")
else:
    print(f"found at index {ant_search}")

if dog_search is None:
    print("not found")
else:
    print(f"found at index {dog_search}")

if zebra_search is None:
    print("not found")
else:
    print(f"found at index {zebra_search}")