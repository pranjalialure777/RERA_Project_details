import os
import re
import fitz  # PyMuPDF
import easyocr
import pandas as pd

# ------------------------------------------------------------------------------
# CONFIGURATION – EDIT THESE PATHS
# ------------------------------------------------------------------------------
VIEW_APP_FOLDER = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\Files_2025_2023"  # XY *_2 PDFs
VIEW_ORIG_FOLDER = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\View_Original_Application"  # View Application PDFs
INPUT_FILE = r"C:\path\to\your\project_list.xlsx"  # <- update
PROJECT_ID_COL = "Project ID"  # column in INPUT_FILE
OUTPUT_PROJECTS_CSV = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\merged_projects.csv"
OUTPUT_APT_CSV = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\merged_apartments.csv"

# Performance / quality settings
MAX_XY_PAGES = 3          # OCR only first 3 pages of XY pdf (lat/lon usually early)
MAX_DETAIL_OCR_PAGES = 5  # OCR first N pages of scanned View Application (coarse parse)
OCR_DPI = 300             # render dpi for OCR images

# ------------------------------------------------------------------------------
# EASY OCR (init once; slow)
# ------------------------------------------------------------------------------
reader = easyocr.Reader(['en'])

# ------------------------------------------------------------------------------
# BASIC UTILS
# ------------------------------------------------------------------------------
def norm_id(pid): 
    return str(pid).strip().upper()

def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()

def is_text_pdf(pdf_path, sample_pages=2):
    doc = fitz.open(pdf_path)
    for i, pg in enumerate(doc):
        if i >= sample_pages:
            break
        if pg.get_text("text").strip():
            return True
    return False

def extract_text_lines_fitz(pdf_path):
    """Return list of non-empty layout lines."""
    doc = fitz.open(pdf_path)
    lines = []
    for pg in doc:
        raw = pg.get_text("text")
        for ln in raw.splitlines():
            ln = ln.strip()
            if ln:
                lines.append(ln)
    return lines

def easyocr_read_pdf(pdf_path, max_pages=None, dpi=300):
    """OCR a PDF and return concatenated text (space-joined)."""
    text_chunks = []
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc, start=1):
        if max_pages is not None and i > max_pages:
            break
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        page_text = " ".join(reader.readtext(img_bytes, detail=0))
        text_chunks.append(page_text)
        print(f"[EasyOCR] {os.path.basename(pdf_path)} p{i}: {len(page_text)} chars")
    return "\n".join(text_chunks)

# ------------------------------------------------------------------------------
# LAT / LON EXTRACTION (XY pdf text)
# ------------------------------------------------------------------------------
def extract_lat_lon(text):
    lat_pat = r"Lat(?:itude)?[^\d+-]*([+-]?\d{1,3}\.\d+)"
    lon_pat = r"Lon(?:gitude)?[^\d+-]*([+-]?\d{1,3}\.\d+)"
    lat_match = re.search(lat_pat, text, flags=re.IGNORECASE)
    lon_match = re.search(lon_pat, text, flags=re.IGNORECASE)
    return (
        lat_match.group(1) if lat_match else "",
        lon_match.group(1) if lon_match else "",
    )

# ------------------------------------------------------------------------------
# HIGH-LEVEL PROJECT FIELDS (inline block)
# ------------------------------------------------------------------------------
_NOISE_CUTOFFS = (
    "are there any", "promoter(", "co-promoters", "designation", "photo",
    "member information", "view photo", "plot bearing", "state", "pin code",
)
def _cleanup(v: str) -> str:
    v = v.strip(" :-,\t")
    v = v.split(" ?")[0] if " ?" in v else v
    v = v.split("?")[0]
    low = v.lower()
    for tok in _NOISE_CUTOFFS:
        pos = low.find(tok)
        if pos != -1:
            v = v[:pos].strip(" :-,\t")
            break
    return v.strip()

def _find(pattern, text):
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""

