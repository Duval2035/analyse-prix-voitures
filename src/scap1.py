import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import random
from urllib.parse import urljoin

import json


BASE_URL = "https://www.cars.com/shopping/results/"
MAX_PAGES = 90
MAX_ANNOUNCEMENTS = 800
MIN_DELAY = 3
MAX_DELAY = 4

# SÉLECTEURS SIMPLIFIÉS
SELECTORS = {
    'annonce': 'div.vehicle-card',
    'prix': 'span.primary-price',
    'lien': 'a.vehicle-card-link',
    'titre': 'h2.title',
    'kilometrage_liste': 'div.mileage, span.mileage, div[class*="mileage"]',
}

# SÉLECTEURS PAGE DÉTAILLÉE
DETAIL_SELECTORS = {
    'vin': 'li.vin-number span',
    'vin_alternatives': [
        'div.vin-number',
        'dt:-soup-contains("VIN") + dd',
        'span:-soup-contains("VIN")'
    ],
    'vin_meta': 'meta[property="vehicle:vin"]',
    'kilometrage': [
        'dt:-soup-contains("Mileage") + dd',
        'div[class*="mileage"]',
        'span[class*="mileage"]',
        'li:-soup-contains("Mileage")',
    ],
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# --- FONCTIONS ---
def detecter_vin(texte):
    """Détecte un VIN dans un texte"""
    if not texte:
        return None
    vin_pattern = r'\b(?![IOQ])[A-HJ-NPR-Z0-9]{17}\b'
    matches = re.findall(vin_pattern, texte.upper())
    for match in matches:
        if len(match) == 17:
            return match
    return None

def extraire_kilometrage(soup, url="", source="detail"):
    try:
        kilometrage = None
        page_text = soup.get_text()

        # JSON-LD
        try:
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        for key in ['mileageFromOdometer', 'mileage', 'odometer', 'vehicleMileage']:
                            if key in data:
                                value = data[key]
                                value = value.get('@value', value) if isinstance(value, dict) else value
                                match = re.search(r'(\d{1,3}(?:,\d{3})*)', str(value))
                                if match:
                                    return int(match.group(1).replace(',', ''))
                except:
                    continue
        except:
            pass

        # Sélecteurs CSS
        km_selectors = DETAIL_SELECTORS['kilometrage'] if source == "detail" else [SELECTORS['kilometrage_liste']]
        for selector in km_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    km_text = element.get_text(strip=True)
                    matches = re.findall(r'([\d,]+)', km_text)
                    for match in matches:
                        km_value = match.replace(',', '')
                        if km_value.isdigit():
                            return int(km_value)
            except:
                continue

        # Regex globale
        patterns = [
            r'Mileage[:\s]*(\d{1,3}(?:,\d{3})*)',
            r'(\d{1,3}(?:,\d{3})*)\s*miles',
            r'(\d{1,3}(?:,\d{3})*)\s*mi\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, page_text)
            if match:
                km_value = match.group(1).replace(',', '')
                return int(km_value)

        return None

    except Exception as e:

        return None


def scraper_page_detail(url):
    try:
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # VIN
        vin = None

        vin_meta = soup.select_one(DETAIL_SELECTORS['vin_meta'])
        if vin_meta and detecter_vin(vin_meta.get('content', '')):
            vin = vin_meta.get('content')

        if not vin:
            elem = soup.select_one(DETAIL_SELECTORS['vin'])
            if elem:
                vin = detecter_vin(elem.get_text(strip=True))

        if not vin:
            for selector in DETAIL_SELECTORS['vin_alternatives']:
                elem = soup.select_one(selector)
                if elem:
                    vin = detecter_vin(elem.get_text(strip=True))
                    if vin:
                        break

        if not vin:
            vin = detecter_vin(soup.get_text())

        # Kilométrage
        km = extraire_kilometrage(soup, url, "detail")

        if vin:
            return {
                'vin': vin,
                'kilometrage_detail': km,
                'url_detail': url
            }
        return None

    except Exception as e:

        return None


def extraire_texte(element, selector, default=None):
    if not element:
        return default
    found = element.select_one(selector)
    return found.get_text(strip=True) if found else default


def extraire_attribut(element, selector, attribut='href', default=None):
    if not element:
        return default
    found = element.select_one(selector)
    return found.get(attribut, default) if found else default


def extraire_kilometrage_liste(annonce):
    try:
        km_element = annonce.select_one(SELECTORS['kilometrage_liste'])
        if km_element:
            match = re.search(r'([\d,]+)', km_element.get_text(strip=True))
            return int(match.group(1).replace(',', '')) if match else None
        return None
    except:
        return None


# --- SCRAPING PRINCIPAL ---
params = {
    'stock_type': 'used',
    'page_size': '20',
    'zip': '10001',
    'sort': 'best_match',
}

liste_annonces_avec_vin = []
annonces_scrapees = 0
pages_scrapees = 0


for page_num in range(1, MAX_PAGES + 1):
    if len(liste_annonces_avec_vin) >= MAX_ANNOUNCEMENTS:
        break

    params['page'] = str(page_num)
    try:

        response = requests.get(BASE_URL, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        annonces = soup.select(SELECTORS['annonce'])
        if not annonces:

            break

        for annonce in annonces:
            if len(liste_annonces_avec_vin) >= MAX_ANNOUNCEMENTS:
                break

            prix_texte = extraire_texte(annonce, SELECTORS['prix'])
            lien_partiel = extraire_attribut(annonce, SELECTORS['lien'])
            kilometrage_liste = extraire_kilometrage_liste(annonce)

            prix = None
            if prix_texte:
                m = re.search(r'[\d,]+', prix_texte)
                if m:
                    prix = int(m.group().replace(',', ''))

            if not lien_partiel:
                continue
            lien_complet = urljoin("https://www.cars.com", lien_partiel)

            detail = scraper_page_detail(lien_complet)

            if detail and detail['vin']:
                km_final = detail['kilometrage_detail'] or kilometrage_liste

                annonce_data = {
                    'ID': f"CARS_{len(liste_annonces_avec_vin)+1:04d}",
                    'VIN': detail['vin'],
                    'Prix': prix,
                    'Kilometrage': km_final,
                }
                liste_annonces_avec_vin.append(annonce_data)

            annonces_scrapees += 1

        pages_scrapees += 1
        time.sleep(random.uniform(MIN_DELAY * 2, MAX_DELAY * 2))

    except Exception as e:

        break

# SAUVEGARDE
if liste_annonces_avec_vin:
    df = pd.DataFrame(liste_annonces_avec_vin)
    filename = "cars_com.csv"
    df.to_csv(filename, index=False)
    print(f"\nFichier sauvegardé : {filename}\n")
else:
    print("Aucune donnée collectée.")
