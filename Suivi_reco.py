"""
Point d'entrée de compatibilité pour Streamlit Community Cloud.

L'application principale a été renommée. Ce fichier conserve l'ancien chemin
de démarrage (Suivi_reco.py) afin que le déploiement Streamlit existant
continue de fonctionner sans changer ses paramètres.
"""
from pathlib import Path
import runpy

APP_PATH = Path(__file__).resolve().with_name(
    "Suivi_reco_V4_rapport_direction_DEXA_avec_graphiques_delais.py"
)

if not APP_PATH.is_file():
    raise FileNotFoundError(
        f"Fichier principal introuvable : {APP_PATH.name}. "
        "Vérifie que le script V4 est bien présent à la racine du dépôt."
    )

runpy.run_path(str(APP_PATH), run_name="__main__")
