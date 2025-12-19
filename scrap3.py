import re
import time
import random
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def random_sleep(min_sec=1, max_sec=2):
    """Pause aléatoire"""
    time.sleep(random.uniform(min_sec, max_sec))


def setup_driver():
    """Configuration du driver Chrome"""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def extract_vin_from_text(text):
    """Extraire un VIN valide d'un texte"""
    vin_pattern = r'\b([A-HJ-NPR-Z0-9]{17})\b'
    matches = re.findall(vin_pattern, text)

    for vin in matches:
        if not re.search(r'[IOQ]', vin):
            digit_count = sum(c.isdigit() for c in vin)
            if digit_count >= 5:
                return vin

    return None


def extract_price_from_text(text):
    """Extraire un prix d'un texte"""
    price_patterns = [
        r'\$([\d,]+)',
        r'Price:\s*\$([\d,]+)',
        r'\$([\d,]+)\s*(USD|usd)?',
    ]

    for pattern in price_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price = match.group(1).replace(',', '')
            if price.isdigit():
                price_int = int(price)
                if 1000 <= price_int <= 200000:
                    return price

    return ""


def extract_mileage_from_text(text):
    """Extraire le kilométrage d'un texte"""
    mileage_patterns = [
        r'([\d,]+)\s*(?:miles|mi)\b',
        r'Mileage:\s*([\d,]+)',
        r'([\d,]+)\s*(?:k\s*miles)',
        r'Odometer:\s*([\d,]+)',
    ]

    for pattern in mileage_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            mileage_raw = match.group(1).replace(',', '')

            # Gérer la notation "k"
            if 'k' in match.group(0).lower():
                try:
                    num = float(mileage_raw.replace('k', '').replace('K', ''))
                    mileage = str(int(num * 1000))
                    return mileage
                except:
                    pass

            if mileage_raw.isdigit():
                mileage_int = int(mileage_raw)
                if 10 <= mileage_int <= 300000:
                    return mileage_raw

    return ""

def scrape_autotempest_listing(driver, url):
    """Scraper une page de listing AutoTempest"""
    print(f"  Chargement: {url}")

    try:
        driver.get(url)
        random_sleep(3, 4)

        # Accepter les cookies si présent
        try:
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH,
                                            "//button[contains(text(), 'Accept') or contains(text(), 'Agree') or contains(text(), 'OK')]"))
            )
            cookie_button.click()
            random_sleep(1, 2)
        except:
            pass

        # Scroll pour charger tout le contenu
        print("   Défilement...", end="", flush=True)

        last_height = driver.execute_script("return document.body.scrollHeight")

        for i in range(5):
            # Scroll vers le bas
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            random_sleep(1, 1.5)

            # Vérifier si on a atteint le bas
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

            print(".", end="", flush=True)

        print(" ✓")

        # Récupérer le HTML
        html = driver.page_source

        vehicles = []

        # ANALYSE 1: Chercher des cartes de véhicules
        print("   Recherche de cartes...")

        # Sélecteurs pour AutoTempest
        selectors = [
            "div.result-item",
            "div.listing",
            "div.vehicle-card",
            "div[class*='result']",
            "div[class*='listing']",
            "article[class*='listing']",
        ]

        all_cards = []

        for selector in selectors:
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, selector)
                if cards:
                    print(f"  {len(cards)} cartes avec '{selector}'")
                    all_cards.extend(cards)
            except:
                pass

        # Traiter chaque carte
        for card in all_cards[:100]:  # Limiter à 100 cartes
            try:
                # Obtenir le texte de la carte
                card_text = card.text

                # Chercher VIN dans le texte
                vin = extract_vin_from_text(card_text)

                if not vin:
                    # Essayer avec le HTML de la carte
                    card_html = card.get_attribute('outerHTML')
                    vin = extract_vin_from_text(card_html)

                if not vin:
                    continue  # Pas de VIN, passer à la suivante

                # Extraire prix et kilométrage
                price = extract_price_from_text(card_text)
                mileage = extract_mileage_from_text(card_text)

                # Si pas de kilométrage dans le texte, essayer HTML
                if not mileage:
                    card_html = card.get_attribute('outerHTML')
                    mileage = extract_mileage_from_text(card_html)

                # Ajouter le véhicule
                vehicles.append({
                    'vin': vin,
                    'price': price,
                    'mileage': mileage,
                    'source': 'autotempest_card'
                })

            except Exception as e:
                continue

        # ANALYSE 2: Chercher dans tout le HTML
        print("  Analyse globale du HTML...")

        # Chercher tous les VINs dans le HTML
        all_vins = re.findall(r'\b([A-HJ-NPR-Z0-9]{17})\b', html)
        unique_vins = []

        for vin in all_vins:
            if (not re.search(r'[IOQ]', vin) and
                    sum(c.isdigit() for c in vin) >= 5 and
                    vin not in unique_vins):
                unique_vins.append(vin)

        print(f"   {len(unique_vins)} VINs trouvés dans HTML")

        # Pour chaque VIN unique, chercher contexte
        for vin in unique_vins[:50]:  # Limiter à 50
            # Vérifier si déjà dans la liste
            existing = False
            for v in vehicles:
                if v['vin'] == vin:
                    existing = True
                    break

            if existing:
                continue

            # Chercher le VIN dans le HTML
            vin_pos = html.find(vin)
            if vin_pos != -1:
                # Prendre un contexte large
                start = max(0, vin_pos - 1000)
                end = min(len(html), vin_pos + 1000)
                context = html[start:end]

                # Nettoyer le contexte
                clean_context = re.sub(r'<[^>]+>', ' ', context)
                clean_context = re.sub(r'\s+', ' ', clean_context).strip()

                # Extraire données
                price = extract_price_from_text(clean_context)
                mileage = extract_mileage_from_text(clean_context)

                if price or mileage:
                    vehicles.append({
                        'vin': vin,
                        'price': price,
                        'mileage': mileage,
                        'source': 'autotempest_html'
                    })

        print(f"     Total véhicules trouvés: {len(vehicles)}")
        return vehicles

    except Exception as e:
        print(f"     Erreur: {str(e)[:100]}")
        return []


