import os
import time
import smtplib
from email.mime.text import MIMEText
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

# --- JOUW GEGEVENS VIA ENV ---
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]

TARGET_URL = "https://brabantplus.omroepbrabant.nl"
KEYWORD = "Roeptoetgat"
CHECK_INTERVAL = 30  # seconden
WORKERS = 4

# geheugen per URL
geheugen = {}

# --- FUNCTIES ---
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
        print(f"✅ Mail verzonden: {onderwerp}", flush=True)
    except Exception as e:
        print(f"❌ Mail fout: {e}", flush=True)


def worker_taak(url_lijst, browser):
    """Worker checkt lijst van URL's binnen gedeelde browser."""
    context = browser.new_context()
    page = context.new_page()

    for url in url_lijst:
        try:
            print(f"   👉 Checken: {url}", flush=True)
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)

            tekst = page.inner_text("body")
            aantal_nu = tekst.lower().count(KEYWORD.lower())
            vorig_aantal = geheugen.get(url, None)

            if vorig_aantal is None:
                geheugen[url] = aantal_nu
                if aantal_nu > 0:
                    print(f"   📍 {url} -> Zichtbaar gevonden: {aantal_nu}x", flush=True)
                continue

            if aantal_nu > vorig_aantal:
                print(f"🎯 ECHTE MATCH GEVONDEN OP: {url}!", flush=True)
                stuur_mail(
                    f"🎯 ZICHTBARE MATCH: {KEYWORD}",
                    f"Het woord staat nu ECHT op de pagina: {url}\nAantal: {aantal_nu}"
                )
                geheugen[url] = aantal_nu

        except Exception as e:
            print(f"   ❌ Fout op {url}: {e}", flush=True)

    context.close()


def scan_site(ronde):
    """Haalt URLs op en verdeelt ze over workers."""
    print(f"\n🔍 [Ronde {ronde}] Start parallelle scan (Workers: {WORKERS})", flush=True)

    urls = [TARGET_URL]

    # Eerste pagina ophalen en links verzamelen
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(TARGET_URL, timeout=15000)
            page.wait_for_timeout(5000)
            links = page.query_selector_all("a")
            for l in links:
                href = l.get_attribute("href")
                if href and any(x in href for x in ["/programma/", "/video/", "/aflevering/", "/radio/", "/tv/"]):
                    full_url = urljoin(TARGET_URL, href)
                    if full_url not in urls:
                        urls.append(full_url)
        except Exception as e:
            print(f"⚠️ Fout bij verzamelen links: {e}", flush=True)
        finally:
            context.close()
            browser.close()

    # Verdeel de lijst in stukjes voor workers
    stukjes = [urls[i::WORKERS] for i in range(WORKERS)]

    # Gebruik één browser instance voor alle workers
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            executor.map(lambda chunk: worker_taak(chunk, browser), stukjes)
        browser.close()


# --- START DE LOOP ---
ronde_teller = 1
while True:
    try:
        scan_site(ronde_teller)
        print(f"😴 Ronde {ronde_teller} klaar. Wachten {CHECK_INTERVAL} sec...", flush=True)
        time.sleep(CHECK_INTERVAL)
        ronde_teller += 1
    except Exception as e:
        print(f"⚠️ Er ging iets mis in de hoofdloop: {e}", flush=True)
        time.sleep(10)
