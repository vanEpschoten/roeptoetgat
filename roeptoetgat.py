import time
import os
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

# --- JOUW GEGEVENS ---
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]

TARGET_URL = "https://brabantplus.omroepbrabant.nl"
KEYWORD = "Roeptoetgat" 
CHECK_INTERVAL = 30  
WORKERS = 4 

geheugen = {}

def stuur_mail(onderwerp, bericht):
    msg = MIMEText(bericht)
    msg['Subject'] = onderwerp
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"✅ Mail verzonden: {onderwerp}")
    except Exception as e:
        print(f"❌ Mail fout: {e}")

def worker_taak(url_lijst):
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(service=Service(executable_path=GECKO_PATH), options=options)
    
    try:
        for url in url_lijst:
            try:
                print(f"   👉 Checken: {url}")
                driver.get(url)
                time.sleep(2)
                
                # --- DIT IS DE BELANGRIJKE WIJZIGING ---
                # We pakken alleen de tekst die ECHT op het scherm staat
                zichtbare_tekst = driver.find_element("tag name", "body").text
                aantal_nu = zichtbare_tekst.lower().count(KEYWORD.lower())
                # ---------------------------------------

                vorig_aantal = geheugen.get(url, None)

                if vorig_aantal is None:
                    geheugen[url] = aantal_nu
                    if aantal_nu > 0:
                        print(f"   📍 {url} -> Zichtbaar gevonden: {aantal_nu}x")
                    continue

                if aantal_nu > vorig_aantal:
                    print(f"🎯 ECHTE MATCH GEVONDEN OP: {url}!")
                    stuur_mail(f"🎯 ZICHTBARE MATCH: {KEYWORD}", f"Het woord staat nu ECHT op de pagina: {url}\nAantal: {aantal_nu}")
                    geheugen[url] = aantal_nu
            except Exception as e:
                print(f"   ❌ Fout op {url}: {e}")
    finally:
        driver.quit()

def scan_site(ronde):
    print(f"\n🔍 [Ronde {ronde}] Start parallelle scan (Workers: {WORKERS})")
    
    options = Options()
    options.add_argument("--headless")
    main_driver = webdriver.Firefox(service=Service(executable_path=GECKO_PATH), options=options)
    urls = [TARGET_URL]
    try:
        main_driver.get(TARGET_URL)
        time.sleep(5)
        links = main_driver.find_elements("tag name", "a")
        for l in links:
            href = l.get_attribute("href")
            if href and any(x in href for x in ["/programma/", "/video/", "/aflevering/", "/radio/", "/tv/"]):
                if href not in urls: urls.append(href)
    finally:
        main_driver.quit()

    # Verdeel de lijst in stukjes voor de workers
    stukjes = [urls[i::WORKERS] for i in range(WORKERS)]
    
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        executor.map(worker_taak, stukjes)

# --- START DE LOOP ---
ronde_teller = 1
while True:
    try:
        scan_site(ronde_teller)
        print(f"😴 Ronde {ronde_teller} klaar. Wachten {CHECK_INTERVAL} sec...")
        time.sleep(CHECK_INTERVAL)
        ronde_teller += 1
    except Exception as e:
        print(f"⚠️ Er ging iets mis in de hoofdloop: {e}")

        time.sleep(10)

