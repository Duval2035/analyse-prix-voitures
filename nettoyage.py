import pandas as pd
import numpy as np

df = pd.read_csv("vehiculecomplet.csv", index_col=0)

# Traitement spécifique pour chaque type de données
for colonne in df.columns:
    print(f"Traitement de la colonne '{colonne}' - {df[colonne].dtype}")
    
    if colonne == "Prix":
        # Gestion spéciale pour la colonne Prix
        print(f" Gestion speciale pour la colonne Prix")
        # D'abord, nettoyer les valeurs (enlever $, espaces, etc.)
        if  df[colonne].dtype == "object":
            df[colonne].df[colonne].astype(str).str.replace('$', '', regex=False)
            df[colonne] = df[colonne].str.replace(',', '', regex=False)
            df[colonne] = df[colonne].str.strip()

            # Convertir en numérique, erreurs -> NaN
            df[colonne] = pd.to_numeric(df[colonne], errors='coerce')

            # Remplacer les NaN par 0
        df[colonne] = df[colonne].fillna(0)

        # Convertir en int si possible
        try:
            df[colonne] = df[colonne].astype(int)
            print(f"  Prix converti en int")
        except:
            print(f"  Prix gardé en float")

    elif colonne in ['Année', 'Kilometrage']:
        # Colonnes numériques : remplacer NaN par 0 et convertir en int
        df[colonne] = df[colonne].fillna(0)
        # Convertir les float en int si possible
        try:
            df[colonne] = df[colonne].astype(int)
        except:
            # Si conversion impossible, garder en float
            pass

    elif colonne in ['Marque', 'Modèle', 'Type', 'Carburant', 'Transmission']:
        # Colonnes textuelles : remplacer NaN par "Inconnu"
        df[colonne] = df[colonne].fillna("Inconnu")
    else:
        # Pour les autres colonnes
        if pd.api.types.is_numeric_dtype(df[colonne]):
            df[colonne] = df[colonne].fillna(0)
        else:
            df[colonne] = df[colonne].fillna("Inconnu")

    if 'Année' in df.columns:
        print("Valeurs uniques dans 'Année' (premiers 10) :")
        print(df['Année'].unique()[:10])
        print()
    # Sauvegarder
    df.to_csv("vehiculecompletnettoyé.csv")