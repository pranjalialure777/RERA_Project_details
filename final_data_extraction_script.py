import os
import re
import fitz  # PyMuPDF
import easyocr
import pandas as pd
from PIL import Image
import io

# --------------------------
# CONFIGURATION
# --------------------------
VIEW_APP_FOLDER = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\Files_2025_2023"
VIEW_ORIG_FOLDER = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\View_Original_Application"
OUTPUT_CSV = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\merged_output_10.csv"



# Initialize EasyOCR
reader = easyocr.Reader(['en'])
df = ['P50500004854',
'P50500004982',
'P50500006543',
'P50500008476',
'P51000012173',
'P51000015004',
'P51500000992',
'P51500007854']


df = pd.DataFrame(df)
print(df)
# --------------------------
# OCR & FIELD EXTRACTION
# --------------------------
def easyocr_read_pdf(pdf_path, max_pages=None, dpi=300 ):
    text = []
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc, start=1):
        if max_pages is not None and i > max_pages:
            break
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        page_text = " ".join(reader.readtext(img_bytes, detail=0))
        text.append(page_text)
        print(f"[EasyOCR] {os.path.basename(pdf_path)} Page {i} -> {len(page_text)} chars")
    return "\n".join(text)

def extract_lat_lon(text):
    lat_pat = r"Lat(?:itude)?[^\d+-]*([+-]?\d{1,3}\.\d+)"
    lon_pat = r"Lon(?:gitude)?[^\d+-]*([+-]?\d{1,3}\.\d+)"
    lat_match = re.search(lat_pat, text, flags=re.IGNORECASE)
    lon_match = re.search(lon_pat, text, flags=re.IGNORECASE)
    return (lat_match.group(1) if lat_match else "", lon_match.group(1) if lon_match else "")

def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()

def find_field(pattern, text):
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""

import re

# optional: strings that, if they appear in a captured value, we trim at that point
_NOISE_CUTOFFS = (
    "are there any", "promoter(", "co-promoters", "designation", "photo",
    "member information", "view photo", "plot bearing", "state", "pin code",
)

def cleanup_field(v: str) -> str:
    v = v.strip(" :-,\t")
    # stop at ? if question noise present
    v = v.split(" ?")[0] if " ?" in v else v
    # stop at explicit '?' char
    v = v.split("?")[0]
    # stop at known noisy tokens
    low = v.lower()
    for tok in _NOISE_CUTOFFS:
        pos = low.find(tok)
        if pos != -1:
            v = v[:pos].strip(" :-,\t")
            break
    return v.strip()

def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def find_field(pattern: str, text: str) -> str:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""

def parse_project_details(text: str) -> dict:
    """
    Parse key MahaRERA fields from OCR or selectable-text PDFs.
    Works on 'inline' layouts where multiple labels appear on one line.
    """
    t = norm_ws(text)

    project_name = find_field(
        r"Project\s*Name[:\s]*(.+?)(?=\s+Project\s*Status\b|\s+Project\s*Type\b|\s+On-Going\s+Project\b|\s+New\s+Project\b|$)",
        t
    )

    project_status = find_field(
        r"Project\s*Status[:\s]*(.+?)(?=\s+Project\s*Type\b|\s+Proposed\s*Date\b|\s+Revised\s*Proposed\b|\s+Plot\s*Bearing\b|\s+Pin\s*Code\b|$)",
        t
    )

    project_type = find_field(
        r"Project\s*Type[:\s]*(.+?)(?=\s+Proposed\s*Date\b|\s+Revised\s*Proposed\b|\s+Plot\s*Bearing\b|\s+Pin\s*Code\b|\s+State\b|$)",
        t
    )

    proposed = find_field(
        r"Proposed\s*Date\s*of\s*Completion[:\s]*(\d{2}/\d{2}/\d{4})",
        t
    )

    revised = find_field(
        r"Revised\s*Proposed\s*Date\s*of\s*Completion[:\s]*(\d{2}/\d{2}/\d{4})",
        t
    )

    developer = find_field(
        r"(?:Name|Promoter|Developer)[:\s]*(.+?)(?=\s+Organization\s*Type\b|\s+Project\s*Name\b|\s+Plot\s*Bearing\b|\s+State\b|\s+Pin\s*Code\b|$)",
        t
    )

    # capture address chunk starting at "Plot Bearing..." (common start of site info)
    project_address = find_field(
        r"(Plot\s*Bearing.*?)(?=\s+Pin\s*Code\b|\s+Pincode\b|\s+Area\(In|\s+State\b|\s+Total\s*Building|\s*$)",
        t
    )

    # pin code (handles "Pin Code", "Pincode", "PINCODE")
    pincode = find_field(
        r"(?:Pin\s*Code|Pincode)[:\s\-]*([0-9]{6})",
        t
    )

    # clean noisy extra text
    project_name = cleanup_field(project_name)
    project_status = cleanup_field(project_status)
    project_type = cleanup_field(project_type)
    developer = cleanup_field(developer)
    project_address = cleanup_field(project_address)

    return {
        "Project Name": project_name,
        "Project Status": project_status,
        "Project Type": project_type,
        "Proposed Date of Completion": proposed,
        "Revised Proposed Date of Completion": revised,
        "Developer Name": developer,
        "Project Address": project_address,
        "Pincode": pincode,
    }

def process_all_projects():
    all_data = []

    # Collect project IDs from View Application folder
    project_ids = set()
    # for file in os.listdir(VIEW_APP_FOLDER):
    #     if file.lower().endswith(".pdf") and "_2" in file:
    #         project_id = re.sub(r'_2.*$', '', os.path.splitext(file)[0])
    #         project_ids.add(project_id)
    for file in os.listdir(VIEW_APP_FOLDER):
           if file.lower().endswith(".pdf") and "_2" in file:
               
            project_id = re.sub(r'_2.*$', '', os.path.splitext(file)[0])
            if project_id in df[0].values :
                print(f"{project_id} : Project ID present in both formats")
                project_ids.add(project_id)

    print(f"[INFO] Found {len(project_ids)} project IDs.")

    for project_id in sorted(project_ids):
        print(f"\n=== Processing Project: {project_id} ===")

        # XY File
        xy_file = next((f for f in os.listdir(VIEW_APP_FOLDER) if f.startswith(project_id) and "_2" in f), None)
        lat, lon = "", ""
        if xy_file:
            xy_path = os.path.join(VIEW_APP_FOLDER, xy_file)
            xy_text = easyocr_read_pdf(xy_path, max_pages=3)  # First 3 pages for speed
            lat, lon = extract_lat_lon(xy_text)
        else:
            print(f"[WARNING] No XY file for {project_id}")

        # Details File
        detail_file = next((f for f in os.listdir(VIEW_ORIG_FOLDER) if f.startswith(project_id)), None)
        details = {}
        if detail_file:
            detail_path = os.path.join(VIEW_ORIG_FOLDER, detail_file)
            detail_text = easyocr_read_pdf(detail_path, max_pages=3)  # Usually first 3 pages contain all info
            details = parse_project_details(detail_text)
            print(f"[plumber] details found")
        else:
            print(f"[WARNING] No details file for {project_id}")

        # Combine and store
        row = {"Project ID": project_id, "Latitude": lat, "Longitude": lon}
        row.update(details)
        all_data.append(row)

        # Write partial CSV after each project
        pd.DataFrame(all_data).to_csv(OUTPUT_CSV, index=False)

    print(f"[INFO] Data extraction complete. Output saved to: {OUTPUT_CSV}")

if __name__ == "__main__":
    process_all_projects()