def parse_project_details(text: str) -> dict:
    t = norm_ws(text)
    out = {}
    out["Project Name"] = _cleanup(_find(
        r"Project\s*Name[:\s]*(.+?)(?=\s+Project\s*Status\b|\s+Project\s*Type\b|\s+On-Going\s+Project\b|\s+New\s+Project\b|$)", t))
    out["Project Status"] = _cleanup(_find(
        r"Project\s*Status[:\s]*(.+?)(?=\s+Project\s*Type\b|\s+Proposed\s*Date\b|\s+Revised\s*Proposed\b|\s+Plot\s*Bearing\b|\s+Pin\s*Code\b|$)", t))
    out["Project Type"] = _cleanup(_find(
        r"Project\s*Type[:\s]*(.+?)(?=\s+Proposed\s*Date\b|\s+Revised\s*Proposed\b|\s+Plot\s*Bearing\b|\s+Pin\s*Code\b|\s+State\b|\s+of\s*Area|\s+CTS|\s+Number|\s+Address|\s+Completion|$)", t))
    out["Proposed Date of Completion"] = _find(
        r"Proposed\s*Date\s*of\s*Completion[:\s]*(\d{2}/\d{2}/\d{4})", t)
    out["Revised Proposed Date of Completion"] = _find(
        r"Revised\s*Proposed\s*Date\s*of\s*Completion[:\s]*(\d{2}/\d{2}/\d{4})", t)
    out["Developer Name"] = _cleanup(_find(
        r"(?:Name|Promoter|Developer)[:\s]*(.+?)(?=\s+Organization\s*Type\b|\s+Project\s*Name\b|\s+Plot\s*Bearing\b|\s+State\b|\s+Pin\s*Code\b|$)", t))
    out["Project Address"] = _cleanup(_find(
        r"(Plot\s*Bearing.*?)(?=\s+Pin\s*Code\b|\s+Pincode\b|\s+Area\(In|\s+State\b|\s+Total\s*Building|\s*$)", t))
    out["Pincode"] = _find(r"(?:Pin\s*Code|Pincode)[:\s\-]*([0-9]{6})", t)
    return out

# ------------------------------------------------------------------------------
# GRANULAR ADDRESS + COUNTS (line-based)
# ------------------------------------------------------------------------------
STOP_LABELS_RE = (
    r"^(?:Building\s*Name|Block|Street|Locality|Landmark|State|StatelUT|State/UT|"
    r"Division|District|Taluka|Village|Pin\s*Code|Pincode|Number\s*of\s*Buildings|"
    r"Total\s*Building\s*Count|Area\(In|Area\(ln|Aggregate\s*Area|Covered\s*Parking|"
    r"Number\s*of\s*Garages|Development\s*Work|Amenities|Project\s*Status|Project\s*Type)"
)

def _line_capture(lines, lab_re, stop_re=STOP_LABELS_RE):
    lab = re.compile(lab_re, re.IGNORECASE)
    stop = re.compile(stop_re, re.IGNORECASE)
    vals, collecting = [], False
    for ln in lines:
        if not collecting:
            m = lab.search(ln)
            if m:
                vals.append(ln[m.end():].strip(" :-\t"))
                collecting = True
        else:
            if stop.search(ln):
                break
            vals.append(ln.strip())
    if not vals:
        return ""
    return norm_ws(" ".join(vals))

