passs = input("NEW PASSWORD:")

with open("hash.data", "w") as f:
    f.write(passs)