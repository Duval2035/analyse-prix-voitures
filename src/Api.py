"""
Script pour obtenir les informations des véhicules via l'API NHTSA
"""
import pandas as pd
import requests
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import re

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NHTSAVehicleDecoder:
    """Classe pour décoder les informations véhicules via l'API NHTSA"""

    BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"

    def __init__(self, rate_limit_delay: float = 0.2):
        """
        Initialise le décodeur NHTSA

        Args:
            rate_limit_delay: Délai entre les requêtes (secondes)
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VehicleDecoder/1.0',
            'Accept': 'application/json'
        })

    def decode_vin_batch(self, vins: List[str], model_year: Optional[str] = None) -> List[Dict]:
        """
        Décode une liste de VINs par lot (jusqu'à 50 par requête)

        Args:
            vins: Liste des VINs à décoder
            model_year: Année du modèle (optionnel, améliore la précision)

        Returns:
            Liste des informations véhicules
        """
        if not vins:
            return []

        all_results = []

        # Traiter par lots de 50 (limite API)
        for i in range(0, len(vins), 50):
            batch = vins[i:i + 50]
            batch_results = self._decode_batch(batch, model_year)
            all_results.extend(batch_results)

            # Pause entre les lots
            if i + 50 < len(vins):
                time.sleep(self.rate_limit_delay * 2)

        return all_results

    def _decode_batch(self, vins: List[str], model_year: Optional[str] = None) -> List[Dict]:
        """
        Décode un lot de VINs
        """
        try:
            # Construire l'URL
            url = f"{self.BASE_URL}/DecodeVINValuesBatch/"

            # Format: VIN1;VIN2;VIN3...
            vin_string = ";".join(vins)

            # Paramètres
            params = {
                'format': 'json',
                'data': vin_string
            }

            if model_year:
                params['modelyear'] = model_year

            logger.info(f"Requête API pour {len(vins)} VINs...")

            response = self.session.post(url, data=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get('Results'):
                results = data['Results']
                logger.info(f"✓ {len(results)} résultats reçus")
                return results
            else:
                logger.warning("Aucun résultat dans la réponse")
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur requête API: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Erreur JSON: {e}")
            return []

    def decode_single_vin(self, vin: str, model_year: Optional[str] = None) -> Dict:
        """
        Décode un seul VIN
        """
        try:
            url = f"{self.BASE_URL}/DecodeVinValues/{vin}"
            params = {'format': 'json'}

            if model_year:
                params['modelyear'] = model_year

            logger.debug(f"Requête pour VIN: {vin}")
            time.sleep(self.rate_limit_delay)

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()

            if data.get('Results') and len(data['Results']) > 0:
                return data['Results'][0]
            else:
                return {}

        except Exception as e:
            logger.error(f"Erreur pour VIN {vin}: {e}")
            return {}

    def get_wmi(self, vin: str) -> Dict:
        """
        Obtient les informations WMI (World Manufacturer Identifier)
        """
        try:
            if len(vin) >= 3:
                wmi = vin[:3]
                url = f"{self.BASE_URL}/DecodeWMI/{wmi}"

                response = self.session.get(url, params={'format': 'json'}, timeout=15)
                response.raise_for_status()

                data = response.json()
                if data.get('Results') and len(data['Results']) > 0:
                    return data['Results'][0]
            return {}
        except Exception as e:
            logger.error(f"Erreur WMI pour {vin}: {e}")
            return {}

    def get_makes(self) -> List[Dict]:
        """Récupère toutes les marques disponibles"""
        try:
            url = f"{self.BASE_URL}/GetAllMakes"
            response = self.session.get(url, params={'format': 'json'}, timeout=15)
            response.raise_for_status()

            data = response.json()
            return data.get('Results', [])
        except Exception as e:
            logger.error(f"Erreur récupération marques: {e}")
            return []


def clean_vin(vin: str) -> str:
    """Nettoie et valide un VIN"""
    if not vin or not isinstance(vin, str):
        return ""

    # Convertir en majuscules, supprimer espaces et caractères spéciaux
    vin_clean = vin.upper().strip()
    vin_clean = re.sub(r'[^A-HJ-NPR-Z0-9]', '', vin_clean)

    # Vérifier la longueur
    if len(vin_clean) != 17:
        logger.warning(f"VIN invalide (longueur {len(vin_clean)}): {vin}")
        return ""

    # Vérifier les caractères interdits
    if re.search(r'[IOQ]', vin_clean):
        logger.warning(f"VIN contient caractères interdits (I,O,Q): {vin}")
        return ""

    return vin_clean


def extract_important_fields(api_result: Dict) -> Dict:
    """
    Extrait les champs importants des résultats de l'API
    """
    if not api_result:
        return {}

    # Mapping des champs API vers des noms plus lisibles
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

    # Informations additionnelles
    extracted['VIN'] = api_result.get('VIN', '')
    extracted['WMI'] = api_result.get('WMI', '')

    return extracted

def process_vin_list(vins: List[str], decoder: NHTSAVehicleDecoder) -> pd.DataFrame:
    """
    Traite une liste de VINs et retourne un DataFrame
    """
    logger.info(f"Traitement de {len(vins)} VINs...")

    all_data = []
    successful = 0
    failed = 0

    # Nettoyer les VINs
    clean_vins = []
    for vin in vins:
        cleaned_vin = clean_vin(vin)  # CORRECTION: changé 'clean_vin' en 'cleaned_vin'
        if cleaned_vin:
            clean_vins.append(cleaned_vin)
        else:
            failed += 1

    logger.info(f"VINs valides après nettoyage: {len(clean_vins)}")

    if not clean_vins:
        return pd.DataFrame()

    # Utiliser le décodage par lots pour plus d'efficacité
    batch_results = decoder.decode_vin_batch(clean_vins)

    for i, result in enumerate(batch_results):
        vin = result.get('VIN', '')

        if result and vin:
            # Extraire les informations importantes
            vehicle_info = extract_important_fields(result)

            if vehicle_info:
                all_data.append(vehicle_info)
                successful += 1
                logger.info(f"✓ VIN {vin}: {vehicle_info.get('Marque', 'N/A')} {vehicle_info.get('Modèle', 'N/A')}")
            else:
                failed += 1
                logger.warning(f"✗ VIN {vin}: Aucune information extraite")
        else:
            failed += 1
            logger.warning(f"✗ VIN {clean_vins[i] if i < len(clean_vins) else 'N/A'}: Résultat vide")

    # Créer le DataFrame
    df = pd.DataFrame(all_data)

    # Statistiques
    logger.info(f"\n📊 STATISTIQUES DE TRAITEMENT:")
    logger.info(f"  VINs traités: {len(vins)}")
    logger.info(f"  VINs valides: {len(clean_vins)}")
    logger.info(f"  Succès: {successful}")
    logger.info(f"  Échecs: {failed}")
    logger.info(f"  Taux de succès: {(successful / max(len(clean_vins), 1)) * 100:.1f}%")

    return df


def merge_with_existing_data(vin_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
    """
    Fusionne les données NHTSA avec les données source existantes
    """
    if vin_df.empty or source_df.empty:
        logger.warning("Données insuffisantes pour la fusion")
        return pd.DataFrame()

    # S'assurer que les colonnes VIN existent
    if 'VIN' not in vin_df.columns or 'VIN' not in source_df.columns:
        logger.error("Colonne VIN manquante dans un des DataFrames")
        return pd.DataFrame()

    # Nettoyer les VINs dans les deux DataFrames
    source_df['VIN_clean'] = source_df['VIN'].apply(clean_vin)
    vin_df['VIN_clean'] = vin_df['VIN'].apply(clean_vin)

    # Fusionner sur VIN
    merged_df = pd.merge(
        source_df,
        vin_df,
        left_on='VIN_clean',
        right_on='VIN_clean',
        how='left',
        suffixes=('_source', '_nhtsa')
    )

    # Supprimer les colonnes temporaires
    merged_df = merged_df.drop(columns=['VIN_clean', 'VIN_nhtsa'])

    # Renommer la colonne VIN source
    merged_df = merged_df.rename(columns={'VIN_source': 'VIN'})

    logger.info(f"Fusion réussie: {len(merged_df)} véhicules")
    logger.info(f"Colonnes ajoutées: {[col for col in vin_df.columns if col != 'VIN']}")

    return merged_df


def main():
    """Fonction principale"""
    print("=" * 60)
    print("DÉCODEUR VÉHICULES - API NHTSA")
    print("=" * 60)

    # Initialiser le décodeur
    decoder = NHTSAVehicleDecoder(rate_limit_delay=0.1)

    # Option 1: Charger depuis un fichier CSV
    # Option 2: Entrer manuellement des VINs
    print("\nOptions:")
    print("1. Charger les VINs depuis un fichier CSV")
    print("2. Entrer les VINs manuellement")
    print("3. Fusionner avec un fichier existant")

    choix = input("\nVotre choix (1, 2 ou 3): ").strip()

    vins = []
    source_df = None

    if choix == "1":
        # Charger depuis CSV
        filename = input("Nom du fichier CSV (avec extension .csv): ").strip()
        try:
            df = pd.read_csv(filename)
            if 'VIN' in df.columns:
                vins = df['VIN'].dropna().astype(str).tolist()
                source_df = df
                print(f"✓ {len(vins)} VINs chargés depuis {filename}")
            else:
                print("❌ Colonne 'VIN' non trouvée dans le fichier")
                return
        except Exception as e:
            print(f"❌ Erreur chargement fichier: {e}")
            return

    elif choix == "2":
        # Entrer manuellement
        print("\nEntrez les VINs (un par ligne, vide pour terminer):")
        while True:
            vin = input("VIN: ").strip()
            if not vin:
                break
            vins.append(vin)

        if not vins:
            print("❌ Aucun VIN entré")
            return

    elif choix == "3":
        # Fusionner avec fichier existant
        file1 = input("Fichier source avec VINs et prix: ").strip()
        try:
            source_df = pd.read_csv(file1)
            if 'VIN' in source_df.columns:
                vins = source_df['VIN'].dropna().astype(str).tolist()
                print(f"✓ {len(vins)} VINs chargés")
            else:
                print("❌ Colonne 'VIN' non trouvée")
                return
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            return

    else:
        print("❌ Choix invalide")
        return

    if not vins:
        print("❌ Aucun VIN à traiter")
        return

    # Traiter les VINs
    print(f"\nTraitement de {len(vins)} VINs...")
    nhtsa_df = process_vin_list(vins, decoder)

    if nhtsa_df.empty:
        print("❌ Aucune donnée récupérée de l'API NHTSA")
        return

    # Sauvegarder les données NHTSA
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nhtsa_file = f'nhtsa_vehicle_data_{timestamp}.csv'
    nhtsa_df.to_csv(nhtsa_file, index=False, encoding='utf-8')
    print(f"\n✓ Données NHTSA sauvegardées: {nhtsa_file}")

    # Fusionner si on a un fichier source
    if source_df is not None and choix in ["1", "3"]:
        merged_df = merge_with_existing_data(nhtsa_df, source_df)

        if not merged_df.empty:
            merged_file = f'vehicules_complets_{timestamp}.csv'
            merged_df.to_csv(merged_file, index=False, encoding='utf-8')
            print(f"✓ Fichier fusionné sauvegardé: {merged_file}")

            # Aperçu
            print("\n📋 APERÇU DES DONNÉES FUSIONNÉES (5 premières lignes):")
            print("-" * 80)
            print(merged_df.head().to_string())

            # Statistiques de complétude
            print("\n📊 COMPLÉTITUDE DES DONNÉES:")
            important_cols = ['Marque', 'Modèle', 'Année', 'Type', 'Carburant']
            for col in important_cols:
                if col in merged_df.columns:
                    filled = merged_df[col].notna().sum()
                    percentage = (filled / len(merged_df)) * 100
                    print(f"  {col}: {filled}/{len(merged_df)} ({percentage:.1f}%)")

    print("\n✅ TRAITEMENT TERMINÉ")
    print("=" * 60)


# Exemple d'utilisation en ligne de commande
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interruption par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback

        traceback.print_exc()