def parse_address_counts(lines) -> dict:
    out = {
        "Address_BuildingName": _line_capture(lines, r"^Building\s*Name|^Building\s*/?\s*Premises\s*Name|^Name\s*of\s*Building"),
        "Address_BlockName":    _line_capture(lines, r"^Block\s*Name|^Wing|^Block\s*/\s*Wing"),
        "Address_StreetName":   _line_capture(lines, r"^Street\b|^Road\b|^Street\s*Name"),
        "Address_Locality":     _line_capture(lines, r"^Locality\b|^Area\b|^Colony\b"),
        "Address_Landmark":     _line_capture(lines, r"^Landmark\b|^Near\b|^Opp(?:osite)?\b|^Behind\b"),
        "Address_StateUT":      _line_capture(lines, r"^State\b|^StatelUT\b|^State/UT\b"),
        "Address_Division":     _line_capture(lines, r"^Division\b"),
        "Address_District":     _line_capture(lines, r"^District\b"),
        "Address_Taluka":       _line_capture(lines, r"^Taluka\b|^Tehsil\b"),
        "Address_Village":      _line_capture(lines, r"^Village\b|^Town\b|^City\b"),
        "Address_Pincode":      _line_capture(lines, r"^Pin\s*Code\b|^Pincode\b|^PINCODE\b"),
        "Total_Building_Count": _line_capture(lines, r"^Total\s*Building\s*Count\b|^Number\s*of\s*Buildings\b"),
        "Aggregate_Area_Sqm":   _line_capture(lines, r"^Area\(In\s*sqmts\)|^Area\(ln\s*sqmts\)|^Aggregate\s*Area\b|^Total\s*Plot\s*Area\b"),
        "Garage_Count":         _line_capture(lines, r"^Number\s*of\s*Garages\b|^Garages\b"),
        "Covered_Parking_Count":_line_capture(lines, r"^Covered\s*Parking\b|^Cover\s*Parking\b|^Covered\s*car\s*parks\b"),
    }

    # normalize numerics
    def _int(v):
        m = re.search(r"\d+", v); return m.group(0) if m else ""
    def _num(v):
        m = re.search(r"\d[\d,\.]*", v); return m.group(0).replace(",", "") if m else ""

    out["Address_Pincode"] = _int(out["Address_Pincode"])
    out["Total_Building_Count"] = _int(out["Total_Building_Count"])
    out["Garage_Count"] = _int(out["Garage_Count"])
    out["Covered_Parking_Count"] = _int(out["Covered_Parking_Count"])
    out["Aggregate_Area_Sqm"] = _num(out["Aggregate_Area_Sqm"])
    return out

# ------------------------------------------------------------------------------
# AMENITIES (Development Works) – Yes/No flags
# ------------------------------------------------------------------------------
AMENITY_PATTERNS = {
    "Amenity_Internal_Roads_Footpaths": r"Internal\s*Roads?.*Footpaths?",
    "Amenity_Water_Supply": r"Water\s*Supply",
    "Amenity_Sewerage": r"Sewerage|Chamber,\s*Lines|STP\b",
    "Amenity_Storm_Water_Drains": r"Storm\s*Water\s*Drains?",
    "Amenity_Landscaping_Tree_Planting": r"Landscaping.*Tree\s*Planting",
    "Amenity_Street_Lighting": r"Street\s*Light",
    "Amenity_Community_Buildings": r"Community\s*Buildings?",
    "Amenity_Treatment_Sewage_Sullage": r"Treatment.*Sewage|Sullage",
    "Amenity_Solid_Waste_Management": r"Solid\s*Waste",
    "Amenity_Water_Conservation_RWH": r"Water\s*Conservation|Rain\s*water|Rainwater",
    "Amenity_Energy_Management": r"Energy\s*Management|Solar|PV",
    "Amenity_Fire_Protection_Safety": r"Fire\s*Protection|Fire\s*Safety",
    "Amenity_Electrical_Meter_Substation": r"Electrical\s*Meter|Sub-?station|Receiving\s*Station",
    "Amenity_Recreational_Open_Space": r"Recreational\s*Open\s*Space",
}
_POSITIVE_TOKENS = ("yes", "y", "provided", "completed", "done", "available", "present", "ready")
_NEGATIVE_TOKENS = ("no", "not", "n/a", "na", "nil", "none")

