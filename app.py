import streamlit as st
import mysql.connector
from mysql.connector import Error
import pandas as pd
import re

# ======================================================================
# CONFIGURATION MYSQL (VERSION XAMPP)
# ======================================================================
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'projetpython2',
    'charset': 'utf8mb4',
    'port': 3307
}

# --- Classe DatabaseManager (fonctions inchangées) ---
class DatabaseManager:
    """Gère la connexion à la base de données MySQL."""

    def __init__(self):
        self.config = MYSQL_CONFIG.copy()
        self.port_val = int(self.config.pop('port', 3306))
        self.conn = None

    def connect(self):
        try:
            config_no_db = self.config.copy()
            config_no_db.pop('database', None)

            temp_conn = mysql.connector.connect(**config_no_db, port=self.port_val)
            cursor = temp_conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {self.config['database']} "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.close()
            temp_conn.close()

            self.conn = mysql.connector.connect(**self.config, port=self.port_val)
            return self.conn.is_connected()

        except Error as e:
            st.error(f"Erreur de connexion MySQL (XAMPP). Vérifie que MySQL est lancé. Détails : {e}")
            return False

    @st.cache_data(ttl=3600)
    def get_unique_values(_self, table, column):
        """Récupère les valeurs uniques d'une colonne donnée, triées."""
        if not _self.conn or not _self.conn.is_connected():
            return []

        query = f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL GROUP BY {column} ORDER BY {column} ASC"

        cursor = _self.conn.cursor()
        try:
            cursor.execute(query)
            return [row[0] for row in cursor.fetchall()]
        except mysql.connector.Error as err:
            st.error(f"Erreur SQL lors de la récupération des uniques : {err}")
            return []
        finally:
            cursor.close()

    @st.cache_data(ttl=3600)
    def rechercher_par_criteres(_self, marque_nom, annee):
        """Recherche et retourne une liste de véhicules selon des critères."""
        if not _self.conn or not _self.conn.is_connected():
            return pd.DataFrame()

        params = []
        conditions = []

        if marque_nom and marque_nom != "Tout":
            conditions.append("m.nom_marque = %s")
            params.append(marque_nom)

        if annee and annee != "Tout":
            conditions.append("v.annee = %s")
            params.append(int(annee))

        query = """
        SELECT
            v.vin, m.nom_marque AS Marque, modl.nom_modele AS Modèle, v.annee AS Année, 
            v.prix AS Prix, v.kilometrage AS Kilométrage, v.transmission AS Transmission,
            v.carburant AS Carburant
        FROM vehicules v
        LEFT JOIN marques m ON v.marque_id = m.id
        LEFT JOIN modeles modl ON v.modele_id = modl.id
        """

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " LIMIT 1000"

        cursor = _self.conn.cursor()
        try:
            cursor.execute(query, tuple(params))

            columns = [i[0] for i in cursor.description]
            data = cursor.fetchall()

            df = pd.DataFrame(data, columns=columns)
            df = df.fillna("Non spécifié")

            return df

        except mysql.connector.Error as err:
            st.error(f"Erreur SQL lors de la recherche multi-critères : {err}")
            return pd.DataFrame()
        finally:
            cursor.close()

    @st.cache_data(ttl=3600)
    def rechercher_vin(_self, vin):
        """Recherche et retourne TOUTES les informations d'un véhicule par son VIN."""
        if not _self.conn or not _self.conn.is_connected():
            return None

        query = """
        SELECT
            v.*, m.nom_marque, modl.nom_modele, s.nom_source
        FROM vehicules v
        JOIN sources s ON v.source_id = s.id
        LEFT JOIN marques m ON v.marque_id = m.id
        LEFT JOIN modeles modl ON v.modele_id = modl.id
        WHERE v.vin = %s
        LIMIT 1
        """
        cursor = _self.conn.cursor(dictionary=True)
        try:
            cursor.execute(query, (vin,))
            return cursor.fetchone()
        except mysql.connector.Error as err:
            st.error(f"Erreur SQL : {err}")
            return None
        finally:
            cursor.close()

    def disconnect(self):
        if self.conn and self.conn.is_connected():
            self.conn.close()


# --- Streamlit ---

@st.cache_resource
def get_db_manager():
    manager = DatabaseManager()
    if manager.connect():
        return manager
    return None


