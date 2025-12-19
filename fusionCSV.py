import pandas as pd
import os

def fusionner():
    fichiers = [
        "autotempest_com.csv",
        "cargurus_com.csv",
        "cars_com.csv"
    ]

    # Vérifier l'existence
    for f in fichiers:
        if not os.path.exists(f):
            raise FileNotFoundError(f"Fichier manquant : {f}")

    dataframes = []

    for fichier in fichiers:
        df = pd.read_csv(fichier)
        df.columns = df.columns.str.strip()

        # Uniformiser noms de colonnes
        mapping = {}
        for col in df.columns:
            c = col.lower()
            if "price" in c or "prix" in c:
                mapping[col] = "Prix"
            elif "mileage" in c or "kil" in c:
                mapping[col] = "Kilometrage"
            elif "vin" in c:
                mapping[col] = "VIN"

        df = df.rename(columns=mapping)

        # Ajouter source
        if "autotempest" in fichier:
            df["Source"] = "AutoTempest"
        elif "cargurus" in fichier:
            df["Source"] = "CarGurus"
        elif "cars_com" in fichier or "cars.com" in fichier:
            df["Source"] = "Cars.com"
        else:
            df["Source"] = "Autre"

        dataframes.append(df)

    # Fusion
    df = pd.concat(dataframes, ignore_index=True)

    # Nettoyage VIN
    if "VIN" in df.columns:
        df["VIN"] = (
            df["VIN"]
            .astype(str)
            .str.upper()
            .str.strip()
            .str.replace(r"[^A-HJ-NPR-Z0-9]", "", regex=True)
        )
        df = df[df["VIN"].str.len() == 17]
        df = df.drop_duplicates(subset=["VIN"], keep="first")

    # Nettoyage prix & km
    if "Prix" in df.columns:
        df["Prix"] = pd.to_numeric(df["Prix"], errors="coerce")

    if "Kilometrage" in df.columns:
        df["Kilometrage"] = pd.to_numeric(df["Kilometrage"], errors="coerce")

    # Export
    df.to_csv("fusion.csv", index=False, encoding="utf-8")

    print("✅ Fichier fusionné créé : fusion.csv")
    print(f"Total véhicules : {len(df)}")


if __name__ == "__main__":
    fusionner()