def parse_amenities_from_text_lines(lines):
    out = {k: "" for k in AMENITY_PATTERNS}
    for k, pat in AMENITY_PATTERNS.items():
        regex = re.compile(pat, re.IGNORECASE)
        for ln in lines:
            if regex.search(ln):
                low = ln.lower()
                val = ""
                if any(tok in low for tok in _POSITIVE_TOKENS):
                    val = "Yes"
                elif any(tok in low for tok in _NEGATIVE_TOKENS):
                    val = "No"
                else:
                    # numeric sometimes indicates provided (e.g., area measure)
                    if re.search(r"\d", ln):
                        val = "Yes"
                out[k] = val
                break
    return out

# ------------------------------------------------------------------------------
# BUILDING STRUCTURE TABLE
# ------------------------------------------------------------------------------
BUILD_STRUCT_HEADER_RE = re.compile(
    r"Proposed\s*Date\s*of\s*Completion.*Number\s*of\s*Basement", re.IGNORECASE)

def parse_building_structure_details(lines) -> dict:
    out = {
        "Bld_Proposed_Date": "",
        "Bld_Num_Basements": "",
        "Bld_Num_Plinth": "",
        "Bld_Num_Podiums": "",
        "Bld_Num_Slab_Super": "",
        "Bld_Num_Stilts": "",
        "Bld_Num_Open_Parking": "",
        "Bld_Num_Closed_Parking": "",
    }
    hdr_idx = None
    for i, ln in enumerate(lines):
        if BUILD_STRUCT_HEADER_RE.search(ln):
            hdr_idx = i
            break
    # If header not found, search entire text
    window_lines = lines[hdr_idx:hdr_idx+5] if hdr_idx is not None else lines
    window = norm_ws(" ".join(window_lines))
    patterns = {
        "Bld_Proposed_Date":      r"Proposed\s*Date\s*of\s*Completion[:\s]*([\d/]+)",
        "Bld_Num_Basements":      r"Number\s*of\s*Basement'?s?[:\s]*([0-9]+)",
        "Bld_Num_Plinth":         r"Number\s*of\s*Plinth[:\s]*([0-9]+)",
        "Bld_Num_Podiums":        r"Number\s*of\s*Podium'?s?[:\s]*([0-9]+)",
        "Bld_Num_Slab_Super":     r"Number\s*of\s*Slab\s*of\s*Super\s*Structure[:\s]*([0-9]+)",
        "Bld_Num_Stilts":         r"Number\s*of\s*Stilts[:\s]*([0-9]+)",
        "Bld_Num_Open_Parking":   r"Number\s*of\s*Open\s*Parking[:\s]*([0-9]+)",
        "Bld_Num_Closed_Parking": r"Number\s*of\s*Closed\s*Parking[:\s]*([0-9]+)",
    }
    for k, pat in patterns.items():
        m = re.search(pat, window, flags=re.IGNORECASE)
        out[k] = m.group(1) if m else ""
    return out

# ------------------------------------------------------------------------------
# APARTMENT MIX TABLE
# ------------------------------------------------------------------------------
APT_HDR_RE = re.compile(r"Apartment\s*Type.*Carpet\s*Area", re.IGNORECASE)
APT_STOP_RE = re.compile(STOP_LABELS_RE, re.IGNORECASE)

def _is_float(s):
    try:
        float(s)
        return True
    except Exception:
        return False

def parse_apartment_mix(lines) -> pd.DataFrame:
    hdr_idx = None
    for i, ln in enumerate(lines):
        if APT_HDR_RE.search(ln):
            hdr_idx = i
            break
    if hdr_idx is None:
        return pd.DataFrame(columns=["SrNo","ApartmentType","CarpetArea_sqm","NumApartment"])

    rows = []
    for ln in lines[hdr_idx+1:]:
        if APT_STOP_RE.search(ln):
            break
        tokens = ln.split()
        if len(tokens) < 4:
            continue
        # pattern: sr apt area num
        if tokens[0].isdigit() and _is_float(tokens[-2]) and tokens[-1].isdigit():
            sr = int(tokens[0])
            area = float(tokens[-2])
            num = int(tokens[-1])
            apt = " ".join(tokens[1:-2])
            rows.append({
                "SrNo": sr,
                "ApartmentType": apt,
                "CarpetArea_sqm": area,
                "NumApartment": num,
            })
    return pd.DataFrame(rows)

