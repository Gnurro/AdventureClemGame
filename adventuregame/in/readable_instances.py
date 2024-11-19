import json

instances_file_path = "newword_instances.json"

with open(instances_file_path, 'r', encoding='utf-8') as instances_file:
    instances = json.load(instances_file)

print(instances)

with open(instances_file_path, 'w', encoding='utf-8') as instances_file:
    json.dump(instances, instances_file, indent=2)