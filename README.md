# Outil de Curation de Données PNDB & Recherche Intégrée

Ce projet est une application de bureau interactive développée en **Python** avec **PySide6**. Elle est spécialement conçue pour assister les experts et gestionnaires de données du **PNDB** (Pôle National de Données de Biodiversité) dans le processus de curation, d'alignement et de validation taxonomique de jeux de données avec le référentiel mondial **GBIF** (Global Biodiversity Information Facility).

## Fonctionnalités Principales

* **Gestion de Fichiers JSON** : Importation de listes de données brutes contenant des statuts de validation et ré-exportation propre après correction.
* **Validation Taxonomique Automatique** : Interrogation directe de l'API v2 de GBIF pour récupérer le nom canonique (`gbif_canonicalName`) et l'identifiant taxonomique officiel (`taxonID`).
* **Métadonnées PNDB en Direct** : Connexion à l'API du catalogue PNDB pour afficher dynamiquement le titre et la description en français du jeu de données sélectionné.
* **Contexte et Historique Interne** : Visualisation en temps réel des espèces déjà validées au sein du même jeu de données, avec possibilité d'annulation (*Invalidation*).
* **Enrichissement des Données** : Ajout à la volée de nouvelles espèces absentes du jeu de données d'origine.
* **Aide à la Recherche Intégrée** : Un navigateur web intégré (via `QWebEngineView`) lance automatiquement une recherche DuckDuckGo dès qu'un élément inconnu est sélectionné, évitant ainsi de quitter l'application pour chercher l'orthographe correcte d'un taxon.

---

## Prérequis & Installation

### 1. Cloner le dépôt
bash
git clone [https://github.com/votre-utilisateur/nom-du-depot.git](https://github.com/votre-utilisateur/nom-du-depot.git)
cd nom-du-depot

### 2. Installer les dépendances
L'application requiert Python 3.8+ ainsi que plusieurs modules tiers. Installez-les via pip :

Bash
pip install PySide6 requests python-dotenv
Note : L'utilisation de PySide6 inclut automatiquement les composants nécessaires à QWebEngineView.

### 3. Configuration des Variables d'Environnement
Afin de pouvoir interroger l'API du catalogue PNDB, vous devez créer un fichier .env à la racine de votre projet pour y ajouter votre clé API.

&nbsp;

Extrait de code :
```
API_KEY=votre_cle_api_pndb_ici
```
&nbsp;

## Utilisation

Pour lancer l'application, exécutez simplement la commande suivante :
```
Bash
python Taxo.curationX.py
```

## Processus de Curation Type :
**Charger** : Cliquez sur 1. Charger un fichier JSON. L'application filtre et affiche automatiquement dans la liste de gauche les éléments dont le statut est "not_found_on_gbif".

**Analyser** : Sélectionnez une ligne. L'application charge sa description PNDB, liste ses espèces parentes validées et ouvre la recherche web.

**Corriger** : Modifiez l'orthographe du nom scientifique dans le champ de saisie textuel si une coquille est détectée.

**Valider** : Cliquez sur 2. Valider avec GBIF v2. Si une correspondance est trouvée, le statut passe au vert et l'élément est mis à jour.

**Exporter** : Une fois le travail terminé, cliquez sur 3. Exporter le JSON corrigé pour sauvegarder vos modifications.

## Format de Données JSON Attendu
Le script s'attend à lire et écrire un dictionnaire JSON structuré par identifiants de jeux de données (dataset_id), contenant une liste d'objets :
```
JSON
{
    "dataset-id-exemple-123": [
        {
            "scientificName": "Passer domesticus",
            "gbif_canonicalName": "Passer domesticus",
            "taxonID": "[https://www.gbif.org/species/5231190](https://www.gbif.org/species/5231190)",
            "status": "validated"
        },
        {
            "scientificName": "Bad spelling taxon",
            "gbif_canonicalName": null,
            "taxonID": null,
            "status": "not_found_on_gbif"
        }
    ]
}
```
Un générateur de fichier JSON dans le format attendu se trouve à l'adresse : https://github.com/FCLMNHN/Cat.taxoCovX

## API Utilisées
GBIF Species API (v2) : https://api.gbif.org/v2/species/match

PNDB Catalog API (v2.1) : https://www.pndb.fr/api/explore/v2.1/...

⚖️ Licence
Ce projet est distribué sous licence MIT. N'hésitez pas à contribuer en ouvrant des Issues ou des Pull Requests.