# ------------------------------------------------------------------------------
# MASTER PARSER FOR TEXT VIEW APPLICATION PDF
# ------------------------------------------------------------------------------
def parse_view_application_pdf_text(pdf_path):
    """
    Return (fields_dict, apartment_mix_df) for text-based View Application PDF.
    """
    lines = extract_text_lines_fitz(pdf_path)
    text_all = "\n".join(lines)

    fields = {}
    fields.update(parse_project_details(text_all))
    fields.update(parse_address_counts(lines))
    fields.update(parse_amenities_from_text_lines(lines))
    fields.update(parse_building_structure_details(lines))

    apt_df = parse_apartment_mix(lines)
    return fields, apt_df

# ------------------------------------------------------------------------------
# FINDERS FOR FILE PATHS
# ------------------------------------------------------------------------------
def find_xy_pdf(project_id):
    pid_u = norm_id(project_id)
    for f in os.listdir(VIEW_APP_FOLDER):
        if not f.lower().endswith(".pdf"):
            continue
        stem = os.path.splitext(f)[0].upper()
        if stem.startswith(pid_u) and "_2" in stem:
            return os.path.join(VIEW_APP_FOLDER, f)
    return None

def find_detail_pdf(project_id):
    pid_u = norm_id(project_id)
    for f in os.listdir(VIEW_ORIG_FOLDER):
        if not f.lower().endswith(".pdf"):
            continue
        stem = os.path.splitext(f)[0].upper()
        if stem.startswith(pid_u):
            return os.path.join(VIEW_ORIG_FOLDER, f)
    return None

# ------------------------------------------------------------------------------
# LOAD INPUT DF
# ------------------------------------------------------------------------------
def load_project_list(path, id_col):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    # normalize column
    colmap = {c.strip().lower(): c for c in df.columns}
    if id_col.lower() not in colmap:
        raise ValueError(f"Column '{id_col}' not found in {path}.")
    df = df.rename(columns={colmap[id_col.lower()]: "Project ID"})
    df["Project ID"] = df["Project ID"].astype(str)
    return df

