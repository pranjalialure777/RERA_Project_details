from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver
import pandas as pd
import time
import os
import re
import easyocr
import pyautogui
import logging as log

# Load data
excel_path = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA_DATA_MH\Thane\Maharera_Projects_Extracted.xlsx"
df = pd.read_excel(excel_path)
df["Download Status"] = df["Download Status"].astype(str)

# Download directory
download_dir = r"C:\Users\Pranjali.Alure\OneDrive - Reliance Corporate IT Park Limited\Desktop\LB\Arul sir\RERA_DATA_MH\Thane\Sellenium test"
os.makedirs(download_dir, exist_ok=True)

# Configure the log.infoging
log_file = os.path.join(download_dir, "rera_download_log2.txt")
log.basicConfig(
    filename=log_file,
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=log.INFO
)
# Start Chrome Driver
def start_driver() -> WebDriver:
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

driver = start_driver()
reader = easyocr.Reader(['en'])
downloaded_count = 0

# CAPTCHA Handling
def captcha_submission(max_retries=10):
    for attempt in range(1, max_retries + 1):
        log.info(f"Attempt {attempt} of {max_retries}")
        captcha_element = driver.find_element(By.ID, "captcahCanvas")
        captcha_element.screenshot("captcha.png")
        time.sleep(3)
        reader = easyocr.Reader(['en'])
        result = reader.readtext("captcha.png", detail=0)
        captcha_text = result[0].strip() if result else ""
        captcha_text = re.sub(r'[^A-Za-z0-9]', '', captcha_text)
        print("CAPTCHA read:", captcha_text)
        log.info("CAPTCHA read:", captcha_text)
       

        captcha_box = driver.find_element(By.CSS_SELECTOR, "input[name='captcha']")
        captcha_box.click()
        captcha_box.clear()
        captcha_box.send_keys(captcha_text)
        time.sleep(2)

        driver.find_element(By.XPATH, "//button[contains(text(), 'Submit')]").click()
        log.info("Submitted CAPTCHA")
        time.sleep(3)

        # ✅ Check if captcha passed
        error_elements = driver.find_elements(By.XPATH, "//p[contains(text(), 'Invalid Captcha')]")
        if not error_elements:
            log.info("CAPTCHA accepted.")
            return True
        log.info(" CAPTCHA failed. Retrying...")
        driver.find_element(By.XPATH, "//button[contains(text(), 'Ok')]").click()
        time.sleep(1)
        driver.find_element(By.CLASS_NAME, "cpt-btn").click()
        time.sleep(2)
    log.info(" Max CAPTCHA attempts reached.")
    return False

# 🧠 Filter out already downloaded
df = df[df["Download Status"].isin(["Not Found", "nan", "None", ""]) | df["Download Status"].isna()]

# 🔁 Loop through projects
for index, row in df.iterrows():
    project_id = str(row["Project ID"]).strip()
    view_details_link = row.get("View Details Link", "")
    file_path = os.path.join(download_dir, f"{project_id}_2.pdf")

    if os.path.exists(file_path):
        log.info(f" Already downloaded: {file_path}")
        df.loc[index, "Download Status"] = "Downloaded"
        continue


    if isinstance(view_details_link, str) and "http" in view_details_link:
        log.info(f"Opening View Details for Project ID: {project_id}")
        driver.get(view_details_link)

    if not captcha_submission():
        log.info(f"Skipping {project_id} due to CAPTCHA failures")
        continue

    # 🖨️ log.info and Save PDF
    try:
        pyautogui.click(x=900, y=500, button='right')
        time.sleep(2)
        pyautogui.press('down')
        pyautogui.press('down')
        pyautogui.press('enter')
        log.info(" log.info dialog.info triggered")

        time.sleep(3)
        pyautogui.press('enter')
        time.sleep(4)
        pyautogui.write(file_path)
        time.sleep(2)
        pyautogui.press('enter')
        log.info(" Data Saved")
        time.sleep(10)
    except Exception as e:
        log.info(f"log.info/save failed for {project_id}: {e}")

driver.quit()
log.info("Done. All processes completed.")

