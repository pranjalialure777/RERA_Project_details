from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import os
import re
import easyocr
from PIL import Image
import pyautogui
# Load the Excel file with links
df = pd.read_excel(r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\Mumbai_Data\New_list.xlsx") 

print(df)
# Setup Chrome driver options
download_dir = os.path.join(os.getcwd(), r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\Mumbai_Data\View Apllication")
os.makedirs(download_dir, exist_ok=True)

options = webdriver.ChromeOptions()
options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "directory_upgrade": True
})
options.add_argument("--start-maximized")

# Start ChromeDriver (update the path if needed)
driver = webdriver.Chrome(service=Service("C:\Pranjali\Chrome_Driver\chromedriver-win64\chromedriver.exe"), options=options)

reader = easyocr.Reader(['en'])
def captcha_submission(reader, max_retries=15):

    for attempt in range(1, max_retries + 1):
        
        print(f"🔁 Attempt {attempt} of {max_retries}")

        # 1. Capture the CAPTCHA
        captcha_element = driver.find_element(By.ID, "captcahCanvas")
        captcha_element.screenshot("captcha.png")
        time.sleep(1)

        # 2. OCR   
        
        result = reader.readtext("captcha.png", detail=0)
        captcha_text = result[0].strip() if result else ""
        captcha_text = re.sub(r'[^A-Za-z0-9]', '', captcha_text)
        print("🔐 CAPTCHA read:", captcha_text)
        time.sleep(2)

        if not captcha_text:
            print("⚠️ Blank CAPTCHA read, refreshing image...")
            refresh_btn = driver.find_element(By.CLASS_NAME, "cpt-btn")
            refresh_btn.click()
            time.sleep(2)
            continue
        # 3. Enter the CAPTCHA
        captcha_box = driver.find_element(By.CSS_SELECTOR, "input[name='captcha']")
        captcha_box.click()
        #captcha_box.clear()
        captcha_box.send_keys(captcha_text)
        time.sleep(1)

        # 4. Click Submit
        submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Submit')]")
        submit_btn.click()
        print("🚀 Submitted CAPTCHA")
        time.sleep(3)

        # 5. Check for Invalid CAPTCHA modal
        error_elements = driver.find_elements(By.XPATH, "//p[contains(text(), 'Invalid Captcha')]")
        if not error_elements:
            print("✅ CAPTCHA accepted.")
            return True  # Exit the loop

        print("❌ Invalid CAPTCHA detected.")

        # 6. Dismiss modal and refresh
        try:
            ok_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Ok')]")
            ok_button.click()
            time.sleep(1)

            #refresh_btn = driver.find_element(By.CLASS_NAME, "cpt-btn")
            #refresh_btn.click()
            #print("🔄 Refreshed CAPTCHA image")
            #time.sleep(2)
        except Exception as modal_error:
            print("⚠️ Could not handle error modal:", modal_error)

    print("Max CAPTCHA attempts exceeded.")

def start_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "directory_upgrade": True
    })
    options.add_argument("--start-maximized")
    return webdriver.Chrome(
        service=Service("C:\\Pranjali\\Chrome_Driver\\chromedriver-win64\\chromedriver.exe"),
        options=options
    )
def project_details():     
        captcha_submission(reader, max_retries=10)
        # --- PRINT AND SAVE PDF HANDLING ---
        try:
            pyautogui.click(x=900, y=500, button='right')  # Adjust coordinates
            time.sleep(2)
            pyautogui.press('down')
            pyautogui.press('down')
            pyautogui.press('enter')
            print("🖨️ Print dialog triggered")
        
            time.sleep(3)
            pyautogui.press('enter')
            time.sleep(4)
            pyautogui.write(f'{project_id}_2')
            time.sleep(2)
            pyautogui.press('enter')
            print('Data Downloaded')
            time.sleep(1)
        except Exception as e:
            print(f"⚠️ Error when downloading Original Application for {project_id}: {e}") 
  
# Loop through the first few projects for testing

for index, row in df.iterrows():
    download_dir = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA automation\Mumbai_Data\View Apllication"
    project_id = str(row["Project ID"]).strip()
    file_path = os.path.join(download_dir, f"{project_id}_2.pdf")

    if os.path.exists(file_path):
        print(f"{project_id} File alredy Exists in a folder")
    else:
        view_details_link = row.get("View Details Link", "")
        
        if isinstance(view_details_link, str) and "http" in view_details_link:
            print(f"\n➡️ Opening View Details for Project ID: {project_id}")          
        try:     
            driver.get(view_details_link)
            project_details()
        except Exception as e:
            print(f"⚠️ Driver error: {e}")
            try:
                driver.quit()  # Close any broken instance
            except:
                pass  # Already closed

            print("🔁 Restarting driver...")
            time.sleep(3)
            driver = start_driver()
            driver.get(view_details_link) 
            project_details()
            

driver.quit()
print("✅ Done. Please check your downloads folder.")
