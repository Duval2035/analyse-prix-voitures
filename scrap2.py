import re
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import csv

def scrape_cargurus_with_filters():
    # Configuration Chrome
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Liste pour stocker les véhicules avec VIN, prix et kilométrage
    vehicles = []

    try:
        # URL avec filtres pour Ram 1500 2012
        base_url = ("https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action"
                    "?sourceContext=carGurusHomePageModel"
                    "&entitySelectingHelper.selectedEntity=d835"  # Ram 1500
                    "&zip=90210"  # Code postal
                    "&distance=500"
                    "&minPrice=1000"
                    "&maxPrice=50000"
                    "&maxMileage=200000"
                    "&sortType=AGE_DESC")

        for page in range(1, 150):  # Pages 1 à 149
            if len(vehicles) >= 500: # Arret si 500 véhicule sont trouvés
                break



            url = f"{base_url}&page={page}"
            print(f"\nPage {page}: {url}")

            driver.get(url)

            # Attendre le chargement
            time.sleep(random.uniform(3, 10))

            # Scroll pour charger le contenu
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(4)

            # Récupérer le HTML
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # 1. Extraire les VINs depuis les attributs data-vin
            for element in soup.find_all(attrs={"data-vin": True}):
                vin = element["data-vin"]

                # Vérifier que c'est un VIN valide de 17 Caracteres
                if len(vin) == 17 and not re.search(r'[IOQ]', vin):

                    # Chercher le prix près de cet élément
                    price = None
                    mileage = None

                    # Méthode 1: Chercher dans le parent ou les éléments proches
                    parent = element.find_parent(['div', 'li', 'article'])
                    if parent:
                        # Chercher le prix et kilométrage dans le texte du parent
                        parent_text = parent.get_text()

                        # Chercher le prix
                        price_match = re.search(r'\$([\d,]+)', parent_text)
                        if price_match:
                            price = price_match.group(1).replace(',', '')

                        # Chercher le kilométrage
                        mileage_match = re.search(r'([\d,]+)\s*miles', parent_text, re.IGNORECASE)
                        if not mileage_match:
                            mileage_match = re.search(r'([\d,]+)\s*mi', parent_text, re.IGNORECASE)
                        if not mileage_match:
                            mileage_match = re.search(r'Mileage:\s*([\d,]+)', parent_text, re.IGNORECASE)

                        if mileage_match:
                            mileage = mileage_match.group(1).replace(',', '')

                    # Méthode 2: Si pas trouvé, chercher dans tout le document
                    if not price or not mileage:
                        # Chercher tous les prix et kilométrages sur la page

                        # Pour le prix
                        if not price:
                            all_prices = re.findall(r'\$([\d,]+)', html)
                            if all_prices:
                                for p in all_prices:
                                    price_num = int(p.replace(',', ''))
                                    if 1000 < price_num < 100000:
                                        price = p.replace(',', '')
                                        break

                        # Pour le kilométrage
                        if not mileage:
                            # Chercher les patterns de kilométrage
                            mileage_patterns = [
                                r'([\d,]+)\s*miles',
                                r'([\d,]+)\s*mi\b',
                                r'Mileage:\s*([\d,]+)',
                                r'(\d{1,3}(?:,\d{3})*)\s*(?:miles|mi)'
                            ]

                            for pattern in mileage_patterns:
                                mileage_matches = re.findall(pattern, html, re.IGNORECASE)
                                if mileage_matches:
                                    for m in mileage_matches:
                                        if isinstance(m, tuple):
                                            m = m[0]
                                        mileage_num = int(m.replace(',', ''))
                                        if 1 <= mileage_num <= 200000:
                                            mileage = m.replace(',', '')
                                            break
                                if mileage:
                                    break

                    # Vérifier si ce VIN n'existe pas déjà
                    existing_vins = [v['VIN'] for v in vehicles]
                    if vin not in existing_vins:
                        vehicles.append({
                            'ID': f"CG_{len(vehicles) + 1:04d}",
                            'VIN': vin,
                            'Prix': price if price else '',
                            'Kilometrage': mileage if mileage else ''
                        })
                        print(
                            f"  [{len(vehicles)}] ID: {vehicles[-1]['ID']}, VIN: {vin}, "
                            f"Prix: ${price if price else 'N/A'}, "
                            f"KM: {mileage if mileage else 'N/A'} miles")

                        if len(vehicles) >= 500:
                            break

            # 2. Extraire les VINs depuis le texte
            if len(vehicles) < 500:
                text = soup.get_text()
                matches = re.findall(r'\b[A-HJ-NPR-Z0-9]{17}\b', text)

                for match in matches:
                    if len(vehicles) >= 500:
                        break

                    # Vérifier que ce n'est pas un VIN invalide
                    if not re.search(r'[IOQ]', match):

                        # Chercher le prix et kilométrage près de ce VIN dans le texte
                        price = None
                        mileage = None

                        # Trouver la position du VIN dans le texte
                        start_pos = text.find(match)
                        if start_pos != -1:
                            # Extraire 500 caractères autour du VIN
                            context_start = max(0, start_pos - 250)
                            context_end = min(len(text), start_pos + 250)
                            context = text[context_start:context_end]

                            # Chercher un prix dans ce contexte
                            price_match = re.search(r'\$([\d,]+)', context)
                            if price_match:
                                price = price_match.group(1).replace(',', '')

                            # Chercher un kilométrage dans ce contexte
                            mileage_match = re.search(r'([\d,]+)\s*miles', context, re.IGNORECASE)
                            if not mileage_match:
                                mileage_match = re.search(r'([\d,]+)\s*mi', context, re.IGNORECASE)
                            if not mileage_match:
                                mileage_match = re.search(r'Mileage:\s*([\d,]+)', context, re.IGNORECASE)

                            if mileage_match:
                                mileage = mileage_match.group(1).replace(',', '')

                        # Vérifier si ce VIN n'existe pas déjà
                        existing_vins = [v['VIN'] for v in vehicles]
                        if match not in existing_vins:
                            vehicles.append({
                                'ID': f"CG_{len(vehicles) + 1:04d}",
                                'VIN': match,
                                'Prix': price if price else '',
                                'Kilometrage': mileage if mileage else ''
                            })
                            print(
                                f"  [{len(vehicles)}] ID: {vehicles[-1]['ID']}, VIN: {match}, "
                                f"Prix: ${price if price else 'N/A'}, "
                                f"KM: {mileage if mileage else 'N/A'} miles")

            print(f"  Véhicules sur cette page: {len(vehicles)}")
            print(f"  Total accumulé: {len(vehicles)}")

            # Pause entre les pages
            if page < 3 and len(vehicles) < 50:
                time.sleep(random.uniform(4, 8))

    except Exception as e:
        print(f"Erreur: {e}")
    finally:
        driver.quit()

    return vehicles[:500]  # Retourne max 20 véhicules


