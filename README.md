Ce projet constitue une solution ETL ( Extraction, Transform, Load) tout-en-un développée pour rassembler des données sur les véhicule d'occasion provenant de divers sites américains.

   L'objectif est de les enrichir à l'aide d'une API, puis de les mettre à disposition pour analyse via une interface web interactive optimisée.

# ****·    1. Architecture du pipeline de données**** 

Le projet adopte une structure linéaire, divisée en quatre phases principales : 
• **Extraction** :  Trois scripts distincts de scraping sont utilisés pour collecter les données des 
annonces. 
• **Consolidation** :  Un module fusionne les fichiers récupérés tout en procédant au nettoyage 
des identifiants VIN (Vehicle Identification Number). 
• **Enrichissement** :  Un décodeur interagit avec l'API de la NHTSA afin d'obtenir des 
spécifications techniques précises. 
• **Exploitation** :  Une application Streamlit assure la gestion de la base de données MySQL et 
la présentation des données sous forme de visualisations interactives. 