def main_app():
    st.set_page_config(
        page_title="Recherche & Analyse Véhicules",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("Centre d'Analyse des Véhicules")
    st.markdown("---")

    db_manager = get_db_manager()

    if not db_manager:
        st.error("Connexion MySQL impossible. Vérifie XAMPP → MySQL est bien lancé.")
        return

    # -----------------------------------------------------------
    # NOUVEAU: SÉLECTION DU MODE DANS LA BARRE LATÉRALE
    # -----------------------------------------------------------
    st.sidebar.header("Mode de Recherche")
    mode = st.sidebar.radio(
        "Choisissez la fonctionnalité :",
        ["Recherche par VIN", "Analyse par Critères"],
        key="mode_selection"
    )
    st.sidebar.markdown("---")

    # Initialisation des variables de recherche
    vin_input = ""
    selected_marque = ""
    selected_annee = ""

    # --- MODE 1: RECHERCHE PAR VIN ---
    if mode == "Recherche par VIN":

        st.subheader("Fiche Détaillée par VIN")

        # Affichage du champ VIN dans la barre latérale pour ce mode
        vin_input = st.sidebar.text_input(
            "Entrez le VIN à Rechercher (17 caractères) :",
            placeholder="Ex: JF2SJALC0HH438002",
            max_chars=17,
            key="vin_saisie"
        ).strip().upper()

        if vin_input:
            if len(vin_input) != 17 or not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', vin_input):
                st.error("Le VIN doit contenir exactement 17 caractères valides (sans I, O, Q).")
                return

            with st.spinner(f"Recherche du VIN {vin_input} ..."):
                info_vehicule = DatabaseManager.rechercher_vin(db_manager, vin_input)

            st.markdown("---")

            if info_vehicule:
                st.success(f"Véhicule trouvé : {info_vehicule.get('nom_marque')} {info_vehicule.get('nom_modele')}")

                tab1, tab2 = st.tabs(["Fiche Technique", "Informations Commerciales"])

                colonnes_a_exclure = ['id', 'source_id', 'marque_id', 'modele_id', 'date_import']
                data_technique = []
                data_commerciale = []

                for cle, valeur in info_vehicule.items():
                    if cle in colonnes_a_exclure or cle.endswith('_id'):
                        continue

                    nom_lisible = cle.replace('_', ' ').title()

                    if valeur is None:
                        valeur_formattee = "Non spécifié"
                        cible = data_technique
                    elif cle == 'prix':
                        valeur_formattee = f"{valeur:,.2f} €"
                        cible = data_commerciale
                    elif cle == 'kilometrage':
                        try:
                            valeur_formattee = f"{int(valeur):,} km"
                        except:
                            valeur_formattee = str(valeur)
                        cible = data_commerciale
                    elif cle == 'nom_source':
                        valeur_formattee = str(valeur)
                        cible = data_commerciale
                    elif cle in ['annee', 'vin', 'nom_marque', 'nom_modele', 'type_vehicule', 'carrosserie',
                                 'moteur', 'cylindree', 'carburant', 'transmission', 'traction']:
                        valeur_formattee = str(valeur)
                        cible = data_technique
                    else:
                        valeur_formattee = str(valeur)
                        cible = data_commerciale

                    if valeur is not None or valeur_formattee == "Non spécifié":
                        cible.append((nom_lisible, valeur_formattee))

                with tab1:
                    col_tech1, col_tech2 = st.columns(2)
                    midpoint_tech = (len(data_technique) + 1) // 2

                    with col_tech1:
                        for cle, val in data_technique[:midpoint_tech]:
                            st.markdown(f"**{cle}:** {val}")
                    with col_tech2:
                        for cle, val in data_technique[midpoint_tech:]:
                            st.markdown(f"**{cle}:** {val}")

                with tab2:
                    col_com1, col_com2 = st.columns(2)
                    midpoint_com = (len(data_commerciale) + 1) // 2

                    with col_com1:
                        for cle, val in data_commerciale[:midpoint_com]:
                            st.markdown(f"**{cle}:** {val}")
                    with col_com2:
                        for cle, val in data_commerciale[midpoint_com:]:
                            st.markdown(f"**{cle}:** {val}")

                if 'date_import' in info_vehicule and info_vehicule['date_import']:
                    st.info(
                        f"Dernière importation des données : {info_vehicule['date_import'].strftime('%Y-%m-%d %H:%M:%S')}")

            else:
                st.warning(f"Aucun véhicule trouvé pour le VIN : **{vin_input}**")

    # --- MODE 2: ANALYSE PAR CRITÈRES ---
    elif mode == "Analyse par Critères":

        st.subheader("Analyse Multi-critères et Visualisation de Données")

        # Affichage des filtres dans la barre latérale pour ce mode
        st.sidebar.header("Filtres d'Analyse")

        marques_options = ["Tout"] + db_manager.get_unique_values("marques", "nom_marque")
        annee_options = ["Tout"] + [str(a) for a in db_manager.get_unique_values("vehicules", "annee")]

        selected_marque = st.sidebar.selectbox("Sélectionner la Marque:", marques_options, key="filtre_marque")
        selected_annee = st.sidebar.selectbox("Sélectionner l'Année:", annee_options, key="filtre_annee")

        # Le bouton d'exécution permet d'éviter les rechargements constants
        if st.button("Rechercher et Afficher le Tableau"):

            with st.spinner("Chargement des résultats de la recherche..."):
                df_resultats = db_manager.rechercher_par_criteres(selected_marque, selected_annee)

            if not df_resultats.empty:

                st.info(f"{len(df_resultats)} véhicules trouvés correspondant aux filtres.")

                # Formatage des colonnes Prix et Kilométrage
                df_resultats['Prix'] = df_resultats['Prix'].apply(
                    lambda x: f"{x:,.0f} €" if isinstance(x, (int, float)) else x)
                df_resultats['Kilométrage'] = df_resultats['Kilométrage'].apply(
                    lambda x: f"{x:,.0f} km" if isinstance(x, (int, float)) else x)

                st.dataframe(df_resultats, use_container_width=True)

            else:
                st.warning("Aucun véhicule trouvé pour ces critères de recherche.")


if __name__ == '__main__':
    main_app()