# Fonction pour extraire spécifiquement le kilométrage des annonces CarGurus
def extract_mileage_from_cargurus(element):
    """Extrait le kilométrage d'un élément d'annonce CarGurus"""
    try:
        # Chercher dans plusieurs sélecteurs possibles pour CarGurus
        mileage_selectors = [
            'span[data-cg="listingMileage"]',
            'div.mileage',
            'span.mileage',
            'div[class*="mileage"]',
            'span[class*="mileage"]',
            'p[class*="mileage"]',
        ]

        # Essayer les sélecteurs CSS
        for selector in mileage_selectors:
            mileage_elem = element.select_one(selector)
            if mileage_elem:
                mileage_text = mileage_elem.get_text(strip=True)
                mileage_match = re.search(r'([\d,]+)', mileage_text)
                if mileage_match:
                    return mileage_match.group(1).replace(',', '')

        # Chercher dans le texte de l'élément
        element_text = element.get_text()
        mileage_patterns = [
            r'([\d,]+)\s*miles',
            r'([\d,]+)\s*mi\b',
            r'Mileage:\s*([\d,]+)',
            r'(\d{1,3}(?:,\d{3})*)\s*(?:miles|mi)'
        ]

        for pattern in mileage_patterns:
            match = re.search(pattern, element_text, re.IGNORECASE)
            if match:
                if isinstance(match.group(1), tuple):
                    mileage = match.group(1)[0]
                else:
                    mileage = match.group(1)
                return mileage.replace(',', '')

        return None
    except:
        return None
# Exécution
if __name__ == "__main__":
    print("Scraping CarGurus avec prix et kilométrage...")
    vehicles = scrape_cargurus_with_filters()

    if vehicles:
        print(f"\n✅ {len(vehicles)} véhicules trouvés:")

        # Afficher avec ID, VIN, prix et kilométrage


        # Sauvegarder avec colonnes ID, VIN, Prix, Kilometrage
        with open('cargurus_com.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'VIN', 'Prix', 'Kilometrage'])
            for vehicle in vehicles:
                writer.writerow([
                    vehicle['ID'],
                    vehicle['VIN'],
                    vehicle['Prix'] if vehicle['Prix'] else '',
                    vehicle['Kilometrage'] if vehicle['Kilometrage'] else ''
                ])

        print(f"\nFichier sauvegardé: cargurus_com.csv")
        print(f"   Colonnes: ID, VIN, Prix, Kilometrage")

    else:
        print("❌ Aucun véhicule trouvé")