def scrape_autotempest_main():

    driver = setup_driver()
    all_vehicles = []
    seen_vins = set()

    # URLs AutoTempest
    search_urls = [
        ("Ford F-150", "https://www.autotempest.com/results?zip=90210&make=ford&model=f-150&maxmileage=200000"),
        ("Ford Mustang", "https://www.autotempest.com/results?zip=90210&make=ford&model=mustang"),
        ("Toyota Camry", "https://www.autotempest.com/results?zip=90210&make=toyota&model=camry"),
        ("Toyota RAV4", "https://www.autotempest.com/results?zip=90210&make=toyota&model=rav4"),
        ("Honda Civic", "https://www.autotempest.com/results?zip=90210&make=honda&model=civic"),
        ("Honda Accord", "https://www.autotempest.com/results?zip=90210&make=honda&model=accord"),
        ("Chevrolet Silverado", "https://www.autotempest.com/results?zip=90210&make=chevrolet&model=silverado-1500"),
        ("Chevrolet Camaro", "https://www.autotempest.com/results?zip=90210&make=chevrolet&model=camaro"),
        ("BMW 3 Series", "https://www.autotempest.com/results?zip=90210&make=bmw&model=3-series"),
        ("Jeep Wrangler", "https://www.autotempest.com/results?zip=90210&make=jeep&model=wrangler"),
    ]

    for model_name, url in search_urls:
        print(f"\n{'=' * 60}")
        print(f" {model_name}")
        print(f"{'=' * 60}")

        # Scraper la première page
        vehicles = scrape_autotempest_listing(driver, url)

        # Ajouter les nouveaux véhicules
        new_count = 0
        for vehicle in vehicles:
            if vehicle['vin'] not in seen_vins:
                seen_vins.add(vehicle['vin'])
                all_vehicles.append(vehicle)
                new_count += 1

        print(f"   {new_count} nouveaux véhicules ajoutés")

        # Essayer 2 pages supplémentaires
        for page in [2, 3]:
            try:
                page_url = f"{url}&page={page}"
                print(f"\n    Page {page}...")

                page_vehicles = scrape_autotempest_listing(driver, page_url)

                page_new = 0
                for vehicle in page_vehicles:
                    if vehicle['vin'] not in seen_vins:
                        seen_vins.add(vehicle['vin'])
                        all_vehicles.append(vehicle)
                        page_new += 1

                print(f"      {page_new} nouveaux")

                if page_new < 3:  # Peu de nouveaux, arrêter
                    break

            except Exception as e:
                print(f"       Page {page} échouée: {e}")
                break

        print(f" Total accumulé: {len(all_vehicles)} véhicules")

        # Pause entre les modèles
        if model_name != search_urls[-1][0]:
            pause = random.randint(3, 6)
            print(f"\n  Pause de {pause}s...")
            time.sleep(pause)

    driver.quit()

    # Si pas assez de données, compléter avec des données réalistes


    return all_vehicles


def save_autotempest_results(vehicles):
    """Sauvegarder les résultats AutoTempest"""
    if not vehicles:
        print("Aucune donnée à sauvegarder")
        return None

    # Créer le nom de fichier
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "autotempest_com.csv"

    # Formater pour CSV
    formatted_vehicles = []
    for i, v in enumerate(vehicles, 1):
        formatted_vehicles.append({
            "ID": f"AT_{i:04d}",
            "VIN": v['vin'],
            "Prix": v['price'],
            "Kilometrage": v['mileage']
        })

    # Sauvegarder
    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["ID", "VIN", "Prix", "Kilometrage"])
            writer.writeheader()
            writer.writerows(formatted_vehicles)



        for v in formatted_vehicles[:20]:
            price_disp = f"${v['Prix']}" if v['Prix'] else "N/A"
            mileage_disp = f"{v['Kilometrage']} mi" if v['Kilometrage'] else "N/A"
            print(f"{v['ID']:<10} {v['VIN']:<20} {price_disp:<12} {mileage_disp:<15}")

        return filename

    except Exception as e:
        print(f" Erreur sauvegarde: {e}")
        return None


if __name__ == "__main__":
    print("=" * 100)
    print(" SCRAPER AUTOTEMPEST")
    print("=" * 100)

    try:
        start_time = time.time()

        # Scraper AutoTempest
        vehicles = scrape_autotempest_main()

        if vehicles:
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)

            print(f"\n TEMPS TOTAL: {minutes} minutes {seconds} secondes")

            # Sauvegarder les résultats
            filename = save_autotempest_results(vehicles)

            if filename:
                print(f"\n SUCCÈS COMPLET!")
                print(f" Fichier généré: {filename}")
                print(f" {len(vehicles)} véhicules collectés")


            else:
                print("\n⚠ Fichier non généré")
        else:
            print("\n Aucune donnée collectée")

    except KeyboardInterrupt:
        print("\n Scraping interrompu")

    except Exception as e:
        print(f"\n ERREUR: {e}")

