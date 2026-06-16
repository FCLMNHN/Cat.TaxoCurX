import os
import sys
import json
import requests
import urllib.parse
from dotenv import load_dotenv
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QListWidget, QListWidgetItem, QLabel, QLineEdit, 
    QFileDialog, QMessageBox, QGroupBox, QTextBrowser, QSplitter, QInputDialog,
    QScrollArea
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFontMetrics
from PySide6.QtWebEngineWidgets import QWebEngineView

# Charger les variables d'environnement à partir du fichier .env
load_dotenv()

# Configuration de la clé d'API selon votre modèle
ODS_API_KEY = os.getenv("API_KEY")

GBIF_API_URL = "https://api.gbif.org/v2/species/match"
PNDB_API_URL_TEMPLATE = "https://www.pndb.fr/api/explore/v2.1/catalog/datasets/{dataset_id}?timezone=UTC&include_links=false&include_app_metas=false"


def make_session() -> requests.Session:
    """Crée une session HTTP authentifiée pour le PNDB."""
    session = requests.Session()
    if ODS_API_KEY:
        session.headers.update({"Authorization": f"Apikey {ODS_API_KEY}"})
    else:
        print("Attention : Aucune clé API trouvée dans le fichier .env (Variable 'API_KEY')")
    return session


# Instanciation de la session globale réutilisable pour le PNDB
pndb_session = make_session()


