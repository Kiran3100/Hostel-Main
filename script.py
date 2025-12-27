import os

def is_text_file(file_path):
    """
    Check if a file is likely a text file (not binary).
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
        return b'\x00' not in chunk
    except Exception:
        return False


def combine_all_files(root_folder, output_file):
    """
    Combine all readable (text/code) files from root_folder and its subfolders
    into a single text file, skipping binary and ignored folders.
    """
    # Folders to skip (case-insensitive)
    ignore_folders = {"_pycache_", ".git", ".idea", "node_modules", ".venv", "env", "venv", "build", "dist"}

    total_files = 0
    written_files = 0

    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write(f"### Combined Content from Folder: {root_folder} ###\n\n")

        for current_folder, subfolders, files in os.walk(root_folder):
            # Skip ignored folders
            subfolders[:] = [sf for sf in subfolders if sf.lower() not in ignore_folders]

            outfile.write(f"\n\n# ===== Folder: {current_folder} =====\n")

            for file_name in files:
                total_files += 1
                file_path = os.path.join(current_folder, file_name)

                # Skip the output file itself
                if os.path.abspath(file_path) == os.path.abspath(output_file):
                    continue

                # Skip hidden files
                if file_name.startswith('.'):
                    continue

                # Skip non-text (binary) files
                if not is_text_file(file_path):
                    print(f"⏭ Skipping binary file: {file_path}")
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                        content = infile.read()

                    # Write header + content
                    outfile.write(f"\n# --- File: {file_path} ---\n")
                    outfile.write(content)
                    outfile.write("\n")
                    written_files += 1

                except Exception as e:
                    print(f"⚠ Could not read {file_path}: {e}")

    print("\n✅ Task Completed Successfully!")
    print(f"📂 Total files scanned: {total_files}")
    print(f"✍ Files written to output: {written_files}")
    print(f"📘 Output file created at: {output_file}")


if __name__ == "__main__":
    # 🔧 Change this path to your main root folder

    root_folder = r"D:\Last Github Push\Last\Hostel-Main\app\schemas\notification"

    # 📄 Output file path (saved inside the same root folder)
    output_file = os.path.join(root_folder, "all_folders_files_content.txt")

    combine_all_files(root_folder, output_file)