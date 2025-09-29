import os


def is_text_file(file_path):
    try:
        with open(file_path, encoding="utf-8") as f:
            f.read()
        return True
    except (UnicodeDecodeError, OSError):
        return False


def ingest_folder_to_txt(
    input_path, output_file="ingested_data.txt", exclude_dirs=None
):
    if exclude_dirs is None:
        exclude_dirs = [".git", "node_modules", "__pycache__", "chroma_db", "ext", ".env"]

    with open(output_file, "w", encoding="utf-8") as out_f:
        for root, dirs, files in os.walk(input_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                file_path = os.path.join(root, file)

                # Skip binary files or the output file itself
                if not is_text_file(file_path) or os.path.abspath(
                    file_path
                ) == os.path.abspath(output_file):
                    continue

                try:
                    with open(file_path, encoding="utf-8") as in_f:
                        content = in_f.read()

                    relative_path = os.path.relpath(file_path, input_path)
                    out_f.write(f"\n### FILE: {relative_path} ###\n")
                    out_f.write(content + "\n")

                except Exception as e:
                    print(f"Skipping {file_path}: {e}")

    print(f"\n✅ Ingested data written to: {output_file}")


# ---- Run from CLI or script ----
if __name__ == "__main__":
    folder_path = input("Enter the path to the folder: ").strip()
    ingest_folder_to_txt(folder_path)