def validate_with_gbif_v2(name):
    """Valide via l'API GBIF v2 (Direct HTTP - Sans authentification requise)."""
    try:
        resp = requests.get(GBIF_API_URL, params={'scientificName': name}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            diag = data.get('diagnostics', {})
            usage = data.get('usage', {})
            if diag.get('matchType') != 'NONE':
                taxon_key = usage.get('key') or data.get('usageKey')
                canonical = usage.get('canonicalName') or data.get('canonicalName')
                if taxon_key:
                    return {"taxonKey": taxon_key, "canonicalName": canonical}
    except Exception as e:
        print(f"Erreur lors de l'appel API GBIF: {e}")
        return None
    return None


def fetch_pndb_metadata(dataset_id):
    """Interroge l'API du PNDB en utilisant la session authentifiée."""
    try:
        url = PNDB_API_URL_TEMPLATE.format(dataset_id=dataset_id)
        # Utilisation de pndb_session au lieu de requests direct
        resp = pndb_session.get(url, timeout=5)
        if resp.status_code == 200:
            json_data = resp.json()
            metas = json_data.get("metas", {})
            default_meta = metas.get("default", metas.get("dcat_ap", {}))
            
            title = default_meta.get("title_fr") or default_meta.get("title") or dataset_id
            description = default_meta.get("description_fr") or default_meta.get("description") or "Aucune description disponible."
            
            return title, description
        elif resp.status_code in (401, 403):
            return dataset_id, "Erreur d'authentification PNDB : Vérifiez la clé API dans votre fichier .env."
    except Exception as e:
        print(f"Erreur lors de l'appel API PNDB: {e}")
    
    return dataset_id, "Impossible de charger les métadonnées du PNDB."


class DataCurationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Outil de Curation de Données PNDB & Recherche Intégrée (PySide6)")
        self.resize(1450, 900)
        
        self.full_data = {}  
        self.current_original_name = "" 
        
        self.setup_ui()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        global_layout = QVBoxLayout(main_widget)

        file_layout = QHBoxLayout()
        self.btn_load = QPushButton("1. Charger un fichier JSON")
        self.btn_load.clicked.connect(self.load_file)
        file_layout.addWidget(self.btn_load)

        self.btn_save = QPushButton("3. Exporter le JSON corrigé")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_file)
        file_layout.addWidget(self.btn_save)
        
        file_layout.addStretch()
        global_layout.addLayout(file_layout)

        main_splitter = QSplitter(Qt.Horizontal)
        global_layout.addWidget(main_splitter)

        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_group = QGroupBox("Éléments à corriger (not_found_on_gbif)")
        list_layout = QVBoxLayout(list_group)
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_item_select)
        list_layout.addWidget(self.list_widget)
        left_layout.addWidget(list_group, stretch=2)

        edit_group = QGroupBox("Curation et Informations PNDB")
        edit_layout = QVBoxLayout(edit_group)

        edit_layout.addWidget(QLabel("<b>Jeu de données (PNDB) :</b>"))
        self.lbl_pndb_title = QLabel("-")
        self.lbl_pndb_title.setWordWrap(True)
        self.lbl_pndb_title.setStyleSheet("font-weight: bold; color: #2C3E50; font-size: 11px;")
        edit_layout.addWidget(self.lbl_pndb_title)
        
        edit_layout.addWidget(QLabel("<b>Description du Dataset :</b>"))
        self.txt_pndb_description = QTextBrowser()
        self.txt_pndb_description.setOpenExternalLinks(True)
        
        metrics = QFontMetrics(self.txt_pndb_description.font())
        line_height = metrics.lineSpacing()
        self.txt_pndb_description.setMinimumHeight(line_height * 20 + 10)
        self.txt_pndb_description.setMaximumHeight(16777215)
        
        edit_layout.addWidget(self.txt_pndb_description)
        
        edit_layout.addSpacing(5)
        edit_layout.addWidget(QLabel("<b>Espèces déjà VALIDÉES dans ce jeu de données :</b>"))
        
        self.scroll_validated = QScrollArea()
        self.scroll_validated.setWidgetResizable(True)
        self.scroll_validated.setMaximumHeight(120)
        self.scroll_validated_container = QWidget()
        self.scroll_validated_layout = QVBoxLayout(self.scroll_validated_container)
        self.scroll_validated_layout.setContentsMargins(2, 2, 2, 2)
        self.scroll_validated_layout.setSpacing(4)
        self.scroll_validated.setWidget(self.scroll_validated_container)
        self.scroll_validated.setStyleSheet("background-color: #F8F9F9; border: 1px solid #D5D8DC;")
        edit_layout.addWidget(self.scroll_validated)
        
        edit_layout.addSpacing(10)

        edit_layout.addWidget(QLabel("<b>Surcharger le Scientific Name :</b>"))
        self.entry_scientific_name = QLineEdit()
        edit_layout.addWidget(self.entry_scientific_name)

        self.btn_validate = QPushButton("2. Valider avec GBIF v2")
        self.btn_validate.setEnabled(False)
        self.btn_validate.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_validate.clicked.connect(self.validate_item)
        edit_layout.addWidget(self.btn_validate)
        
        self.btn_add_species = QPushButton("➕ Ajouter une nouvelle espèce à ce Dataset")
        self.btn_add_species.setEnabled(False)
        self.btn_add_species.setStyleSheet("background-color: #0078D7; color: white; font-weight: bold;")
        self.btn_add_species.clicked.connect(self.add_new_species)
        edit_layout.addWidget(self.btn_add_species)
        
        edit_layout.addSpacing(15)

        self.lbl_canonical = QLabel("gbif_canonicalName : ")
        edit_layout.addWidget(self.lbl_canonical)

        self.lbl_taxon_id = QLabel("taxonID : ")
        edit_layout.addWidget(self.lbl_taxon_id)

        self.lbl_status = QLabel("status : ")
        self.lbl_status.setStyleSheet("font-weight: bold;")
        edit_layout.addWidget(self.lbl_status)

        edit_layout.addStretch()
        left_layout.addWidget(edit_group, stretch=3)
        
        web_group = QGroupBox("Navigateur Google Intégré")
        web_layout = QVBoxLayout(web_group)
        
        self.web_view = QWebEngineView()
        self.web_view.setHtml("<h3 style='font-family:sans-serif; color:#7f8c8d; text-align:center; margin-top:20%;'>Sélectionnez un élément pour charger sa recherche Google</h3>")
        web_layout.addWidget(self.web_view)
        
        main_splitter.addWidget(left_container)
        main_splitter.addWidget(web_group)
        main_splitter.setSizes([650, 550])

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Ouvrir le fichier JSON", "", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.full_data = json.load(f)

            self.list_widget.clear()
            count = 0

            for dataset_key, elements in self.full_data.items():
                if isinstance(elements, list):
                    for idx, item in enumerate(elements):
                        if item.get("status") == "not_found_on_gbif":
                            count += 1
                            list_item = QListWidgetItem(f"[{item.get('scientificName')}]")
                            list_item.setData(Qt.UserRole, {"dataset_key": dataset_key, "item_index": idx})
                            self.list_widget.addItem(list_item)

            if count > 0:
                QMessageBox.information(self, "Succès", f"{count} éléments à corriger trouvés !")
                self.btn_save.setEnabled(True)
                self.list_widget.setCurrentRow(0)
            else:
                QMessageBox.information(self, "Information", "Aucun élément avec le statut 'not_found_on_gbif' n'a été trouvé.")
                self.btn_save.setEnabled(False)

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de lire le fichier :\n{e}")

    def on_item_select(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            self.btn_validate.setEnabled(False)
            self.btn_add_species.setEnabled(False)
            self.clear_validated_layout()
            return

        list_item = selected_items[0]
        meta_data = list_item.data(Qt.UserRole)
        dataset_key = meta_data["dataset_key"]
        item_index = meta_data["item_index"]
        
        item = self.full_data[dataset_key][item_index]

        self.current_original_name = item.get("scientificName", "")

        if self.current_original_name:
            query_string = f'scientific name "{self.current_original_name}"'
            encoded_query = urllib.parse.quote(query_string)
            ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            self.web_view.setUrl(QUrl(ddg_url))
        else:
            self.web_view.setHtml("<p>Pas de nom scientifique valide pour la recherche.</p>")

        self.lbl_pndb_title.setText("Chargement des métadonnées PNDB...")
        self.txt_pndb_description.setHtml("<i>Veuillez patienter...</i>")
        QApplication.processEvents()
        
        title, description = fetch_pndb_metadata(dataset_key)
        self.lbl_pndb_title.setText(title)
        self.txt_pndb_description.setHtml(f"<div style='line-height: 1.6;'>{description}</div>")

        self.refresh_validated_context_widget(dataset_key)

        self.entry_scientific_name.setText(self.current_original_name)
        self.update_status_labels(item)
        self.btn_validate.setEnabled(True)
        self.btn_add_species.setEnabled(True)

    def clear_validated_layout(self):
        while self.scroll_validated_layout.count():
            child = self.scroll_validated_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def refresh_validated_context_widget(self, dataset_key):
        self.clear_validated_layout()
        all_elements = self.full_data.get(dataset_key, [])
        has_validated = False
        
        for idx, el in enumerate(all_elements):
            if el.get("status") == "validated":
                has_validated = True
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(4, 2, 4, 2)
                
                lbl_text = QLabel(f"• <b>{el.get('scientificName')}</b> (<i>{el.get('gbif_canonicalName')}</i>)")
                lbl_text.setStyleSheet("color: #27AE60; font-size: 11px;")
                row_layout.addWidget(lbl_text, stretch=1)
                
                btn_invalidate = QPushButton("❌ Invalider")
                btn_invalidate.setFixedWidth(85)
                btn_invalidate.setStyleSheet("background-color: #E74C3C; color: white; font-size: 10px; font-weight: bold; padding: 2px;")
                btn_invalidate.clicked.connect(lambda checked=False, dk=dataset_key, i=idx: self.invalidate_species(dk, i))
                
                row_layout.addWidget(btn_invalidate)
                self.scroll_validated_layout.addWidget(row_widget)
                
        if not has_validated:
            no_data_lbl = QLabel("<i>Aucune autre espèce n'est encore validée pour ce dataset.</i>")
            no_data_lbl.setStyleSheet("color: #7F8C8D; padding: 5px;")
            self.scroll_validated_layout.addWidget(no_data_lbl)
            
        self.scroll_validated_layout.addStretch()

    def invalidate_species(self, dataset_key, item_index):
        species_name = self.full_data[dataset_key][item_index].get("scientificName", "Inconnue")
        
        reply = QMessageBox.question(
            self, 
            "Confirmer l'invalidation", 
            f"Voulez-vous vraiment invalider l'espèce '{species_name}' ?\n"
            "Elle sera réinitialisée et ajoutée à votre liste d'éléments à corriger à gauche.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return

        self.full_data[dataset_key][item_index]["gbif_canonicalName"] = None
        self.full_data[dataset_key][item_index]["taxonID"] = None
        self.full_data[dataset_key][item_index]["status"] = "not_found_on_gbif"
        
        new_list_item = QListWidgetItem(f"[{species_name}]")
        new_list_item.setData(Qt.UserRole, {"dataset_key": dataset_key, "item_index": item_index})
        self.list_widget.addItem(new_list_item)
        
        self.btn_save.setEnabled(True)
        self.refresh_validated_context_widget(dataset_key)

    def update_status_labels(self, item):
        self.lbl_canonical.setText(f"gbif_canonicalName : {item.get('gbif_canonicalName')}")
        self.lbl_taxon_id.setText(f"taxonID : {item.get('taxonID')}")
        
        status = item.get("status")
        self.lbl_status.setText(f"status : {status}")
        if status == "validated":
            self.lbl_status.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.lbl_status.setStyleSheet("font-weight: bold; color: red;")

    def validate_item(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        new_name = self.entry_scientific_name.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Attention", "Le champ Scientific Name ne peut pas être vide.")
            return

        list_item = selected_items[0]
        meta_data = list_item.data(Qt.UserRole)
        dataset_key = meta_data["dataset_key"]
        item_index = meta_data["item_index"]

        result = validate_with_gbif_v2(new_name)
        self.full_data[dataset_key][item_index]["scientificName"] = new_name

        if result:
            self.full_data[dataset_key][item_index]["gbif_canonicalName"] = result["canonicalName"]
            self.full_data[dataset_key][item_index]["taxonID"] = f"https://www.gbif.org/species/{result['taxonKey']}"
            self.full_data[dataset_key][item_index]["status"] = "validated"
        else:
            self.full_data[dataset_key][item_index]["gbif_canonicalName"] = None
            self.full_data[dataset_key][item_index]["taxonID"] = None
            self.full_data[dataset_key][item_index]["status"] = "not_found_on_gbif"
            QMessageBox.warning(self, "Échec", "Aucune correspondance trouvée sur GBIF pour ce nom scientifique.")

        updated_item = self.full_data[dataset_key][item_index]
        self.update_status_labels(updated_item)
        
        prefix = "[VALIDÉ] " if updated_item["status"] == "validated" else ""
        list_item.setText(f"{prefix}[{new_name}]")
        
        self.refresh_validated_context_widget(dataset_key)

    def add_new_species(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        list_item = selected_items[0]
        meta_data = list_item.data(Qt.UserRole)
        dataset_key = meta_data["dataset_key"]

        new_name, ok = QInputDialog.getText(
            self, 
            "Ajouter une espèce", 
            f"Entrez le Scientific Name à ajouter au dataset :\n{dataset_key[:70]}..."
        )
        
        if ok and new_name.strip():
            name_stripped = new_name.strip()
            result = validate_with_gbif_v2(name_stripped)
            
            new_entry = {
                "scientificName": name_stripped,
                "gbif_canonicalName": result["canonicalName"] if result else None,
                "taxonID": f"https://www.gbif.org/species/{result['taxonKey']}" if result else None,
                "status": "validated" if result else "not_found_on_gbif"
            }
            
            if dataset_key not in self.full_data or not isinstance(self.full_data[dataset_key], list):
                self.full_data[dataset_key] = []
            
            self.full_data[dataset_key].append(new_entry)
            
            if not result:
                new_item_index = len(self.full_data[dataset_key]) - 1
                added_list_item = QListWidgetItem(f"[{name_stripped}]")
                added_list_item.setData(Qt.UserRole, {"dataset_key": dataset_key, "item_index": new_item_index})
                self.list_widget.addItem(added_list_item)
                QMessageBox.warning(self, "Ajouté", "Espèce ajoutée, mais non trouvée sur GBIF (status: 'not_found_on_gbif').")
            
            self.refresh_validated_context_widget(dataset_key)

    def save_file(self):
        if not self.full_data:
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le fichier JSON", "", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.full_data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Succès", f"Fichier sauvegardé avec succès !\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de sauvegarder le fichier :\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setStyleSheet("""
        QWidget { 
            font-family: 'Helvetica', 'Arial', sans-serif; 
            font-size: 14px; 
        }
        QTextBrowser {
            line-height: 160%;
        }
    """)
    
    window = DataCurationApp()
    window.show()
    sys.exit(app.exec())