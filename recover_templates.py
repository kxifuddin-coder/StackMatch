import os

log_dir = r"C:\Users\kxifu\.gemini\antigravity\brain\77a97d29-9ff5-4160-9127-c54bca86ab60\.system_generated\logs"
output_dir = r"c:\Users\kxifu\teammate-matcher\templates"

def recover_files():
    for log_filename in os.listdir(log_dir):
        if not log_filename.endswith(".txt"): continue
        log_path = os.path.join(log_dir, log_filename)
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        current_file = None
        extracted_lines = []
        in_file_block = False
        
        for line in lines:
            if "File Path: " in line and "`file:///" in line:
                # e.g. File Path: `file:///c:/Users/kxifu/teammate-matcher/templates/index.html`
                path = line.split("`file:///")[1].split("`")[0]
                if "/templates/" in path:
                    current_file = os.path.basename(path)
                else:
                    current_file = None
            elif "The following code has been modified to include a line number" in line:
                if current_file:
                    in_file_block = True
                    extracted_lines = []
            elif "The above content does NOT show the entire file contents" in line or "The above content shows the entire, complete file contents" in line:
                if in_file_block:
                    in_file_block = False
                    # Overwrite file to avoid duplicates, only if it's currently 0 bytes
                    target_path = os.path.join(output_dir, current_file)
                    if os.path.exists(target_path) and os.path.getsize(target_path) == 0:
                        print(f"Recovered {current_file}")
                        with open(target_path, "w", encoding="utf-8") as out_f:
                            for ex_line in extracted_lines:
                                out_f.write(ex_line)
            else:
                if in_file_block and current_file:
                    if ": " in line:
                        parts = line.split(": ", 1)
                        if parts[0].isdigit():
                            extracted_lines.append(parts[1])

if __name__ == "__main__":
    recover_files()
