import requests
from bs4 import BeautifulSoup
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def extract_projects_from_html(html, page_number):
    soup = BeautifulSoup(html, "html.parser")
    projects = soup.find_all("div", class_="row shadow p-3 mb-5 bg-body rounded")
    page_data = []

    for project in projects:
        try:
            project_id = project.find("p", class_="p-0").text.strip().replace("# ", "")
            project_name = project.find("h4", class_="title4").text.strip()
            promoter_name = project.find("p", class_="darkBlue bold").text.strip()
            location = project.find("ul", class_="listingList").find("a").text.strip()
            state = project.find("div", string="State").find_next_sibling("p").text.strip()
            pincode = project.find("div", string="Pincode").find_next_sibling("p").text.strip()
            district = project.find("div", string="District").find_next_sibling("p").text.strip()
            last_modified = project.find("div", string="Last Modified").find_next_sibling("p").text.strip()
            certificate_link = project.find("a", title="View Certificate")
            cert_status = "Available" if certificate_link else "N/A"
            ext_cert = project.find("div", string="Extension Certificate").find_next_sibling("a").text.strip()
            view_link_tag = project.find("a", string="View Details")
            view_link = view_link_tag["href"] if view_link_tag else ""

            page_data.append({
                "Project ID": project_id,
                "Project Name": project_name,
                "Promoter": promoter_name,
                "Location": location,
                "State": state,
                "Pincode": pincode,
                "District": district,
                "Last Modified": last_modified,
                "Certificate": cert_status,
                "Extension Certificate": ext_cert,
                "View Details Link": view_link,
                "Page Number": page_number
            })
        except Exception:
            continue
    return page_data


def scrape_page(page):
    """Function to scrape a single page"""
    url = f"https://maharera.maharashtra.gov.in/projects-search-result?project_state=27&page={page}&op=Search"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return extract_projects_from_html(response.text, page)
        else:
            print(f"Failed to fetch page {page}, status: {response.status_code}")
    except Exception as e:
        print(f"Error on page {page}: {e}")
    return []


def main():
    start_time = time.time()
    print(start_time)
    total_pages = 4246
    all_projects = []

    # Use ThreadPoolExecutor for parallel requests
    with ThreadPoolExecutor(max_workers=2) as executor:  # Try 10, 20, 30 workers (depending on your network)
        futures = {executor.submit(scrape_page, page): page for page in range(1, total_pages + 1)}
        for future in as_completed(futures):
            page = futures[future]
            try:
                page_projects = future.result()
                if page_projects:
                    all_projects.extend(page_projects)
            except Exception as e:
                print(f"Error processing page {page}: {e}")

    df = pd.DataFrame(all_projects)
    excel_path = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA_DATA_MH\All_projects_list_muliprocessing.xlsx"
    df.to_excel(excel_path, index=False)
    print(f"Scraping completed in {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
