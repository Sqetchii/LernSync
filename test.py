from pinnwand import Pinnwand

with open("pinnwand.html", "rb") as f:
    raw = f.read()

p = Pinnwand()
neu = p.collect_new_files(raw)

for f in neu:
    print(f.name, f.path, f.upload_date)