# ------------------------------------------------------------------------------
# MAIN PROCESS
# ------------------------------------------------------------------------------
def process_all():
    df = ['P50500004854',
    'P50500004982',
    'P50500006543',
    'P50500008476',
    'P51000012173',
    'P51000015004',
    'P51500000992',
    'P51500007854']


    df_in = pd.DataFrame(df)
    print(df_in)
    ids = pd.unique(df_in[0])


    project_rows = []
    apt_rows = []

    # OCR cache to avoid repeated reads
    ocr_cache = {}

    for pid in ids:
        pid_u = norm_id(pid)
        print(f"\n=== {pid_u} ===")

        # ---------------- XY PDF -> Lat/Lon ----------------
        lat = lon = ""
        xy_path = find_xy_pdf(pid_u)
        if xy_path:
            if xy_path not in ocr_cache:
                ocr_cache[xy_path] = easyocr_read_pdf(xy_path, max_pages=MAX_XY_PAGES, dpi=OCR_DPI)
            xy_text = ocr_cache[xy_path]
            lat, lon = extract_lat_lon(xy_text)
        else:
            print("   [WARN] XY (_2) PDF not found.")

        # ---------------- Detail PDF -> full parse if text ----------------
        detail_fields = {}
        detail_path = find_detail_pdf(pid_u)
        if detail_path:
            if is_text_pdf(detail_path):
                print("   [DETAIL] Text PDF detected.")
                fields, apt_df = parse_view_application_pdf_text(detail_path)
            else:
                print("   [DETAIL] Scanned PDF -> OCR (limited fields).")
                if detail_path not in ocr_cache:
                    ocr_cache[detail_path] = easyocr_read_pdf(detail_path, max_pages=MAX_DETAIL_OCR_PAGES, dpi=OCR_DPI)
                ocr_text = ocr_cache[detail_path]
                fields = parse_project_details(ocr_text)  # coarse
                # blanks for granular fields
                blanks = {
                    "Address_BuildingName": "", "Address_BlockName": "", "Address_StreetName": "",
                    "Address_Locality": "", "Address_Landmark": "", "Address_StateUT": "",
                    "Address_Division": "", "Address_District": "", "Address_Taluka": "",
                    "Address_Village": "", "Address_Pincode": "", "Total_Building_Count": "",
                    "Aggregate_Area_Sqm": "", "Garage_Count": "", "Covered_Parking_Count": "",
                    "Bld_Proposed_Date": "", "Bld_Num_Basements": "", "Bld_Num_Plinth": "",
                    "Bld_Num_Podiums": "", "Bld_Num_Slab_Super": "", "Bld_Num_Stilts": "",
                    "Bld_Num_Open_Parking": "", "Bld_Num_Closed_Parking": "",
                }
                # Amenity blanks
                blanks.update({k: "" for k in AMENITY_PATTERNS})
                fields.update(blanks)
                apt_df = pd.DataFrame(columns=["SrNo","ApartmentType","CarpetArea_sqm","NumApartment"])
        else:
            print("   [WARN] Detail PDF not found.")
            fields = {
                "Project Name": "", "Project Status": "", "Project Type": "",
                "Proposed Date of Completion": "", "Revised Proposed Date of Completion": "",
                "Developer Name": "", "Project Address": "", "Pincode": "",
                "Address_BuildingName": "", "Address_BlockName": "", "Address_StreetName": "",
                "Address_Locality": "", "Address_Landmark": "", "Address_StateUT": "",
                "Address_Division": "", "Address_District": "", "Address_Taluka": "",
                "Address_Village": "", "Address_Pincode": "", "Total_Building_Count": "",
                "Aggregate_Area_Sqm": "", "Garage_Count": "", "Covered_Parking_Count": "",
                "Bld_Proposed_Date": "", "Bld_Num_Basements": "", "Bld_Num_Plinth": "",
                "Bld_Num_Podiums": "", "Bld_Num_Slab_Super": "", "Bld_Num_Stilts": "",
                "Bld_Num_Open_Parking": "", "Bld_Num_Closed_Parking": "",
            }
            fields.update({k: "" for k in AMENITY_PATTERNS})
            apt_df = pd.DataFrame(columns=["SrNo","ApartmentType","CarpetArea_sqm","NumApartment"])

        # assemble row
        row = {"Project ID": pid_u, "Latitude": lat, "Longitude": lon}
        row.update(fields)
        project_rows.append(row)

        # collect apartment mix
        if not apt_df.empty:
            apt_df = apt_df.assign(ProjectID=pid_u)
            apt_rows.append(apt_df)

        # incremental save
        pd.DataFrame(project_rows).to_csv(OUTPUT_PROJECTS_CSV, index=False)
        if apt_rows:
            pd.concat(apt_rows, ignore_index=True).to_csv(OUTPUT_APT_CSV, index=False)

    # final save
    projects_df = pd.DataFrame(project_rows)
    apartments_df = pd.concat(apt_rows, ignore_index=True) if apt_rows else pd.DataFrame(columns=["ProjectID","SrNo","ApartmentType","CarpetArea_sqm","NumApartment"])

    projects_df.to_csv(OUTPUT_PROJECTS_CSV, index=False)
    apartments_df.to_csv(OUTPUT_APT_CSV, index=False)

    print(f"\n[INFO] Extraction complete.\n  Projects -> {OUTPUT_PROJECTS_CSV}\n  Apartments -> {OUTPUT_APT_CSV}")
    return projects_df, apartments_df

# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    process_all()
