import json
def read_txt_file(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            content_json = json.loads(content)
        return content_json
    except FileNotFoundError:
        return "File not found."
    except Exception as e:
        return f"An error occurred: {e}"
    
def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            content_json = json.loads(content)
        return content_json
    except FileNotFoundError:
        return "File not found."
    except Exception as e:
        return f"An error occurred: {e}"