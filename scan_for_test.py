import os

def search_for_test(directory):
    pattern = "test"
    file_glob = ".py"
    matches = []

    for root, _, files in os.walk(directory):
        # Skip common non-project directories
        if any(p in root.split(os.sep) for p in ['.git', '__pycache__', 'node_modules', '.venv', 'venv']):
            continue
        for file in files:
            if file.endswith(file_glob):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if pattern in content:
                            matches.append((file_path, content.count(pattern)))
                except Exception:
                    pass
    
    return matches

def main():
    directory = "."
    results = search_for_test(directory)
    
    for file_path, count in results:
        print(f"Found 'test' {count} times in: {file_path}")

if __name__ == "__main__":
    main()
