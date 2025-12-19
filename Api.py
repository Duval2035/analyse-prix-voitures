import pandas as pd
import requests
import time

from datetime import datetime
import re

class NHTSAVehicleDecoder:
    BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"

    def __init__(self, rate_limit_delay: float = 0.2):
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VehicleDecoder/1.0',
            'Accept': 'application/json'
        })

    def decode_vin_batch(self, vins: list, model_year: str = None) -> list:
        if not vins:
            return []

        all_results = []
        for i in range(0, len(vins), 50):
            batch = vins[i:i + 50]
            batch_results = self._decode_batch(batch, model_year)
            all_results.extend(batch_results)

            if i + 50 < len(vins):
                time.sleep(self.rate_limit_delay * 2)

        return all_results

    def _decode_batch(self, vins: list, model_year: str = None) -> list:
        try:
            url = f"{self.BASE_URL}/DecodeVINValuesBatch/"
            vin_string = ";".join(vins)
            params = {'format': 'json', 'data': vin_string}

            if model_year:
                params['modelyear'] = model_year


            response = self.session.post(url, data=params, timeout=50)
            response.raise_for_status()

            data = response.json()
            results = data.get('Results', [])

            return results

        except Exception as e:

            return []

def clean_vin(vin: str) -> str:
    if not vin or not isinstance(vin, str):
        return ""

    vin_clean = vin.upper().strip()
    vin_clean = re.sub(r'[^A-HJ-NPR-Z0-9]', '', vin_clean)

    if len(vin_clean) != 17 or re.search(r'[IOQ]', vin_clean):

        return ""

    return vin_clean

def extract_important_fields(api_result: dict) -> dict:
    if not api_result:
        return {}

    field_mapping = {
        'Make': 'Marque',
        'Model': 'Modèle',
        'ModelYear': 'Année',
        'VehicleType': 'Type',
        'BodyClass': 'Carrosserie',
        'EngineModel': 'Moteur',
        'DisplacementL': 'Cylindrée',
        'FuelTypePrimary': 'Carburant',
        'TransmissionStyle': 'Transmission',
        'DriveType': 'Traction',
        'Trim': 'Finition',
        'PlantCountry': 'Pays_assemblage',
        'PlantCity': 'Ville_assemblage',
        'PlantState': 'Etat_assemblage',
        'Series': 'Série',
        'Doors': 'Portes',
        'Windows': 'Vitres',
        'Seats': 'Sièges'
    }

    extracted = {}

    for api_field, french_name in field_mapping.items():
        value = api_result.get(api_field)
        if value and str(value).strip() not in ['', 'Not Applicable', 'None']:
            extracted[french_name] = str(value).strip()

    extracted['VIN'] = api_result.get('VIN', '')

    return extracted

def process_vin_list(vins: list, decoder: NHTSAVehicleDecoder) -> pd.DataFrame:

    clean_vins = []
    for vin in vins:
        cleaned_vin = clean_vin(vin)
        if cleaned_vin:
            clean_vins.append(cleaned_vin)

    if not clean_vins:
        return pd.DataFrame()

    batch_results = decoder.decode_vin_batch(clean_vins)

    all_data = []
    successful = 0

    for result in batch_results:
        vin = result.get('VIN', '')

        if result and vin:
            vehicle_info = extract_important_fields(result)

            if vehicle_info:
                all_data.append(vehicle_info)
                successful += 1

    df = pd.DataFrame(all_data)

    return df

def main():

    print("Decodeur")

    decoder = NHTSAVehicleDecoder(rate_limit_delay=0.1)

    print("\nOptions:")
    print("1. Charger les VINs depuis un fichier CSV")
    print("2. Entrer les VINs manuellement")
    print("3. Fusionner avec un fichier existant")

    choix = input("\nVotre choix (1, 2 ou 3): ").strip()
    vins, source_df = [], None

    if choix == "1":
        filename = input("Nom du fichier CSV (avec extension .csv): ").strip()
        try:
            df = pd.read_csv(filename)
            if 'VIN' in df.columns:
                vins = df['VIN'].dropna().astype(str).tolist()
                source_df = df
                print(f" {len(vins)} VINs chargés depuis {filename}")
            else:
                print("Colonne 'VIN' non trouvée")
                return
        except Exception as e:
            print(f" Erreur: {e}")
            return

    elif choix == "2":
        print("\nEntrez les VINs (un par ligne, vide pour terminer):")
        while True:
            vin = input("VIN: ").strip()
            if not vin:
                break
            vins.append(vin)

        if not vins:
            print(" Aucun VIN entré")
            return

    elif choix == "3":
        file1 = input("Fichier source avec VINs et prix: ").strip()
        try:
            source_df = pd.read_csv(file1)
            if 'VIN' in source_df.columns:
                vins = source_df['VIN'].dropna().astype(str).tolist()
                print(f"✓ {len(vins)} VINs chargés")
            else:
                print(" Colonne 'VIN' non trouvée")
                return
        except Exception as e:
            print(f" Erreur: {e}")
            return

    else:
        print("Choix invalide")
        return

    if not vins:
        print(" Aucun VIN à traiter")
        return

    print(f"\nTraitement de {len(vins)} VINs...")
    nhtsa_df = process_vin_list(vins, decoder)

    if nhtsa_df.empty:
        print(" Aucune donnée récupérée")
        return

    if source_df is not None and choix in ["1", "3"]:
        source_df['VIN_clean'] = source_df['VIN'].apply(clean_vin)
        nhtsa_df['VIN_clean'] = nhtsa_df['VIN'].apply(clean_vin)

        merged_df = pd.merge(
            source_df,
            nhtsa_df,
            left_on='VIN_clean',
            right_on='VIN_clean',
            how='left',
            suffixes=('_source', '_nhtsa')
        )

        merged_df = merged_df.drop(columns=['VIN_clean', 'VIN_nhtsa'])
        merged_df = merged_df.rename(columns={'VIN_source': 'VIN'})

        merged_file = 'vehiculecomplet.csv'
        merged_df.to_csv(merged_file, index=False, encoding='utf-8')

        print("\n COMPLÉTITUDE DES DONNÉES:")
        important_cols = ['Marque', 'Modèle', 'Année', 'Type', 'Carburant']
        for col in important_cols:
            if col in merged_df.columns:
                filled = merged_df[col].notna().sum()
                percentage = (filled / len(merged_df)) * 100
                print(f"  {col}: {filled}/{len(merged_df)} ({percentage:.1f}%)")

    print("\n TRAITEMENT TERMINÉ")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n Interruption par l'utilisateur")
    except Exception as e:
        print(f"\n Erreur inattendue: {e}")