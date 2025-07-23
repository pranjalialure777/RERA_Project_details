
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pyautogui
import time
import os
import subprocess
import pandas as pd 

# Setup download directory
download_dir = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA_DATA_MH\Thane\Sellenium test"
#os.makedirs(download_dir, exist_ok=True)

#To handle adobe 
def kill_acrobat_if_open():
    try:
        subprocess.call(["taskkill", "/F", "/IM", "Acrobat.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(["taskkill", "/F", "/IM", "AcroRd32.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("❌ Closed Adobe Acrobat if it was opened.")
    except Exception as e:
        print("No Adobe process found or error:", e)
# Chrome options for print/save flow
options = webdriver.ChromeOptions()
options.add_argument("--kiosk-printing")  # Enable silent printing
options.add_argument("--start-maximized")

driver = webdriver.Chrome(
    service=Service("C:/Pranjali/Chrome_Driver/chromedriver-win64/chromedriver.exe"),
    options=options
)

base_url = "https://maharera.maharashtra.gov.in/projects-search-result?project_state=27&division=3&district=42&op=Search&page={}"

for page in range(443,4500):  # Test for first 3 pages
    print(f"🔄 Loading page {page}")
    driver.get(base_url.format(page))
    time.sleep(3)


    soup = BeautifulSoup(driver.page_source, "html.parser")
    projects = soup.find_all("div", class_="row shadow p-3 mb-5 bg-body rounded")
    
    #stoping pdf viewer from lounching 
    options = webdriver.ChromeOptions()
    prefs = {
    "plugins.always_open_pdf_externally": True,  # ✅ Forces download, not open in browser
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "download.default_directory": r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA_DATA_MH\Thane\Sellenium test",  # set your path here
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--start-maximized")
    options.add_experimental_option("prefs", prefs)
    df = pd.read_excel(r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\Mumbai_Data\New_list.xlsx") 
    for i, project in enumerate(projects):
        try:
            download_dir = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\View_Original_Application"
            project_id = project.find("p", class_="p-0").text.strip().replace("# ", "")
            #print(f"Processing project_id :{project_id} ")
            if project_id in df["Project ID"].values:
                print(f"📌 Project ID: {project_id} in Thane list")
                #project_id = str(row["Project ID"]).strip()
                file_path = os.path.join(download_dir, f"{project_id}.pdf")

                if os.path.exists(file_path):
                    print(f"{project_id} File alredy Exists in a folder")
                else:
                    
                
                    options = webdriver.ChromeOptions()
                    

                    

                    # Find and click 'View Original Application'
                    xpath = f"(//a[@title='View Original Application'])[{i + 1}]"
                    view_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    
                    driver.execute_script("arguments[0].scrollIntoView(true);", view_button)
                    driver.execute_script("arguments[0].click();", view_button)
                    

                    time.sleep(5)  # Allow time for iframe content
                    
                    # Right-click to open context menu, select print
                    pyautogui.click(x=900, y=500, button='right')  # Adjust coordinates
                    time.sleep(5)
                    pyautogui.press('down')  # Navigate to 'Print'
                    pyautogui.press('enter')
                    print("🖨️ Print dialog triggered")

                    time.sleep(5) 
                    # Wait for Print dialog
                    save_path ="{}".format(project_id)
                    pyautogui.write(save_path)
                    pyautogui.press("enter")

                    # Press Enter to trigger Save as PDF
                    pyautogui.press('enter')
                    print("💾 Triggered Save")
                    
                    close_btn = driver.find_element(By.CLASS_NAME, "btn-close")
                    close_btn.click()
                    print("❎ Modal closed")
                    kill_acrobat_if_open() # To kill Acrobat
                    driver.switch_to.default_content()
            else :
                print('Projects not found in this page')     

        except Exception as e:
            print(f"⚠️ Error processing project {i+1} ({project_id}): {e}")
            driver.switch_to.default_content()
            continue

driver.quit()
print("🎉 All PDFs saved via Print > Save As PDF flow")
