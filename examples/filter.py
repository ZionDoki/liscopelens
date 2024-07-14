import json

def filter_json(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data = data['targets']
    filtered_data = {}
    for key, value in data.items():
        filtered_data[key] = {
            "deps": value.get("deps", None),
            "outputs": value.get("outputs", None),
            "type": value.get("type", None),
            "sources": value.get("sources", None)
        }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, ensure_ascii=False, indent=4)

input_file = 'out.json'
output_file = 'new.json'

filter_json(input_file, output_file)
