import os
import re
import csv

# --- EDIT THESE PATHS ---
folder1 = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\Files_2025_2023"
folder2 = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\View_Original_Application"
output_csv = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\files_available.csv"


# --- Helpers -----------------------------------------------------------------

project_id_regex = re.compile(r'(P\d+)', re.IGNORECASE)

def extract_project_id_from_name(name: str) -> str | None:
    """
    Try to extract the canonical Project ID (e.g., P49800077507) from any filename.
    Returns uppercase ID or None.
    """
    m = project_id_regex.search(name)
    if not m:
        return None
    return m.group(1).upper()


def normalize_folder1_name(filename: str) -> str | None:
    """
    Folder1 files are like ProjectID_2(.pdf|.something).
    We'll try:
    1. Extract Project ID via regex.
    2. If that fails, strip '_2' before extension and use what's left (uppercased).
    """
    pid = extract_project_id_from_name(filename)
    if pid:
        return pid

    stem, _ = os.path.splitext(filename)
    if stem.endswith('_2'):
        stem = stem[:-2]  # drop the trailing _2
    return stem.upper() if stem else None


def normalize_folder2_name(filename: str) -> str | None:
    """
    Folder2 files are like ProjectID(.pdf|...).
    Extract via regex first; else fallback to stem.
    """
    pid = extract_project_id_from_name(filename)
    if pid:
        return pid

    stem, _ = os.path.splitext(filename)
    return stem.upper() if stem else None


# --- Scan Folders ------------------------------------------------------------

folder2_ids = {}
for f in os.listdir(folder2):
    if f.startswith('~$'):  # ignore temp files
        continue
    pid = normalize_folder2_name(f)
    if pid:
        # keep first occurrence; overwrite if duplicates are OK
        folder2_ids.setdefault(pid, f)

folder1_records = []
missing_records = []

for f in os.listdir(folder1):
    if f.startswith('~$'):
        continue
    pid = normalize_folder1_name(f)
    if not pid:
        folder1_records.append((None, f, False, ""))  # couldn't parse
        continue

    found = pid in folder2_ids
    folder1_records.append((pid, f, found, folder2_ids.get(pid, "")))
    if not found:
        missing_records.append((pid, f))


# --- Report ------------------------------------------------------------------

print("Files in Folder 1 whose Project ID is NOT present in Folder 2:")
if missing_records:
    for pid, fname in missing_records:
        print(f"- {fname}  (Project ID: {pid})")
else:
    print("None! Every Folder 1 Project ID has a match in Folder 2.")


# --- Optional CSV ------------------------------------------------------------
if output_csv:
    header = ["project_id", "folder1_file", "found_in_folder2", "folder2_file_match"]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for rec in folder1_records:
            writer.writerow(rec)
    print(f"\nCSV written: {output_csv}")
