import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as io
from plotly.subplots import make_subplots
from datetime import datetime
import os
import re
import unicodedata
from io import BytesIO

# Streamlit Page Config
st.set_page_config(
    page_title="Suivi DEXA — Intelligence managériale",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cartographie DR -> Secteurs
MAPPING_DR_SECTEUR = {
    "DRANE": ["Plateau", "Cocody", "Palmeraie", "Angré"],
    "DRAS": ["Marcory", "Koumassi", "Vridy", "Zone 4"],
    "DRYOP": ["Yop", "Annaneraie", "Niangon", "Wassakara"],
    "DRABO": ["Dokui", "Biabou", "Colatier", "N'dotré"]
}

LISTE_GF = ["GF0", "GF1", "GF2", "GF3"]

# Cibles officielles de délai de facturation : GF0 mensuel, GF1-GF3 trimestriels.
CIBLES_DELAIS_JOURS = {"GF0": 5.0, "GF1": 30.0, "GF2": 30.0, "GF3": 30.0}

LISTE_COLLABORATEURS = [
    "Gokon Fabrice",
    "Taper Yasmine",
    "Konan Yao",
    "Kodjo Anick",
    "Gnahoua Kader"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_SUIVI_FILE = os.path.join(BASE_DIR, "data_suivi_recodification.csv")
DATA_SITES_FILE = os.path.join(BASE_DIR, "data_referentiel_sites.csv")
DATA_DELAIS_FILE = os.path.join(BASE_DIR, "data_delais_facturation.csv")


def save_persistent_data():
    """Sauvegarde automatiquement les DataFrames dans des fichiers CSV locaux."""
    if "df_sites" in st.session_state:
        st.session_state.df_sites.to_csv(DATA_SITES_FILE, index=False, encoding="utf-8")
    if "df_suivi" in st.session_state:
        st.session_state.df_suivi.to_csv(DATA_SUIVI_FILE, index=False, encoding="utf-8")
    if "df_delais" in st.session_state:
        st.session_state.df_delais.to_csv(DATA_DELAIS_FILE, index=False, encoding="utf-8")


if "df_sites" not in st.session_state:
    # Chargement depuis le disque si le fichier existe
    if os.path.exists(DATA_SITES_FILE):
        try:
            st.session_state.df_sites = pd.read_csv(DATA_SITES_FILE, encoding="utf-8")
        except Exception:
            pass

    if "df_sites" not in st.session_state or st.session_state.df_sites.empty:
        # Référentiel des stocks par (Site, GF)
        records = []
        for dr, secteurs in MAPPING_DR_SECTEUR.items():
            for sec in secteurs:
                site_name = f"{dr}_{sec}"
                for gf in LISTE_GF:
                    records.append({
                        "DR": dr,
                        "Secteur": sec,
                        "Site": site_name,
                        "GF": gf,
                        "Stock_Initial": 100  # Valeur par défaut initiale
                    })
        st.session_state.df_sites = pd.DataFrame(records)

if "df_suivi" not in st.session_state:
    # Chargement depuis le disque si le fichier existe
    if os.path.exists(DATA_SUIVI_FILE):
        try:
            st.session_state.df_suivi = pd.read_csv(DATA_SUIVI_FILE, encoding="utf-8")
        except Exception:
            pass

    if "df_suivi" not in st.session_state:
        # Dataframe de la production réalisée
        st.session_state.df_suivi = pd.DataFrame(columns=[
            "Date", "Semaine", "Collaborateur", "DR", "Secteur", "Site", "GF", "Nb_Realise"
        ])

# Historique indépendant des délais de facturation
if "df_delais" not in st.session_state:
    if os.path.exists(DATA_DELAIS_FILE):
        try:
            st.session_state.df_delais = pd.read_csv(DATA_DELAIS_FILE, encoding="utf-8")
        except Exception:
            st.session_state.df_delais = pd.DataFrame()
    else:
        st.session_state.df_delais = pd.DataFrame()


# Fonctions de préparation des données de délais
def normalize_column_name(value):
    """Normalise un nom de colonne pour faciliter sa reconnaissance."""
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


DELAY_ALIASES = {
    "DR": ["dr", "direction_regionale", "direction", "region"],
    "Secteur": ["secteur", "agence", "site", "nom_agence", "centre"],
    "GF": ["gf", "groupe_facturation", "groupe_de_facturation", "cycle_gf"],
    "Annee": ["annee", "an", "year", "exercice"],
    "Periode": ["periode", "period", "mois", "date", "date_cycle", "cycle", "mois_cycle"],
    "Delai_Jours": ["delai_jours", "delai_facturation", "delai_moyen", "moyenne_delai", "delai", "jours", "nb_jours", "duree_facturation"]
}

MOIS_FR = {
    "janvier": 1, "janv": 1, "jan": 1, "fevrier": 2, "fevr": 2, "fev": 2,
    "mars": 3, "avril": 4, "avr": 4, "mai": 5, "juin": 6, "juillet": 7,
    "juil": 7, "aout": 8, "septembre": 9, "sept": 9, "octobre": 10,
    "oct": 10, "novembre": 11, "nov": 11, "decembre": 12, "dec": 12
}


def guess_source_column(columns, target):
    normalized = {col: normalize_column_name(col) for col in columns}
    aliases = DELAY_ALIASES[target]
    for alias in aliases:
        for original, clean in normalized.items():
            if clean == alias:
                return original
    for alias in aliases:
        for original, clean in normalized.items():
            if alias in clean:
                return original
    return None


def normalize_dexa_dr(value):
    """Convertit les libellés historiques vers les codes DR de l'application."""
    key = normalize_column_name(value)
    mapping = {
        "drane": "DRANE",
        "dras": "DRAS",
        "yopougon": "DRYOP",
        "dryop": "DRYOP",
        "abobo": "DRABO",
        "drabo": "DRABO",
    }
    return mapping.get(key, str(value).strip().upper())


def normalize_dexa_sector(value):
    """Harmonise les libellés des agences présents dans le classeur historique."""
    key = normalize_column_name(value)
    mapping = {
        "plateau": "Plateau",
        "palmeraie": "Palmeraie",
        "cocody": "Cocody",
        "angre": "Angré",
        "zone_4": "Zone 4",
        "marcory": "Marcory",
        "vridi": "Vridi",
        "koumassi": "Koumassi",
        "yopougon": "Yop",
        "yop": "Yop",
        "niangon": "Niangon",
        "ananeraie": "Ananeraie",
        "anneraie": "Ananeraie",
        "wassakara": "Wassakara",
        "dokui_131": "Dokui",
        "dokui": "Dokui",
        "biabou_176": "Biabou",
        "biabou": "Biabou",
        "colatier_140": "Colatier",
        "colatier": "Colatier",
        "n_dotre_162": "N'dotré",
        "n_dotre": "N'dotré",
    }
    return mapping.get(key, str(value).strip().title())


def detect_dexa_year_sheets(file_bytes):
    """Retourne les feuilles annuelles présentant la structure DEXA attendue.

    Le nom de la feuille doit contenir une année à quatre chiffres (20xx).
    Le format attendu conserve les mois sur la ligne 2 et les codes GF sur la ligne 3.
    Cette détection ne dépend pas d'une liste d'années figée : 2027, 2028, etc. sont acceptées.
    """
    excel_file = pd.ExcelFile(BytesIO(file_bytes))
    month_keys = set(MOIS_FR.keys())
    valid_gf = {"gf0", "gf1", "gf2", "gf3"}
    detected = []
    for sheet_name in excel_file.sheet_names:
        if not re.search(r"20\d{2}", str(sheet_name)):
            continue
        try:
            probe = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name, header=None, nrows=4, dtype=object)
            if probe.shape[0] < 3 or probe.shape[1] < 4:
                continue
            month_headers = probe.iloc[1, 2:].ffill()
            gf_headers = probe.iloc[2, 2:]
            has_month = any(normalize_column_name(v) in month_keys for v in month_headers if pd.notna(v))
            has_gf = any(normalize_column_name(v) in valid_gf for v in gf_headers if pd.notna(v))
            if has_month and has_gf:
                detected.append(sheet_name)
        except Exception:
            continue
    return detected


def prepare_dexa_wide_workbook(file_bytes):
    """Lit toutes les feuilles annuelles DEXA (2024, 2025, 2026, 2027, etc.)."""
    excel_file = pd.ExcelFile(BytesIO(file_bytes))
    records = []
    # Les mois complets et leurs abréviations usuelles sont acceptés.
    month_order = {normalize_column_name(name): num for name, num in MOIS_FR.items()}

    valid_year_sheets = set(detect_dexa_year_sheets(file_bytes))
    for sheet_name in excel_file.sheet_names:
        year_match = re.search(r"20\d{2}", str(sheet_name))
        if not year_match or sheet_name not in valid_year_sheets:
            continue
        year = int(year_match.group(0))
        raw = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name, header=None, dtype=object)
        if raw.shape[0] < 4 or raw.shape[1] < 4:
            continue

        # Dans ce classeur : ligne 2 = mois, ligne 3 = GF.
        # GF0 est mensuel ; GF1, GF2 et GF3 suivent un cycle trimestriel.
        # Les colonnes « Ecart » sont ignorées et les deux périodicités
        # sont conservées pour une analyse séparée dans le tableau de bord.
        period_headers = raw.iloc[1, 2:].ffill()
        gf_headers = raw.iloc[2, 2:]
        current_dr = None

        for row_idx in range(3, len(raw)):
            dr_cell = raw.iat[row_idx, 0] if raw.shape[1] > 0 else None
            sector_cell = raw.iat[row_idx, 1] if raw.shape[1] > 1 else None

            if pd.notna(dr_cell) and str(dr_cell).strip():
                current_dr = normalize_dexa_dr(dr_cell)

            if pd.isna(sector_cell) or not str(sector_cell).strip():
                continue
            sector_text = str(sector_cell).strip()
            sector_key = normalize_column_name(sector_text)

            # Ne pas réimporter les lignes de synthèse régionales / DEXA :
            # elles seraient comptées une deuxième fois avec les lignes agence.
            if "moyenne" in sector_key or sector_key.startswith("dexa"):
                continue
            if current_dr is None:
                continue

            sector = normalize_dexa_sector(sector_text)
            for col_idx in range(2, raw.shape[1]):
                gf_value = gf_headers.iloc[col_idx - 2] if col_idx - 2 < len(gf_headers) else None
                period_value = period_headers.iloc[col_idx - 2] if col_idx - 2 < len(period_headers) else None
                gf_key = normalize_column_name(gf_value) if pd.notna(gf_value) else ""
                if gf_key not in {"gf0", "gf1", "gf2", "gf3"}:
                    # Les colonnes « Ecart » de 2026 sont conservées dans le fichier
                    # d'origine mais ne sont pas interprétées comme des délais.
                    continue
                month_key = normalize_column_name(period_value) if pd.notna(period_value) else ""
                if month_key not in month_order:
                    continue

                raw_value = raw.iat[row_idx, col_idx]
                value = pd.to_numeric(
                    pd.Series([str(raw_value).replace(" ", "").replace(",", ".") if pd.notna(raw_value) else None]),
                    errors="coerce"
                ).iloc[0]
                # Les N/A, cellules vides et erreurs Excel (#DIV/0!) sont exclus.
                if pd.isna(value) or value < 0:
                    continue

                month_num = month_order[month_key]
                month_label = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"][month_num - 1]
                gf_code = gf_key.upper()
                records.append({
                    "Annee": year,
                    "Periode": month_label,
                    "Periode_Affichage": f"{month_label} {year}",
                    "Ordre_Periode": month_num,
                    "DR": current_dr,
                    "Secteur": sector,
                    "GF": gf_code,
                    # GF0 est un cycle mensuel ; GF1, GF2 et GF3 sont trimestriels.
                    "Periodicite": "Mensuelle" if gf_code == "GF0" else "Trimestrielle",
                    "Delai_Jours": float(value),
                    "Source_Feuille": str(sheet_name),
                })

    out = pd.DataFrame(records)
    if out.empty:
        raise ValueError("Aucune donnée exploitable détectée dans les feuilles annuelles du classeur DEXA.")

    # Une observation unique par année, période, DR, agence et GF est attendue.
    # On retire uniquement les doublons exacts éventuels, sans agréger de valeurs.
    out = out.drop_duplicates(subset=["Annee", "Periode", "DR", "Secteur", "GF", "Delai_Jours"])
    return out.sort_values(["Annee", "Ordre_Periode", "DR", "Secteur", "GF"]).reset_index(drop=True)


def prepare_delay_data(raw_df, mapping):
    """Convertit les colonnes du fichier importé vers un schéma stable."""
    if raw_df is None or raw_df.empty:
        raise ValueError("Le fichier sélectionné ne contient aucune ligne.")
    if not mapping.get("Periode") or not mapping.get("Delai_Jours"):
        raise ValueError("Les colonnes Période et Délai (jours) sont obligatoires.")

    out = pd.DataFrame(index=raw_df.index)
    for field in ["DR", "Secteur", "GF"]:
        source = mapping.get(field)
        out[field] = raw_df[source] if source else "Non renseigné"
    out["Periode_Source"] = raw_df[mapping["Periode"]]
    out["Delai_Jours"] = raw_df[mapping["Delai_Jours"]].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
    out["Delai_Jours"] = pd.to_numeric(out["Delai_Jours"], errors="coerce")

    # L'année peut être fournie séparément ou déduite d'une période reconnue comme date.
    date_values = pd.to_datetime(out["Periode_Source"], errors="coerce", dayfirst=True)
    year_source = mapping.get("Annee")
    if year_source:
        out["Annee"] = pd.to_numeric(raw_df[year_source], errors="coerce")
    else:
        out["Annee"] = date_values.dt.year

    # Normalisation de la période : mois français si la source contient une date complète.
    period_labels = out["Periode_Source"].astype(str).str.strip()
    month_names = {1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
                   7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"}
    date_mask = date_values.notna()
    period_labels.loc[date_mask] = date_values.loc[date_mask].dt.month.map(month_names)
    out["Periode"] = period_labels

    for field in ["DR", "Secteur", "GF"]:
        out[field] = out[field].fillna("Non renseigné").astype(str).str.strip()
    out["DR"] = out["DR"].str.upper()
    out["GF"] = out["GF"].str.upper()
    out["Annee"] = pd.to_numeric(out["Annee"], errors="coerce")

    # Ordre chronologique, utile même lorsque les mois sont écrits en français.
    def period_month(value):
        key = normalize_column_name(value)
        for month, num in MOIS_FR.items():
            if key == month or key.startswith(month):
                return num
        match = re.search(r"(20\d{2})[\-_ /](\d{1,2})", key)
        if match:
            return int(match.group(2))
        return 99

    out["Ordre_Periode"] = out["Periode"].map(period_month)
    out = out.dropna(subset=["Annee", "Delai_Jours"])
    out = out[out["Delai_Jours"] >= 0]
    out["Annee"] = out["Annee"].astype(int)
    out["Periode_Affichage"] = out["Periode"].astype(str) + " " + out["Annee"].astype(str)
    out["Periodicite"] = np.where(out["GF"].eq("GF0"), "Mensuelle", "Trimestrielle")
    out = out[["Annee", "Periode", "Periode_Affichage", "Ordre_Periode", "DR", "Secteur", "GF", "Periodicite", "Delai_Jours"]]
    if out.empty:
        raise ValueError("Aucune ligne exploitable : vérifie les colonnes Année, Période et Délai.")
    return out.reset_index(drop=True)


def build_managerial_diagnostics(current_data, history_data, current_year):
    """Diagnostic d'agence/GF ; N-1 est comparé sur les mêmes périodes uniquement."""
    required = {"Annee", "Periode", "DR", "Secteur", "GF", "Delai_Jours"}
    if current_data is None or current_data.empty or not required.issubset(current_data.columns):
        return pd.DataFrame()
    cur = current_data.copy()
    hist = history_data.copy() if history_data is not None else pd.DataFrame()
    month_order = {"janvier": 1, "janv": 1, "jan": 1, "fevrier": 2, "fevr": 2, "fev": 2,
                   "mars": 3, "avril": 4, "avr": 4, "mai": 5, "juin": 6, "juillet": 7,
                   "juil": 7, "aout": 8, "septembre": 9, "sept": 9, "octobre": 10,
                   "oct": 10, "novembre": 11, "nov": 11, "decembre": 12, "dec": 12}
    for frame in (cur, hist):
        if frame.empty:
            continue
        frame["Annee"] = pd.to_numeric(frame["Annee"], errors="coerce")
        frame["Delai_Jours"] = pd.to_numeric(frame["Delai_Jours"], errors="coerce")
        frame["GF"] = frame["GF"].astype(str).str.upper().str.strip()
        if "Ordre_Periode" not in frame.columns:
            frame["Ordre_Periode"] = np.nan
        frame["Ordre_Periode"] = pd.to_numeric(frame["Ordre_Periode"], errors="coerce")
        missing = frame["Ordre_Periode"].isna()
        if missing.any():
            frame.loc[missing, "Ordre_Periode"] = frame.loc[missing, "Periode"].map(
                lambda v: next((n for label, n in month_order.items()
                                if normalize_column_name(v) == label or normalize_column_name(v).startswith(label)), np.nan))
        frame.dropna(subset=["Annee", "Delai_Jours"], inplace=True)
    cur = cur[cur["Annee"].eq(int(current_year))].copy()
    if cur.empty:
        return pd.DataFrame()
    cur["Cible_Jours"] = cur["GF"].map(CIBLES_DELAIS_JOURS)
    cur = cur.dropna(subset=["Cible_Jours", "Delai_Jours"])
    keys = ["GF", "DR", "Secteur"]
    if cur.empty:
        return pd.DataFrame()
    agency = cur.groupby(keys, dropna=False).agg(
        Delai_Moyen=("Delai_Jours", "mean"), Delai_Median=("Delai_Jours", "median"),
        Delai_Min=("Delai_Jours", "min"), Delai_Max=("Delai_Jours", "max"),
        Nb_Observations=("Delai_Jours", "size")).reset_index()
    cur["Hors_Cible"] = cur["Delai_Jours"] > cur["Cible_Jours"]
    exceed = cur.groupby(keys, dropna=False).agg(
        Nb_Periodes_Hors_Cible=("Hors_Cible", "sum"),
        Taux_Periodes_Hors_Cible=("Hors_Cible", "mean")).reset_index()
    agency = agency.merge(exceed, on=keys, how="left")
    agency["Cible_Jours"] = agency["GF"].map(CIBLES_DELAIS_JOURS)
    agency["Ecart_Cible"] = agency["Delai_Moyen"] - agency["Cible_Jours"]
    agency["Taux_Periodes_Hors_Cible"] *= 100

    # Comparaison annuelle à périodes identiques (ex. janvier 2026 vs janvier 2025).
    if not hist.empty:
        prev = hist[hist["Annee"].eq(int(current_year) - 1) & hist["GF"].isin(cur["GF"].unique())].copy()
        if not prev.empty:
            cur_p = cur.dropna(subset=["Ordre_Periode"]).groupby(keys + ["Ordre_Periode"])["Delai_Jours"].mean().reset_index(name="Moyenne_Courante_Comparable")
            prev_p = prev.dropna(subset=["Ordre_Periode"]).groupby(keys + ["Ordre_Periode"])["Delai_Jours"].mean().reset_index(name="Moyenne_N1_Comparable")
            matched = cur_p.merge(prev_p, on=keys + ["Ordre_Periode"], how="inner")
            if not matched.empty:
                comparison = matched.groupby(keys).agg(
                    Delai_Courant_Comparable=("Moyenne_Courante_Comparable", "mean"),
                    Delai_N1_Comparable=("Moyenne_N1_Comparable", "mean"),
                    Nb_Periodes_Comparees=("Ordre_Periode", "nunique")).reset_index()
                agency = agency.merge(comparison, on=keys, how="left")
    for col in ["Delai_Courant_Comparable", "Delai_N1_Comparable", "Nb_Periodes_Comparees"]:
        if col not in agency.columns:
            agency[col] = np.nan
    agency["Variation_vs_N1"] = agency["Delai_Courant_Comparable"] - agency["Delai_N1_Comparable"]

    def trend(v):
        if pd.isna(v): return "Comparaison N-1 indisponible"
        if v < -0.5: return "Amélioration vs N-1"
        if v > 0.5: return "Dégradation vs N-1"
        return "Stable vs N-1"
    agency["Tendance"] = agency["Variation_vs_N1"].map(trend)

    def diagnostic(r):
        if r.Ecart_Cible > 0 and r.Nb_Observations == 1: return "Dépassement à confirmer"
        if r.Ecart_Cible > 0 and r.Taux_Periodes_Hors_Cible >= 50: return "Dépassement récurrent"
        if r.Ecart_Cible > 0: return "Moyenne au-dessus de la cible"
        if r.Nb_Periodes_Hors_Cible > 0: return "Moyenne conforme, cycle(s) à surveiller"
        return "Cible tenue"
    def priority(r):
        if r.Ecart_Cible > 0 and r.Taux_Periodes_Hors_Cible >= 50: return "1 — Priorité haute"
        if r.Ecart_Cible > 0: return "2 — Action corrective"
        if r.Tendance == "Dégradation vs N-1" or r.Nb_Periodes_Hors_Cible > 0: return "3 — Vigilance"
        return "4 — Maintien"
    def action(r):
        if r.Ecart_Cible > 0 and r.Nb_Observations == 1:
            return f"Vérifier le délai observé par rapport à la cible de {r.Cible_Jours:.0f} jours et contrôler le prochain cycle avant de conclure à une récurrence."
        if r.Ecart_Cible > 0 and r.Taux_Periodes_Hors_Cible >= 50:
            return "Plan correctif prioritaire : analyser les étapes relevé, transmission et émission ; identifier un responsable et suivre chaque période jusqu'au retour sous cible."
        if r.Ecart_Cible > 0:
            return "Examiner les périodes hors cible, rechercher la cause du retard et engager une correction ciblée avec le responsable du secteur."
        if r.Tendance == "Dégradation vs N-1":
            return "La moyenne reste sous la cible mais se dégrade : rechercher la cause de la hausse et renforcer le contrôle au prochain cycle."
        if r.Nb_Periodes_Hors_Cible > 0:
            return "Maintenir la moyenne sous la cible et analyser les cycles isolés en dépassement pour éviter leur répétition."
        if r.Tendance == "Amélioration vs N-1":
            return "Consolider les pratiques associées à l'amélioration et les partager avec les secteurs du même GF."
        return "Maintenir les pratiques qui permettent de tenir la cible et partager les méthodes efficaces."
    agency["Diagnostic"] = agency.apply(diagnostic, axis=1)
    agency["Niveau_Action"] = agency.apply(priority, axis=1)
    agency["Action_Conseillée"] = agency.apply(action, axis=1)
    agency["Rang"] = agency.groupby("GF")["Delai_Moyen"].rank(method="min", ascending=True).astype(int)
    agency["Agence"] = agency["DR"].astype(str) + " — " + agency["Secteur"].astype(str)
    return agency.sort_values(["GF", "Niveau_Action", "Ecart_Cible", "Taux_Periodes_Hors_Cible"],
                              ascending=[True, True, False, False]).reset_index(drop=True)


# -----------------------------------------------------------------------------
# Préparation du rapport mensuel DEXA
# -----------------------------------------------------------------------------
def report_sector_key(value):
    """Clé commune pour faire correspondre les libellés secteur entre fichiers."""
    key = normalize_column_name(value)
    aliases = {
        "vridy": "vridi",
        "vridi": "vridi",
        "annaneraie": "ananeraie",
        "anneraie": "ananeraie",
        "yopougon": "yop",
        "yop": "yop",
        "n_dotre_162": "n_dotre",
    }
    return aliases.get(key, key)



def parse_report_date_series(values):
    """Parse les dates ISO et françaises sans inverser les dates ISO."""
    raw = values.astype(str).str.strip()
    parsed_iso = pd.to_datetime(raw, format="%Y-%m-%d", errors="coerce")
    parsed_dmy = pd.to_datetime(raw, format="%d/%m/%Y", errors="coerce")
    parsed = parsed_iso.combine_first(parsed_dmy)
    remaining = parsed.isna()
    if remaining.any():
        parsed.loc[remaining] = pd.to_datetime(raw.loc[remaining], errors="coerce")
    return parsed

def report_status_from_progress(rate, stock):
    if pd.isna(stock) or stock <= 0:
        return "Stock initial non renseigné"
    if pd.isna(rate) or rate <= 0:
        return "Non démarré"
    if rate >= 100:
        return "Stock initial traité"
    return "En cours"


def parse_report_week(value):
    """Lit la semaine saisie dans la colonne Semaine du formulaire.

    Exemples acceptés : S48, 48, S 48, 2026-S48. Cette valeur est la
    référence hebdomadaire du tableau de bord ; elle ne doit pas être
    recalculée à partir de la date calendrier de saisie.
    """
    if pd.isna(value):
        return (np.nan, "", np.nan)
    raw = str(value).strip().upper()
    if not raw:
        return (np.nan, "", np.nan)
    year_match = re.search(r"(20\d{2})", raw)
    week_match = re.search(r"(?:S|SEM(?:AINE)?)[ _-]*0*(\d{1,2})\s*$", raw)
    if not week_match:
        week_match = re.search(r"(\d{1,2})\s*$", raw)
    if not week_match:
        return (np.nan, "", np.nan)
    week_number = int(week_match.group(1))
    if not 1 <= week_number <= 53:
        return (np.nan, "", np.nan)
    year_number = int(year_match.group(1)) if year_match else np.nan
    label = f"{int(year_number)}-S{week_number:02d}" if pd.notna(year_number) else f"S{week_number:02d}"
    return (week_number, label, year_number)


def report_week_sort_key(label, report_year):
    """Ordre chronologique des libellés de semaine issus de la colonne Semaine."""
    year_match = re.search(r"(20\d{2})", str(label))
    week_match = re.search(r"S(\d{1,2})$", str(label).upper())
    year = int(year_match.group(1)) if year_match else int(report_year)
    week = int(week_match.group(1)) if week_match else 0
    return (year, week, str(label))


def report_period_number(value):
    """Convertit un libellé de période en numéro de mois."""
    if pd.isna(value):
        return np.nan
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.notna(numeric) and 1 <= numeric <= 12:
        return int(numeric)
    key = normalize_column_name(value)
    for label, number in MOIS_FR.items():
        if key == label or key.startswith(label):
            return number
    match = re.search(r"(?:20\d{2})[_\-/ ](\d{1,2})", key)
    if match:
        n = int(match.group(1))
        return n if 1 <= n <= 12 else np.nan
    return np.nan


def _aggregate_report_progress(frame, keys):
    if frame.empty:
        return pd.DataFrame()
    if keys:
        out = frame.groupby(keys, dropna=False).agg(
            Stock_Initial=("Stock_Initial", "sum"),
            Nb_Realise=("Nb_Realise", "sum"),
            Reste_A_Faire=("Reste_A_Faire", "sum"),
            Depassement=("Depassement", "sum"),
            Nb_Saisies=("Nb_Saisies", "sum"),
        ).reset_index()
    else:
        out = pd.DataFrame([{
            "Stock_Initial": frame["Stock_Initial"].sum(),
            "Nb_Realise": frame["Nb_Realise"].sum(),
            "Reste_A_Faire": frame["Reste_A_Faire"].sum(),
            "Depassement": frame["Depassement"].sum(),
            "Nb_Saisies": frame["Nb_Saisies"].sum(),
        }])
    out["Taux_Avancement"] = np.where(
        out["Stock_Initial"] > 0,
        out["Nb_Realise"] / out["Stock_Initial"] * 100,
        np.nan,
    )
    out["Statut_Recodification"] = out.apply(
        lambda r: report_status_from_progress(r["Taux_Avancement"], r["Stock_Initial"]), axis=1
    )
    return out


def build_monthly_report_data(df_sites, df_suivi, df_delais, cutoff_date):
    """Construit les tables du rapport à une date d'arrêté donnée.

    Les indicateurs de recodification sont reconstitués à partir des saisies datées
    jusqu'à la date d'arrêté. L'analyse des délais compare l'année d'arrêté à N-1
    sur les mêmes mois disponibles. Cette comparaison est descriptive, non causale.
    """
    cutoff = pd.Timestamp(cutoff_date).normalize()
    report_year = int(cutoff.year)
    report_month = int(cutoff.month)

    # ----- Stocks initiaux configurés -----
    stock = df_sites.copy() if isinstance(df_sites, pd.DataFrame) else pd.DataFrame()
    for col in ["DR", "Secteur", "GF", "Stock_Initial"]:
        if col not in stock.columns:
            stock[col] = np.nan if col == "Stock_Initial" else ""
    stock["DR"] = stock["DR"].astype(str).str.strip().str.upper()
    stock["GF"] = stock["GF"].astype(str).str.strip().str.upper()
    stock["Secteur"] = stock["Secteur"].astype(str).str.strip()
    stock["Secteur_Cle"] = stock["Secteur"].map(report_sector_key)
    stock["Stock_Initial"] = pd.to_numeric(stock["Stock_Initial"], errors="coerce").fillna(0)
    stock = stock[stock["DR"].ne("") & stock["GF"].isin(LISTE_GF)].copy()
    stock_grouped = stock.groupby(["DR", "Secteur_Cle", "GF"], dropna=False).agg(
        Stock_Initial=("Stock_Initial", "sum"),
        Secteur_Stock=("Secteur", "first"),
    ).reset_index()

    # ----- Saisies de recodification arrêtées à la date sélectionnée -----
    suivi_all = df_suivi.copy() if isinstance(df_suivi, pd.DataFrame) else pd.DataFrame()
    for col in ["Date", "Semaine", "DR", "Secteur", "GF", "Nb_Realise"]:
        if col not in suivi_all.columns:
            suivi_all[col] = np.nan if col == "Nb_Realise" else ""
    suivi_all["Date_Saisie"] = parse_report_date_series(suivi_all["Date"])
    suivi_all["Nb_Realise"] = pd.to_numeric(suivi_all["Nb_Realise"], errors="coerce").fillna(0)
    suivi_all["DR"] = suivi_all["DR"].astype(str).str.strip().str.upper()
    suivi_all["GF"] = suivi_all["GF"].astype(str).str.strip().str.upper()
    suivi_all["Secteur"] = suivi_all["Secteur"].astype(str).str.strip()
    suivi_all["Secteur_Cle"] = suivi_all["Secteur"].map(report_sector_key)
    missing_dates_count = int(suivi_all["Date_Saisie"].isna().sum())
    missing_dates_volume = float(suivi_all.loc[suivi_all["Date_Saisie"].isna(), "Nb_Realise"].sum())
    suivi = suivi_all[
        suivi_all["Date_Saisie"].notna()
        & suivi_all["Date_Saisie"].le(cutoff)
        & suivi_all["DR"].ne("")
        & suivi_all["GF"].isin(LISTE_GF)
    ].copy()

    # La colonne « Semaine » est la référence hebdomadaire officielle du tableau
    # « Récapitulatif des Saisies par Collaborateur et par Semaine ».
    # La date de saisie reste utilisée pour l'arrêté et la date de dernière saisie,
    # mais elle ne sert plus à recalculer le numéro de semaine.
    if not suivi.empty:
        week_info = suivi["Semaine"].apply(parse_report_week)
        suivi[["Numero_Semaine_Saisie", "Semaine_Label", "Annee_Semaine_Saisie"]] = pd.DataFrame(
            week_info.tolist(), index=suivi.index
        )
        suivi["Numero_Semaine_Saisie"] = pd.to_numeric(suivi["Numero_Semaine_Saisie"], errors="coerce")
        suivi["Annee_Semaine_Saisie"] = pd.to_numeric(suivi["Annee_Semaine_Saisie"], errors="coerce")
        prod_grouped = suivi.groupby(["DR", "Secteur_Cle", "GF"], dropna=False).agg(
            Nb_Realise=("Nb_Realise", "sum"),
            Nb_Saisies=("Nb_Realise", "size"),
            Derniere_Saisie=("Date_Saisie", "max"),
            Secteur_Saisie=("Secteur", "first"),
        ).reset_index()
        valid_week_rows = suivi[suivi["Semaine_Label"].astype(str).str.len().gt(0)].copy()
        if not valid_week_rows.empty:
            last_week = (valid_week_rows.sort_values(
                ["Annee_Semaine_Saisie", "Numero_Semaine_Saisie", "Date_Saisie"],
                na_position="first"
            ).groupby(["DR", "Secteur_Cle", "GF"], as_index=False).tail(1)
             [["DR", "Secteur_Cle", "GF", "Semaine_Label"]]
             .rename(columns={"Semaine_Label": "Semaine_Derniere_Saisie"}))
            prod_grouped = prod_grouped.merge(last_week, on=["DR", "Secteur_Cle", "GF"], how="left")
        else:
            prod_grouped["Semaine_Derniere_Saisie"] = ""
    else:
        prod_grouped = pd.DataFrame(columns=[
            "DR", "Secteur_Cle", "GF", "Nb_Realise", "Nb_Saisies", "Derniere_Saisie",
            "Secteur_Saisie", "Semaine_Derniere_Saisie"
        ])

    progress = stock_grouped.merge(prod_grouped, on=["DR", "Secteur_Cle", "GF"], how="outer")
    progress["Secteur"] = progress.get("Secteur_Stock", pd.Series(index=progress.index, dtype=object)).combine_first(
        progress.get("Secteur_Saisie", pd.Series(index=progress.index, dtype=object))
    )
    progress["Stock_Initial"] = pd.to_numeric(progress["Stock_Initial"], errors="coerce").fillna(0)
    progress["Nb_Realise"] = pd.to_numeric(progress["Nb_Realise"], errors="coerce").fillna(0)
    progress["Nb_Saisies"] = pd.to_numeric(progress["Nb_Saisies"], errors="coerce").fillna(0).astype(int)
    raw_remaining = progress["Stock_Initial"] - progress["Nb_Realise"]
    progress["Reste_A_Faire"] = raw_remaining.clip(lower=0)
    progress["Depassement"] = (-raw_remaining).clip(lower=0)
    progress["Taux_Avancement"] = np.where(
        progress["Stock_Initial"] > 0,
        progress["Nb_Realise"] / progress["Stock_Initial"] * 100,
        np.nan,
    )
    progress["Statut_Recodification"] = progress.apply(
        lambda r: report_status_from_progress(r["Taux_Avancement"], r["Stock_Initial"]), axis=1
    )
    progress["Derniere_Saisie"] = pd.to_datetime(progress["Derniere_Saisie"], errors="coerce")
    progress = progress[[
        "DR", "Secteur", "Secteur_Cle", "GF", "Stock_Initial", "Nb_Realise", "Reste_A_Faire",
        "Depassement", "Taux_Avancement", "Statut_Recodification", "Nb_Saisies",
        "Derniere_Saisie", "Semaine_Derniere_Saisie"
    ]].sort_values(["DR", "Secteur", "GF"]).reset_index(drop=True)

    # Deux périmètres de lecture sont volontairement distingués :
    # - DEXA et synthèse DEXA par GF : totalité des quatre DR, y compris les
    #   secteurs/GF où aucune action n'a encore été saisie.
    # - Détail DR/GF et secteur/GF : uniquement les combinaisons avec au moins
    #   une saisie réelle (Nb_Saisies > 0).
    progress_active = progress[progress["Nb_Saisies"].gt(0)].copy()
    dr_progress = _aggregate_report_progress(progress, ["DR"])
    # Le total DEXA est recomposé à partir des lignes des DR, puis son taux est
    # recalculé sur les totaux (réalisé DEXA / stock initial DEXA), jamais comme
    # une moyenne simple des taux régionaux.
    global_progress = _aggregate_report_progress(dr_progress, [])
    # La synthèse DEXA par GF agrège également toutes les DR, y compris les GF
    # sans action. Le détail DR/GF reste, lui, limité aux actions réellement saisies.
    gf_progress = _aggregate_report_progress(progress, ["GF"])
    dr_gf_progress = _aggregate_report_progress(progress_active, ["DR", "GF"])

    # Contrôle arithmétique : le DEXA doit être égal à la somme des 4 DR et à
    # la somme des quatre GF sur les principaux volumes de recodification.
    global_row_check = global_progress.iloc[0] if not global_progress.empty else pd.Series(dtype=float)
    reconcile_fields = ["Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Depassement", "Nb_Saisies"]
    dr_sums = {field: float(pd.to_numeric(dr_progress.get(field, pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) for field in reconcile_fields}
    gf_sums = {field: float(pd.to_numeric(gf_progress.get(field, pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) for field in reconcile_fields}
    reconciliation = {
        "par_dr": {field: bool(np.isclose(float(global_row_check.get(field, 0) or 0), dr_sums[field])) for field in reconcile_fields},
        "par_gf": {field: bool(np.isclose(float(global_row_check.get(field, 0) or 0), gf_sums[field])) for field in reconcile_fields},
        "ecarts_dr": {field: float(global_row_check.get(field, 0) or 0) - dr_sums[field] for field in reconcile_fields},
        "ecarts_gf": {field: float(global_row_check.get(field, 0) or 0) - gf_sums[field] for field in reconcile_fields},
    }

    # Activité hebdomadaire : reprendre exactement la colonne Semaine du dashboard.
    # Les lignes datées après l'arrêté sont exclues ; une ligne sans date peut être
    # conservée si son champ Semaine est renseigné, comme dans la matrice du dashboard.
    weekly_source = suivi_all.copy()
    weekly_source["Date_Saisie"] = parse_report_date_series(weekly_source["Date"])
    weekly_source["Nb_Realise"] = pd.to_numeric(weekly_source["Nb_Realise"], errors="coerce").fillna(0)
    weekly_source["DR"] = weekly_source["DR"].astype(str).str.strip().str.upper()
    weekly_source["GF"] = weekly_source["GF"].astype(str).str.strip().str.upper()
    weekly_source["Secteur"] = weekly_source["Secteur"].astype(str).str.strip()
    weekly_source["Secteur_Cle"] = weekly_source["Secteur"].map(report_sector_key)
    weekly_source = weekly_source[
        (weekly_source["Date_Saisie"].isna() | weekly_source["Date_Saisie"].le(cutoff))
        & weekly_source["DR"].ne("")
        & weekly_source["GF"].isin(LISTE_GF)
    ].copy()
    weekly_info = weekly_source["Semaine"].apply(parse_report_week)
    weekly_source[["Numero_Semaine_Saisie", "Semaine_Label", "Annee_Semaine_Saisie"]] = pd.DataFrame(
        weekly_info.tolist(), index=weekly_source.index
    )
    weekly_source["Numero_Semaine_Saisie"] = pd.to_numeric(weekly_source["Numero_Semaine_Saisie"], errors="coerce")
    weekly_source["Annee_Semaine_Saisie"] = pd.to_numeric(weekly_source["Annee_Semaine_Saisie"], errors="coerce")
    saisies_sans_semaine = int(weekly_source["Semaine_Label"].fillna("").eq("").sum())
    weekly_source = weekly_source[weekly_source["Semaine_Label"].fillna("").ne("")].copy()

    if not weekly_source.empty:
        week_options = weekly_source[["Semaine_Label", "Numero_Semaine_Saisie", "Annee_Semaine_Saisie"]].drop_duplicates()
        week_options["Annee_Ordre"] = week_options["Annee_Semaine_Saisie"].fillna(report_year)
        week_options = week_options.sort_values(["Annee_Ordre", "Numero_Semaine_Saisie", "Semaine_Label"])
        latest_week_labels = week_options["Semaine_Label"].drop_duplicates().tail(5).tolist()
        week_grid = pd.DataFrame({"Semaine_Label": latest_week_labels})
        week_grid["Libelle_Semaine"] = week_grid["Semaine_Label"]
        weekly_rows = weekly_source[weekly_source["Semaine_Label"].isin(latest_week_labels)].copy()
        weekly_totals = weekly_rows.groupby("Semaine_Label").agg(
            Nb_Saisies=("Nb_Realise", "size"),
            Nb_Realise=("Nb_Realise", "sum"),
            Nb_DR=("DR", "nunique"),
            Nb_Secteurs=("Secteur_Cle", "nunique"),
        ).reset_index()
        weekly_dr = weekly_rows.groupby(["Semaine_Label", "DR"]).agg(
            Nb_Saisies=("Nb_Realise", "size"), Nb_Realise=("Nb_Realise", "sum")
        ).reset_index()
        weekly_dr_gf = weekly_rows.groupby(["Semaine_Label", "DR", "GF"]).agg(
            Nb_Saisies=("Nb_Realise", "size"), Nb_Realise=("Nb_Realise", "sum")
        ).reset_index()
        weekly_totals = week_grid.merge(weekly_totals, on="Semaine_Label", how="left")
        for numeric_col in ["Nb_Saisies", "Nb_Realise", "Nb_DR", "Nb_Secteurs"]:
            weekly_totals[numeric_col] = pd.to_numeric(weekly_totals[numeric_col], errors="coerce").fillna(0)
        weekly_totals["Nb_Saisies"] = weekly_totals["Nb_Saisies"].astype(int)
        weekly_totals[["Nb_DR", "Nb_Secteurs"]] = weekly_totals[["Nb_DR", "Nb_Secteurs"]].astype(int)
        weekly_dr = weekly_dr.merge(week_grid, on="Semaine_Label", how="left")
        weekly_dr_gf = weekly_dr_gf.merge(week_grid, on="Semaine_Label", how="left")
        weekly_totals = weekly_totals[["Semaine_Label", "Libelle_Semaine", "Nb_Saisies", "Nb_Realise", "Nb_DR", "Nb_Secteurs"]]
    else:
        weekly_totals = pd.DataFrame(columns=["Semaine_Label", "Libelle_Semaine", "Nb_Saisies", "Nb_Realise", "Nb_DR", "Nb_Secteurs"])
        weekly_dr = pd.DataFrame(columns=["Semaine_Label", "DR", "Nb_Saisies", "Nb_Realise", "Libelle_Semaine"])
        weekly_dr_gf = pd.DataFrame(columns=["Semaine_Label", "DR", "GF", "Nb_Saisies", "Nb_Realise", "Libelle_Semaine"])

    # Date et semaine de dernière activité par DR pour le diagnostic d'impact.
    if not suivi.empty:
        dr_activity = suivi.groupby("DR").agg(
            Date_Derniere_Saisie_DR=("Date_Saisie", "max"),
            Nb_Saisies_DR=("Nb_Realise", "size"),
            Volume_Recodifie_DR=("Nb_Realise", "sum"),
        ).reset_index()
        dr_week_source = suivi[suivi["Semaine_Label"].fillna("").ne("")].copy()
        if not dr_week_source.empty:
            dr_week_source = dr_week_source.sort_values(
                ["Annee_Semaine_Saisie", "Numero_Semaine_Saisie", "Date_Saisie"], na_position="first"
            )
            latest_dr_week = (dr_week_source.groupby("DR", as_index=False).tail(1)
                              [["DR", "Semaine_Label"]]
                              .rename(columns={"Semaine_Label": "Semaine_Derniere_Saisie_DR"}))
            dr_activity = dr_activity.merge(latest_dr_week, on="DR", how="left")
        else:
            dr_activity["Semaine_Derniere_Saisie_DR"] = ""
    else:
        dr_activity = pd.DataFrame(columns=["DR", "Date_Derniere_Saisie_DR", "Nb_Saisies_DR", "Volume_Recodifie_DR", "Semaine_Derniere_Saisie_DR"])
    if not dr_progress.empty:
        dr_progress = dr_progress.merge(dr_activity, on="DR", how="left")

    # ----- Délais : exercice du rapport et N-1 sur périodes identiques -----
    delay = df_delais.copy() if isinstance(df_delais, pd.DataFrame) else pd.DataFrame()
    delay_current = pd.DataFrame()
    delay_sector_impact = pd.DataFrame()
    delay_dr_impact = pd.DataFrame()
    delay_dexa_impact = pd.DataFrame()
    delay_evolution = pd.DataFrame()
    if not delay.empty:
        for col in ["Annee", "Periode", "DR", "Secteur", "GF", "Delai_Jours"]:
            if col not in delay.columns:
                delay[col] = np.nan if col in {"Annee", "Delai_Jours"} else ""
        delay["Annee"] = pd.to_numeric(delay["Annee"], errors="coerce")
        delay["Delai_Jours"] = pd.to_numeric(delay["Delai_Jours"], errors="coerce")
        ordre_periode_source = delay["Ordre_Periode"] if "Ordre_Periode" in delay.columns else pd.Series(np.nan, index=delay.index)
        delay["Ordre_Periode"] = pd.to_numeric(ordre_periode_source, errors="coerce").astype("float64")
        missing_order = delay["Ordre_Periode"].isna()
        if missing_order.any():
            delay.loc[missing_order, "Ordre_Periode"] = delay.loc[missing_order, "Periode"].map(report_period_number).astype("float64")
        delay["DR"] = delay["DR"].map(normalize_dexa_dr)
        delay["Secteur"] = delay["Secteur"].astype(str).str.strip()
        delay["Secteur_Cle"] = delay["Secteur"].map(report_sector_key)
        delay["GF"] = delay["GF"].astype(str).str.upper().str.strip()
        delay = delay.dropna(subset=["Annee", "Ordre_Periode", "Delai_Jours"])
        delay = delay[delay["GF"].isin(LISTE_GF) & delay["Delai_Jours"].ge(0)].copy()
        delay["Annee"] = delay["Annee"].astype(int)
        delay["Ordre_Periode"] = delay["Ordre_Periode"].astype(int)
        delay_current = delay[
            delay["Annee"].eq(report_year) & delay["Ordre_Periode"].le(report_month)
        ].copy()
        if not delay_current.empty:
            delay_current["Cible_Jours"] = delay_current["GF"].map(CIBLES_DELAIS_JOURS)
            delay_current["Ecart_Cible"] = delay_current["Delai_Jours"] - delay_current["Cible_Jours"]
            delay_current["Statut_Cible"] = np.where(delay_current["Ecart_Cible"] > 0, "Hors cible", "Conforme")
        delay_previous = delay[
            delay["Annee"].eq(report_year - 1) & delay["Ordre_Periode"].le(report_month)
        ].copy()
        delay_evolution = delay_current.copy()
        if not delay_current.empty:
            delay_sector_current = delay_current.groupby(["DR", "Secteur_Cle", "GF"], dropna=False).agg(
                Delai_Moyen_Courant=("Delai_Jours", "mean"), Nb_Periodes_Courantes=("Delai_Jours", "size"),
                Secteur_Delai=("Secteur", "first")
            ).reset_index()
        else:
            delay_sector_current = pd.DataFrame(columns=["DR", "Secteur_Cle", "GF", "Delai_Moyen_Courant", "Nb_Periodes_Courantes", "Secteur_Delai"])

        match_keys = ["DR", "Secteur_Cle", "GF", "Ordre_Periode"]
        if not delay_current.empty and not delay_previous.empty:
            cur_period = delay_current.groupby(match_keys, dropna=False)["Delai_Jours"].mean().reset_index(name="Delai_Courant_Comparable")
            prev_period = delay_previous.groupby(match_keys, dropna=False)["Delai_Jours"].mean().reset_index(name="Delai_N1_Comparable")
            matched = cur_period.merge(prev_period, on=match_keys, how="inner")
        else:
            matched = pd.DataFrame(columns=match_keys + ["Delai_Courant_Comparable", "Delai_N1_Comparable"])
        if not matched.empty:
            trend_sector = matched.groupby(["DR", "Secteur_Cle", "GF"], dropna=False).agg(
                Delai_Courant_Comparable=("Delai_Courant_Comparable", "mean"),
                Delai_N1_Comparable=("Delai_N1_Comparable", "mean"),
                Nb_Periodes_Comparees=("Ordre_Periode", "nunique"),
            ).reset_index()
            trend_sector["Variation_vs_N1"] = trend_sector["Delai_Courant_Comparable"] - trend_sector["Delai_N1_Comparable"]
        else:
            trend_sector = pd.DataFrame(columns=["DR", "Secteur_Cle", "GF", "Delai_Courant_Comparable", "Delai_N1_Comparable", "Nb_Periodes_Comparees", "Variation_vs_N1"])

        delay_sector_impact = delay_sector_current.merge(trend_sector, on=["DR", "Secteur_Cle", "GF"], how="left")
        delay_sector_impact = delay_sector_impact.merge(
            progress[["DR", "Secteur_Cle", "GF", "Secteur", "Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Taux_Avancement", "Statut_Recodification", "Nb_Saisies", "Derniere_Saisie", "Semaine_Derniere_Saisie"]],
            on=["DR", "Secteur_Cle", "GF"], how="left", suffixes=("_Delai", "_Recodif")
        )
        # Dans le rapprochement opérationnel, ne conserver que les secteurs/GF
        # sur lesquels une action de recodification a effectivement été saisie.
        if "Nb_Saisies" in delay_sector_impact.columns:
            delay_sector_impact["Nb_Saisies"] = pd.to_numeric(delay_sector_impact["Nb_Saisies"], errors="coerce").fillna(0)
            delay_sector_impact = delay_sector_impact[delay_sector_impact["Nb_Saisies"].gt(0)].copy()
        if "Secteur" not in delay_sector_impact.columns:
            delay_sector_impact["Secteur"] = delay_sector_impact.get("Secteur_Delai", "")
        else:
            delay_sector_impact["Secteur"] = delay_sector_impact["Secteur"].combine_first(delay_sector_impact.get("Secteur_Delai"))
        delay_sector_impact["Cible_Jours"] = delay_sector_impact["GF"].map(CIBLES_DELAIS_JOURS)
        delay_sector_impact["Ecart_Cible"] = delay_sector_impact["Delai_Moyen_Courant"] - delay_sector_impact["Cible_Jours"]

        # Le calcul des délais DR/DEXA doit porter sur toutes les observations
        # de délais, pas uniquement sur les secteurs affichés dans le tableau
        # de rapprochement des actions de recodification.
        if not delay_sector_current.empty:
            dr_delay_current = delay_sector_current.groupby(["DR", "GF"]).agg(
                Delai_Moyen_Courant=("Delai_Moyen_Courant", "mean"),
                Nb_Secteurs_Avec_Delai=("Secteur_Cle", "nunique"),
            ).reset_index()
        else:
            dr_delay_current = pd.DataFrame(columns=["DR", "GF", "Delai_Moyen_Courant", "Nb_Secteurs_Avec_Delai"])
        if not matched.empty:
            trend_dr = matched.groupby(["DR", "GF"]).agg(
                Delai_Courant_Comparable=("Delai_Courant_Comparable", "mean"),
                Delai_N1_Comparable=("Delai_N1_Comparable", "mean"),
                Nb_Periodes_Comparees=("Ordre_Periode", "nunique"),
            ).reset_index()
            trend_dr["Variation_vs_N1"] = trend_dr["Delai_Courant_Comparable"] - trend_dr["Delai_N1_Comparable"]
        else:
            trend_dr = pd.DataFrame(columns=["DR", "GF", "Delai_Courant_Comparable", "Delai_N1_Comparable", "Nb_Periodes_Comparees", "Variation_vs_N1"])
        delay_dr_impact = dr_gf_progress.merge(dr_delay_current, on=["DR", "GF"], how="outer").merge(
            trend_dr, on=["DR", "GF"], how="left"
        )
        # Le tableau de rapprochement DR/GF est un tableau des actions : les
        # résultats de délai sans saisie de recodification ne doivent pas y figurer.
        if "Nb_Saisies" in delay_dr_impact.columns:
            delay_dr_impact["Nb_Saisies"] = pd.to_numeric(delay_dr_impact["Nb_Saisies"], errors="coerce").fillna(0)
            delay_dr_impact = delay_dr_impact[delay_dr_impact["Nb_Saisies"].gt(0)].copy()
        if not suivi.empty:
            activity_dr_gf = suivi.groupby(["DR", "GF"]).agg(
                Date_Derniere_Saisie_DR_GF=("Date_Saisie", "max"),
                Nb_Saisies_DR_GF=("Nb_Realise", "size"),
                Volume_Recodifie_DR_GF=("Nb_Realise", "sum"),
            ).reset_index()
            dr_gf_week_source = suivi[suivi["Semaine_Label"].fillna("").ne("")].copy()
            dr_gf_week_source = dr_gf_week_source.sort_values(
                ["Annee_Semaine_Saisie", "Numero_Semaine_Saisie", "Date_Saisie"], na_position="first"
            )
            latest_dr_gf_week = (dr_gf_week_source.groupby(["DR", "GF"], as_index=False).tail(1)
                                 [["DR", "GF", "Semaine_Label"]]
                                 .rename(columns={"Semaine_Label": "Semaine_Derniere_Saisie_DR_GF"}))
            activity_dr_gf = activity_dr_gf.merge(latest_dr_gf_week, on=["DR", "GF"], how="left")
            delay_dr_impact = delay_dr_impact.merge(activity_dr_gf, on=["DR", "GF"], how="left")
        else:
            delay_dr_impact["Date_Derniere_Saisie_DR_GF"] = pd.NaT
            delay_dr_impact["Nb_Saisies_DR_GF"] = 0
            delay_dr_impact["Volume_Recodifie_DR_GF"] = 0
            delay_dr_impact["Semaine_Derniere_Saisie_DR_GF"] = ""
        delay_dr_impact["Cible_Jours"] = delay_dr_impact["GF"].map(CIBLES_DELAIS_JOURS)
        delay_dr_impact["Ecart_Cible"] = delay_dr_impact["Delai_Moyen_Courant"] - delay_dr_impact["Cible_Jours"]
        # dr_progress contient déjà la dernière date et la dernière semaine de saisie par DR.
        if not dr_progress.empty:
            dr_status = dr_progress[["DR", "Taux_Avancement", "Statut_Recodification", "Date_Derniere_Saisie_DR", "Semaine_Derniere_Saisie_DR"]].rename(
                columns={"Taux_Avancement": "Taux_Avancement_DR", "Statut_Recodification": "Statut_DR"}
            )
            delay_dr_impact = delay_dr_impact.merge(dr_status, on="DR", how="left")

        # Synthèse des délais DEXA : elle doit rester calculée sur toutes les DR
        # disposant de délais, et non sur le seul sous-ensemble DR/GF avec actions.
        # On conserve la pondération égale entre DR utilisée par le suivi historique.
        dexa_delay_base = dr_delay_current.merge(trend_dr, on=["DR", "GF"], how="left")
        if not dexa_delay_base.empty:
            delay_dexa_impact = dexa_delay_base.groupby("GF", dropna=False).agg(
                Delai_Moyen_DEXA=("Delai_Moyen_Courant", "mean"),
                Delai_DEXA_Comparable=("Delai_Courant_Comparable", "mean"),
                Delai_N1_DEXA_Comparable=("Delai_N1_Comparable", "mean"),
                Variation_vs_N1=("Variation_vs_N1", "mean"),
                Nb_DR_Avec_Delai=("DR", "nunique"),
            ).reset_index()
            delay_dexa_impact = delay_dexa_impact.merge(
                gf_progress.rename(columns={
                    "Stock_Initial": "Stock_Initial_DEXA_GF",
                    "Nb_Realise": "Nb_Realise_DEXA_GF",
                    "Reste_A_Faire": "Reste_A_Faire_DEXA_GF",
                    "Taux_Avancement": "Taux_Avancement_DEXA_GF",
                    "Statut_Recodification": "Statut_Recodification_DEXA_GF",
                })[["GF", "Stock_Initial_DEXA_GF", "Nb_Realise_DEXA_GF", "Reste_A_Faire_DEXA_GF", "Taux_Avancement_DEXA_GF", "Statut_Recodification_DEXA_GF"]],
                on="GF", how="left"
            )
            delay_dexa_impact["Cible_Jours"] = delay_dexa_impact["GF"].map(CIBLES_DELAIS_JOURS)
            delay_dexa_impact["Ecart_Cible"] = delay_dexa_impact["Delai_Moyen_DEXA"] - delay_dexa_impact["Cible_Jours"]

        def impact_reading(row):
            variation = row.get("Variation_vs_N1", np.nan)
            status = row.get("Statut_Recodification", row.get("Statut_DR", "Non renseigné"))
            if pd.isna(row.get("Delai_Moyen_Courant", np.nan)):
                return "Aucun délai renseigné sur l'exercice et les périodes retenues."
            if pd.isna(variation):
                return "Délai disponible, mais comparaison N-1 sur périodes identiques indisponible."
            if variation < -0.5 and status == "Stock initial traité":
                return "Baisse du délai constatée sur une DR dont le stock initial est traité : évolution favorable concomitante."
            if variation < -0.5 and status == "En cours":
                return "Baisse du délai constatée pendant que les saisies de recodification se poursuivent."
            if variation > 0.5 and status in {"Stock initial traité", "En cours"}:
                return "Le délai augmente malgré l'avancement des saisies : analyser le décalage temporel et les autres causes opérationnelles."
            if variation > 0.5 and status == "Non démarré":
                return "Le délai se dégrade sans saisie de recodification enregistrée sur ce GF : examiner la cause et programmer le traitement du stock."
            if variation < -0.5 and status == "Non démarré":
                return "Le délai baisse sans saisie de recodification enregistrée sur ce GF : cette amélioration ne peut pas être reliée au chantier sur la base des données disponibles."
            if abs(variation) <= 0.5:
                return "Délai globalement stable par rapport aux mêmes périodes de N-1."
            return "Évolution à interpréter avec le niveau d'avancement et les dates effectives de traitement."
        if not delay_dr_impact.empty:
            delay_dr_impact["Lecture_Impact"] = delay_dr_impact.apply(impact_reading, axis=1)
        if not delay_sector_impact.empty:
            delay_sector_impact["Lecture_Impact"] = delay_sector_impact.apply(impact_reading, axis=1)

    # Harmonise les tables et fournit un résumé de l'arrêté.
    global_progress.insert(0, "Perimetre", "DEXA")
    global_progress.insert(1, "Date_Arrete", cutoff.date())
    if dr_progress.empty:
        dr_progress = pd.DataFrame(columns=["DR", "Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Depassement", "Nb_Saisies", "Taux_Avancement", "Statut_Recodification"])
    if dr_gf_progress.empty:
        dr_gf_progress = pd.DataFrame(columns=["DR", "GF", "Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Depassement", "Nb_Saisies", "Taux_Avancement", "Statut_Recodification"])
    if gf_progress.empty:
        gf_progress = pd.DataFrame(columns=["GF", "Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Depassement", "Nb_Saisies", "Taux_Avancement", "Statut_Recodification"])

    progress_presentation = progress_active.drop(columns=["Secteur_Cle"], errors="ignore").copy()
    delay_sector_presentation = delay_sector_impact.drop(columns=["Secteur_Cle"], errors="ignore").copy()
    delay_current_presentation = delay_current.drop(columns=["Secteur_Cle"], errors="ignore").copy()

    return {
        "date_arrete": cutoff,
        "annee": report_year,
        "mois": report_month,
        "global": global_progress,
        "dr": dr_progress,
        "gf": gf_progress,
        "reconciliation": reconciliation,
        "dr_gf": dr_gf_progress,
        "secteur_gf": progress_presentation,
        "weekly": weekly_totals,
        "weekly_dr": weekly_dr,
        "weekly_dr_gf": weekly_dr_gf,
        "delay_current": delay_current_presentation,
        "delay_previous": delay_previous.drop(columns=["Secteur_Cle"], errors="ignore") if "delay_previous" in locals() else pd.DataFrame(),
        "delay_sector_impact": delay_sector_presentation,
        "delay_dr_impact": delay_dr_impact,
        "delay_dexa_impact": delay_dexa_impact,
        "delay_evolution": delay_evolution,
        "saisies_sans_date": missing_dates_count,
        "volume_saisies_sans_date": missing_dates_volume,
        "saisies_sans_semaine": saisies_sans_semaine,
        "nb_saisies_arrete": int(len(suivi)),
        "volume_saisies_arrete": float(suivi["Nb_Realise"].sum()) if not suivi.empty else 0,
    }


def build_monthly_report_excel(payload):
    """Produit un classeur multi-onglets annexé au rapport mensuel."""
    buffer = BytesIO()
    sheets = {
        "Synthese_DEXA": payload["global"],
        "Avancement_DR": payload["dr"],
        "Avancement_GF": payload["gf"],
        "Avancement_DR_GF": payload["dr_gf"],
        "Avancement_Secteur_GF": payload["secteur_gf"],
        "Saisies_5_semaines": payload["weekly"],
        "Saisies_Par_DR": payload["weekly_dr"],
        "Saisies_Par_DR_GF": payload["weekly_dr_gf"],
        "Impact_DEXA_GF": payload["delay_dexa_impact"],
        "Impact_DR_GF": payload["delay_dr_impact"],
        "Impact_Secteur_GF": payload["delay_sector_impact"],
        "Delais_Annee": payload["delay_current"],
    }
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            (frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()).to_excel(
                writer, sheet_name=name[:31], index=False
            )
    buffer.seek(0)
    return buffer.getvalue()


def _report_table_html(frame, max_rows=None):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return "<p class='muted'>Aucune donnée disponible sur le périmètre sélectionné.</p>"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    for col in shown.columns:
        if pd.api.types.is_datetime64_any_dtype(shown[col]):
            shown[col] = shown[col].dt.strftime("%d/%m/%Y").fillna("—")
    return shown.to_html(index=False, border=0, classes="data", na_rep="—", escape=True)



def build_report_delay_figures(payload):
    """Construit les graphiques d'évolution des délais pour l'écran et le rapport exporté.

    La courbe DEXA reprend la méthode du rapport : moyenne des moyennes régionales,
    afin que chaque DR ait le même poids quel que soit le nombre de secteurs renseignés.
    La courbe régionale détaille ensuite chaque DR par GF pour l'année de l'arrêté.
    """
    current = payload.get("delay_current", pd.DataFrame())
    previous = payload.get("delay_previous", pd.DataFrame())
    current_year = int(payload.get("annee", datetime.now().year))

    def prepare_dexa(frame, year_label):
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return pd.DataFrame()
        needed = {"DR", "GF", "Periode", "Ordre_Periode", "Delai_Jours"}
        if not needed.issubset(frame.columns):
            return pd.DataFrame()
        work = frame.copy()
        work["DR"] = work["DR"].astype(str).str.strip().str.upper()
        work["GF"] = work["GF"].astype(str).str.strip().str.upper()
        work["Delai_Jours"] = pd.to_numeric(work["Delai_Jours"], errors="coerce")
        work["Ordre_Periode"] = pd.to_numeric(work["Ordre_Periode"], errors="coerce")
        work = work.dropna(subset=["Delai_Jours", "Ordre_Periode"])
        work = work[work["GF"].isin(LISTE_GF) & work["DR"].ne("")]
        if work.empty:
            return pd.DataFrame()
        # Première moyenne au niveau DR/période, puis moyenne égale entre DR.
        regional = work.groupby(["DR", "GF", "Ordre_Periode", "Periode"], dropna=False).agg(
            Delai_DR=("Delai_Jours", "mean")
        ).reset_index()
        dexa = regional.groupby(["GF", "Ordre_Periode", "Periode"], dropna=False).agg(
            Delai_DEXA=("Delai_DR", "mean"), Nb_DR=("DR", "nunique")
        ).reset_index()
        dexa["Annee_Comparaison"] = str(year_label)
        return dexa

    dexa_parts = [prepare_dexa(previous, current_year - 1), prepare_dexa(current, current_year)]
    dexa_parts = [part for part in dexa_parts if not part.empty]
    dexa_data = pd.concat(dexa_parts, ignore_index=True) if dexa_parts else pd.DataFrame()

    fig_dexa = None
    if not dexa_data.empty:
        fig_dexa = make_subplots(
            rows=2, cols=2,
            subplot_titles=[f"{gf} — cible {CIBLES_DELAIS_JOURS[gf]:g} jours" for gf in LISTE_GF],
            horizontal_spacing=0.12, vertical_spacing=0.18,
        )
        years = [str(current_year - 1), str(current_year)]
        for idx, gf in enumerate(LISTE_GF):
            row, col = idx // 2 + 1, idx % 2 + 1
            panel = dexa_data[dexa_data["GF"].eq(gf)]
            if panel.empty:
                fig_dexa.add_annotation(
                    text="Aucune donnée pour ce GF", x=0.5, y=0.5,
                    xref=f"x{idx + 1 if idx else ''} domain", yref=f"y{idx + 1 if idx else ''} domain",
                    showarrow=False, font={"color": "#6b7280"}, row=row, col=col
                )
                continue
            for yr in years:
                series = panel[panel["Annee_Comparaison"].eq(yr)].sort_values("Ordre_Periode")
                if series.empty:
                    continue
                is_current = yr == str(current_year)
                fig_dexa.add_trace(
                    io.Scatter(
                        x=series["Periode"], y=series["Delai_DEXA"],
                        mode="lines+markers", name=yr, legendgroup=yr,
                        showlegend=(idx == 0),
                        line={"dash": "solid" if is_current else "dash", "width": 3 if is_current else 2},
                        customdata=series[["Nb_DR"]],
                        hovertemplate=("Période : %{x}<br>Délai DEXA : %{y:.1f} jours"
                                       "<br>DR renseignées : %{customdata[0]}<extra>%{fullData.name}</extra>"),
                    ), row=row, col=col
                )
            fig_dexa.add_hline(
                y=CIBLES_DELAIS_JOURS[gf], line_dash="dot", line_color="#d64545",
                line_width=1.5, opacity=0.8, row=row, col=col,
            )
            period_order = (panel[["Periode", "Ordre_Periode"]].drop_duplicates()
                            .sort_values("Ordre_Periode")["Periode"].tolist())
            fig_dexa.update_xaxes(categoryorder="array", categoryarray=period_order, tickangle=-25, row=row, col=col)
            fig_dexa.update_yaxes(title_text="Jours", rangemode="tozero", row=row, col=col)
        fig_dexa.update_layout(
            title=f"Évolution du délai moyen DEXA par GF — {current_year} comparé à {current_year - 1}",
            height=760, template="plotly_white", hovermode="x unified",
            legend_title_text="Exercice", margin={"l": 45, "r": 25, "t": 95, "b": 65},
        )

    fig_dr = None
    if isinstance(current, pd.DataFrame) and not current.empty:
        needed = {"DR", "GF", "Periode", "Ordre_Periode", "Delai_Jours"}
        if needed.issubset(current.columns):
            regional_data = current.copy()
            regional_data["DR"] = regional_data["DR"].astype(str).str.strip().str.upper()
            regional_data["GF"] = regional_data["GF"].astype(str).str.strip().str.upper()
            regional_data["Delai_Jours"] = pd.to_numeric(regional_data["Delai_Jours"], errors="coerce")
            regional_data["Ordre_Periode"] = pd.to_numeric(regional_data["Ordre_Periode"], errors="coerce")
            regional_data = regional_data.dropna(subset=["Delai_Jours", "Ordre_Periode"])
            regional_data = regional_data[regional_data["GF"].isin(LISTE_GF) & regional_data["DR"].ne("")]
            if not regional_data.empty:
                regional_data = regional_data.groupby(
                    ["DR", "GF", "Periode", "Ordre_Periode"], dropna=False
                )["Delai_Jours"].mean().reset_index()
                fig_dr = make_subplots(
                    rows=2, cols=2,
                    subplot_titles=[f"{gf} — cible {CIBLES_DELAIS_JOURS[gf]:g} jours" for gf in LISTE_GF],
                    horizontal_spacing=0.12, vertical_spacing=0.18,
                )
                dr_names = sorted(regional_data["DR"].unique().tolist())
                for idx, gf in enumerate(LISTE_GF):
                    row, col = idx // 2 + 1, idx % 2 + 1
                    panel = regional_data[regional_data["GF"].eq(gf)]
                    if panel.empty:
                        continue
                    for dr in dr_names:
                        series = panel[panel["DR"].eq(dr)].sort_values("Ordre_Periode")
                        if series.empty:
                            continue
                        fig_dr.add_trace(
                            io.Scatter(
                                x=series["Periode"], y=series["Delai_Jours"],
                                mode="lines+markers", name=dr, legendgroup=dr,
                                showlegend=(idx == 0),
                                hovertemplate="Période : %{x}<br>Délai : %{y:.1f} jours<extra>%{fullData.name}</extra>",
                            ), row=row, col=col
                        )
                    fig_dr.add_hline(
                        y=CIBLES_DELAIS_JOURS[gf], line_dash="dot", line_color="#d64545",
                        line_width=1.5, opacity=0.8, row=row, col=col,
                    )
                    period_order = (panel[["Periode", "Ordre_Periode"]].drop_duplicates()
                                    .sort_values("Ordre_Periode")["Periode"].tolist())
                    fig_dr.update_xaxes(categoryorder="array", categoryarray=period_order, tickangle=-25, row=row, col=col)
                    fig_dr.update_yaxes(title_text="Jours", rangemode="tozero", row=row, col=col)
                fig_dr.update_layout(
                    title=f"Évolution des délais par DR et GF — exercice {current_year}",
                    height=760, template="plotly_white", hovermode="x unified",
                    legend_title_text="Direction régionale", margin={"l": 45, "r": 25, "t": 95, "b": 65},
                )
    return fig_dexa, fig_dr


def _report_delay_charts_html(payload):
    """Rend les figures Plotly dans le rapport HTML autonome (imprimable en PDF)."""
    figures = build_report_delay_figures(payload)
    if not any(fig is not None for fig in figures):
        return "<section><h2>Graphiques d'évolution des délais</h2><p class='muted'>Aucune donnée de délai disponible pour tracer les évolutions.</p></section>"
    blocks = ["<section class='charts-section'><h2>Graphiques d'évolution des délais de facturation</h2>"]
    plotly_loaded = False
    for title, fig in zip(
        ["Évolution DEXA par GF : année de l'arrêté et N-1", "Évolution par DR et GF : année de l'arrêté"],
        figures,
    ):
        if fig is None:
            continue
        blocks.append(f"<h3>{title}</h3>")
        blocks.append(
            fig.to_html(
                full_html=False,
                include_plotlyjs="inline" if not plotly_loaded else False,
                config={"responsive": True, "displaylogo": False},
            )
        )
        plotly_loaded = True
    blocks.append("</section>")
    return "".join(blocks)


def build_monthly_report_html(payload):
    """Rapport HTML imprimable (le navigateur permet de l'enregistrer en PDF)."""
    cutoff = payload["date_arrete"].strftime("%d/%m/%Y")
    global_row = payload["global"].iloc[0] if not payload["global"].empty else {}
    kpis = [
        ("Stock initial", f"{global_row.get('Stock_Initial', 0):,.0f}"),
        ("Recodifié", f"{global_row.get('Nb_Realise', 0):,.0f}"),
        ("Reste à faire", f"{global_row.get('Reste_A_Faire', 0):,.0f}"),
        ("Avancement", f"{global_row.get('Taux_Avancement', 0):.1f} %" if pd.notna(global_row.get("Taux_Avancement", np.nan)) else "—"),
    ]
    kpi_html = "".join(f"<div class='kpi'><span>{label}</span><strong>{value}</strong></div>" for label, value in kpis)
    sections = [
        ("1. Avancement global de la recodification", payload["dr"]),
        ("2. Avancement par GF au niveau DEXA", payload["gf"]),
        ("3. Avancement par DR et GF", payload["dr_gf"]),
        ("4. Avancement détaillé par secteur et GF", payload["secteur_gf"]),
        ("5. Saisies des cinq dernières semaines", payload["weekly"]),
        ("6. Détail hebdomadaire par DR", payload["weekly_dr"]),
        ("7. Détail hebdomadaire par DR et GF", payload["weekly_dr_gf"]),
        ("8. Synthèse de l'évolution des délais DEXA par GF", payload["delay_dexa_impact"]),
        ("9. Concordance recodification / délais par DR et GF", payload["delay_dr_impact"]),
        ("10. Concordance recodification / délais par secteur et GF", payload["delay_sector_impact"]),
    ]
    section_html = "".join(f"<section><h2>{title}</h2>{_report_table_html(frame)}</section>" for title, frame in sections)
    delay_charts_html = _report_delay_charts_html(payload)
    disclaimer = (
        "Lecture d'impact descriptive : la comparaison des délais avec les semaines de saisie indique une évolution "
        "concomitante, mais ne prouve pas à elle seule que la recodification est la cause exclusive de l'évolution. "
        "Une mesure causale nécessiterait notamment les dates individuelles de correction, de relevé et d'émission des factures."
    )
    return f"""<!doctype html><html lang='fr'><head><meta charset='utf-8'>
    <meta name='viewport' content='width=device-width,initial-scale=1'><title>Rapport mensuel DEXA</title>
    <style>
      @page {{ size: A4 landscape; margin: 12mm; }}
      body {{ font-family: Arial, sans-serif; color:#1f2937; margin:24px; }}
      header {{ border-bottom:3px solid #16834a; padding-bottom:14px; margin-bottom:20px; }}
      h1 {{ margin:0 0 6px; color:#14532d; }} h2 {{ color:#14532d; font-size:17px; margin:24px 0 10px; }}
      .muted {{ color:#6b7280; font-size:12px; }} .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:18px 0; }}
      .kpi {{ border:1px solid #d1d5db; border-radius:8px; padding:12px; }} .kpi span {{ display:block; color:#6b7280; font-size:12px; }}
      .kpi strong {{ display:block; font-size:22px; margin-top:6px; }}
      table.data {{ width:100%; border-collapse:collapse; font-size:10px; }}
      table.data th {{ background:#e8f3ec; text-align:left; }} table.data th,table.data td {{ border:1px solid #d1d5db; padding:5px 6px; }}
      tr {{ page-break-inside:avoid; }} section {{ page-break-inside:auto; }}
      .note {{ background:#f3f4f6; padding:12px; border-left:4px solid #6b7280; font-size:11px; margin-top:20px; }}
      .charts-section {{ page-break-before:always; }} .charts-section h3 {{ color:#374151; font-size:14px; margin-top:18px; }}
      .charts-section .plotly-graph-div {{ width:100% !important; }}
      @media print {{ body {{ margin:0; }} h2 {{ page-break-after:avoid; }} }}
    </style></head><body>
      <header><h1>Rapport mensuel de pilotage — DEXA</h1>
      <div class='muted'>Situation arrêtée au {cutoff} • Exercice de délais : {payload['annee']} • Source : données de l'application de suivi</div></header>
      <div class='kpis'>{kpi_html}</div>
      {section_html}
      {delay_charts_html}
      <div class='note'><strong>Précaution d'interprétation :</strong> {disclaimer}<br>
      Saisies sans date exploitable et exclues du calcul à la date d'arrêté : {payload['saisies_sans_date']} ligne(s), soit {payload['volume_saisies_sans_date']:,.0f} élément(s).</div>
    </body></html>"""


# Helper to generate test data
def generate_demo_data():
    records_suivi = []
    weeks = [f"S{i:02d}" for i in range(1, 6)]
    np.random.seed(42)

    for w_idx, week in enumerate(weeks):
        for colab in LISTE_COLLABORATEURS:
            # Random selections
            dr = np.random.choice(list(MAPPING_DR_SECTEUR.keys()))
            sec = np.random.choice(MAPPING_DR_SECTEUR[dr])
            site = f"{dr}_{sec}"
            gf = np.random.choice(LISTE_GF)
            nb = np.random.randint(5, 30)

            records_suivi.append({
                "Date": f"2026-02-0{w_idx + 1}",
                "Semaine": week,
                "Collaborateur": colab,
                "DR": dr,
                "Secteur": sec,
                "Site": site,
                "GF": gf,
                "Nb_Realise": int(nb)
            })

    st.session_state.df_suivi = pd.DataFrame(records_suivi)
    save_persistent_data()


st.title("📌 Suivi de Recodification & Performance de Facturation — DEXA")
st.markdown(
    "Application de suivi de l'avancement hebdo par Direction Régionale, Secteur (Site) et Groupe de Facturation (GF).")

with st.sidebar:
    st.header("⚙️ Actions & Démo")
    if st.button("🔄 Charger des données de démonstration", use_container_width=True):
        generate_demo_data()
        st.success("Données de test chargées avec succès !")
        st.rerun()

    if st.button("🗑️ Réinitialiser toutes les saisies", use_container_width=True):
        st.session_state.df_suivi = pd.DataFrame(columns=[
            "Date", "Semaine", "Collaborateur", "DR", "Secteur", "Site", "GF", "Nb_Realise"
        ])
        save_persistent_data()
        st.warning("Historique de suivi réinitialisé !")
        st.rerun()

    st.divider()
    st.markdown("### ℹ️ Structure du Réseau")
    for dr, secs in MAPPING_DR_SECTEUR.items():
        with st.expander(f"📍 {dr}"):
            for s in secs:
                st.write(f"- `{dr}_{s}` (GF0, GF1, GF2, GF3)")

tab_dash, tab_saisie, tab_stock, tab_data, tab_delais, tab_rapport = st.tabs([
    "📊 Dashboard Recodification",
    "📝 Saisie Production",
    "⚙️ Configuration Stocks Initial",
    "📁 Gestion des Données",
    "⏱️ Suivi des délais de facturation",
    "📑 Rapport mensuel DEXA"
])

with tab_dash:
    st.subheader("📊 Tableau de Bord Synthetique")

    # Validation structures
    df_sites = st.session_state.df_sites.copy()
    df_suivi = st.session_state.df_suivi.copy()

    # Sécurisation des colonnes requises dans df_suivi
    cols_suivi_requises = ["Date", "Semaine", "Collaborateur", "DR", "Secteur", "Site", "GF", "Nb_Realise"]
    for col in cols_suivi_requises:
        if col not in df_suivi.columns:
            df_suivi[col] = 0 if col == "Nb_Realise" else ""

    # Top level filters
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        dr_filter = st.multiselect("Filtrer par DR", options=list(MAPPING_DR_SECTEUR.keys()))
    with col_f2:
        sec_options = [s for dr in (dr_filter if dr_filter else MAPPING_DR_SECTEUR.keys()) for s in
                       MAPPING_DR_SECTEUR[dr]]
        sec_filter = st.multiselect("Filtrer par Secteur", options=sec_options)
    with col_f3:
        gf_filter = st.multiselect("Filtrer par GF", options=LISTE_GF)
    with col_f4:
        colab_filter = st.multiselect("Filtrer par Collaborateur", options=LISTE_COLLABORATEURS)

    # Apply filters
    if dr_filter:
        df_sites = df_sites[df_sites["DR"].isin(dr_filter)]
        if not df_suivi.empty:
            df_suivi = df_suivi[df_suivi["DR"].isin(dr_filter)]
    if sec_filter:
        df_sites = df_sites[df_sites["Secteur"].isin(sec_filter)]
        if not df_suivi.empty:
            df_suivi = df_suivi[df_suivi["Secteur"].isin(sec_filter)]
    if gf_filter:
        df_sites = df_sites[df_sites["GF"].isin(gf_filter)]
        if not df_suivi.empty:
            df_suivi = df_suivi[df_suivi["GF"].isin(gf_filter)]
    if colab_filter and not df_suivi.empty:
        df_suivi = df_suivi[df_suivi["Collaborateur"].isin(colab_filter)]

    # Compute Global KPIs
    total_stock_init = df_sites["Stock_Initial"].sum()
    total_realise = df_suivi["Nb_Realise"].sum() if not df_suivi.empty else 0
    reste_a_faire = max(0, total_stock_init - total_realise)
    taux_avancement = (total_realise / total_stock_init * 100) if total_stock_init > 0 else 0.0

    # Display KPI Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("📌 Stock Initial Total", f"{total_stock_init:,}")
    kpi2.metric("✅ Total Recodifié (Cumul)", f"{total_realise:,}")
    kpi3.metric("⏳ Reste à Faire", f"{reste_a_faire:,}")
    kpi4.metric("📈 Taux d'Avancement", f"{taux_avancement:.1f} %")

    st.divider()

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("#### 📅 Évolution de la Recodification par Semaine")
        if not df_suivi.empty:
            df_weekly = df_suivi.groupby(["Semaine", "DR"])["Nb_Realise"].sum().reset_index()
            fig_week = px.bar(
                df_weekly,
                x="Semaine",
                y="Nb_Realise",
                color="DR",
                barmode="stack",
                title="Saisies Hebdomadaires par DR"
            )
            st.plotly_chart(fig_week, use_container_width=True)
        else:
            st.info("Aucune donnée de saisie enregistrée pour afficher le graphique.")

    with col_chart2:
        st.markdown("#### 👨‍💻 Production par Collaborateur")
        if not df_suivi.empty:
            df_colab = df_suivi.groupby("Collaborateur")["Nb_Realise"].sum().reset_index().sort_values(by="Nb_Realise",
                                                                                                       ascending=False)
            fig_colab = px.pie(
                df_colab,
                names="Collaborateur",
                values="Nb_Realise",
                hole=0.4,
                title="Répartition du Travail par Agent"
            )
            st.plotly_chart(fig_colab, use_container_width=True)
        else:
            st.info("Aucune donnée de collaborateur disponible.")

    st.divider()

    # Récapitulatif Matrice Collaborateurs x Semaines
    st.markdown("#### 👥 Récapitulatif des Saisies par Collaborateur et par Semaine")
    if not df_suivi.empty:
        df_pivot_colab = df_suivi.pivot_table(
            index="Collaborateur",
            columns="Semaine",
            values="Nb_Realise",
            aggfunc="sum",
            fill_value=0
        )
        # Calcul du total cumulé par collaborateur
        df_pivot_colab["Total Général"] = df_pivot_colab.sum(axis=1)

        st.dataframe(df_pivot_colab, use_container_width=True)
    else:
        st.info("Aucune donnée de suivi disponible pour dresser la matrice par collaborateur.")

    # Table of Progress per Site & GF
    st.markdown("#### 📋 Avancement par Site et Groupe de Facturation (GF)")

    # Merge Stock and Realized
    if not df_suivi.empty:
        df_real_grouped = df_suivi.groupby(["Site", "GF"])["Nb_Realise"].sum().reset_index()
        df_progress = pd.merge(df_sites, df_real_grouped, on=["Site", "GF"], how="left").fillna(0)
    else:
        df_progress = df_sites.copy()
        df_progress["Nb_Realise"] = 0

    df_progress["Reste_A_Faire"] = df_progress["Stock_Initial"] - df_progress["Nb_Realise"]
    df_progress["Avancement_%"] = np.where(
        df_progress["Stock_Initial"] > 0,
        (df_progress["Nb_Realise"] / df_progress["Stock_Initial"] * 100).round(1),
        0.0
    )

    st.dataframe(
        df_progress[["DR", "Secteur", "Site", "GF", "Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Avancement_%"]],
        use_container_width=True,
        column_config={
            "Avancement_%": st.column_config.ProgressColumn(
                "Progression (%)",
                format="%.1f%%",
                min_value=0,
                max_value=100
            )
        }
    )

with tab_saisie:
    st.subheader("📝 Formulaire de Saisie de la Production")
    st.caption("Sélectionnez la date, la semaine, le collaborateur ainsi que le site (DR_Secteur) et le GF concerné.")

    col_s1, col_s2, col_s3 = st.columns(3)

    with col_s1:
        date_input = st.date_input("Date de réalisation", value=datetime.now())
        semaine_input = st.selectbox("Semaine", [f"S{i:02d}" for i in range(1, 53)], index=0)
        collaborateur_input = st.selectbox("Collaborateur", LISTE_COLLABORATEURS)

    with col_s2:
        dr_input = st.selectbox("Direction Régionale (DR)", list(MAPPING_DR_SECTEUR.keys()), key="dr_form_saisie")
        secteurs_dispo = MAPPING_DR_SECTEUR[dr_input]
        secteur_input = st.selectbox("Secteur (Agence/Site)", secteurs_dispo, key="sec_form_saisie")
        site_calcule = f"{dr_input}_{secteur_input}"
        st.info(f"**Site généré :** `{site_calcule}`")

    with col_s3:
        gf_input = st.selectbox("Groupe de Facturation (GF)", LISTE_GF, key="gf_form_saisie")

        # Cross reference stock info
        stock_lookup = st.session_state.df_sites[
            (st.session_state.df_sites["Site"] == site_calcule) &
            (st.session_state.df_sites["GF"] == gf_input)
            ]

        stock_cible = stock_lookup["Stock_Initial"].values[0] if not stock_lookup.empty else 0
        st.warning(f"**Stock Initial configuré ({site_calcule} - {gf_input}) :** {stock_cible}")

        nb_realise_input = st.number_input("Nombre de recodifications effectuées", min_value=1, step=1, value=10)

        if st.button("💾 Enregistrer la saisie", use_container_width=True, type="primary"):
            nouvelle_saisie = pd.DataFrame([{
                "Date": date_input.strftime("%Y-%m-%d"),
                "Semaine": semaine_input,
                "Collaborateur": collaborateur_input,
                "DR": dr_input,
                "Secteur": secteur_input,
                "Site": site_calcule,
                "GF": gf_input,
                "Nb_Realise": int(nb_realise_input)
            }])

            st.session_state.df_suivi = pd.concat([st.session_state.df_suivi, nouvelle_saisie], ignore_index=True)
            save_persistent_data()
            st.success(
                f"✅ Saisie de {nb_realise_input} recodification(s) enregistrée pour {collaborateur_input} sur `{site_calcule}` [{gf_input}] ({semaine_input}) !")

    st.divider()
    st.markdown("#### 📜 Historique & Modification des Saisies")
    st.caption(
        "Vous pouvez modifier directement les valeurs ou supprimer des lignes en cas d'erreur dans le tableau ci-dessous.")

    edited_suivi = st.data_editor(
        st.session_state.df_suivi,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Nb_Realise": st.column_config.NumberColumn(
                "Nb_Realise",
                min_value=0,
                step=1
            )
        },
        key="editor_suivi_saisies"
    )

    if st.button("💾 Sauvegarder les modifications de l'historique", type="primary"):
        st.session_state.df_suivi = edited_suivi
        save_persistent_data()
        st.success("Modifications enregistrées avec succès !")
        st.rerun()

with tab_stock:
    st.subheader("⚙️ Configuration des Stocks Initiaux par Site et GF")
    st.markdown(
        "Vous pouvez éditer directement les valeurs du stock initial pour chaque combinaison **Site + GF** ci-dessous.")

    edited_df = st.data_editor(
        st.session_state.df_sites,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Stock_Initial": st.column_config.NumberColumn(
                "Stock Initial à Recodifier",
                min_value=0,
                step=1
            )
        }
    )

    if st.button("💾 Sauvegarder les modifications des stocks", type="primary"):
        st.session_state.df_sites = edited_df
        save_persistent_data()
        st.success("Modifications des stocks initiaux enregistrées !")

with tab_data:
    st.subheader("📁 Importation et Exportation des Données")

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.markdown("#### 📥 Télécharger les Données (Export CSV)")

        csv_suivi = st.session_state.df_suivi.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Télécharger l'historique des saisies (CSV)",
            data=csv_suivi,
            file_name=f"suivi_recodification_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

        csv_sites = st.session_state.df_sites.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Télécharger le référentiel des stocks (CSV)",
            data=csv_sites,
            file_name=f"referentiel_stocks_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_d2:
        st.markdown("#### 📤 Importer l'historique des Saisies (CSV)")
        uploaded_file = st.file_uploader("Charger un fichier CSV de suivi", type=["csv"])
        if uploaded_file is not None:
            try:
                # 1. Détection automatique du séparateur (virgule ou point-virgule Excel)
                try:
                    df_upload = pd.read_csv(uploaded_file, sep=None, engine='python')
                except Exception:
                    uploaded_file.seek(0)
                    df_upload = pd.read_csv(uploaded_file, sep=";")

                # 2. Nettoyage des noms de colonnes
                df_upload.columns = df_upload.columns.str.strip()

                # Mappage insensible à la casse
                col_map = {}
                for col in df_upload.columns:
                    col_lower = col.lower().replace(" ", "_").replace("'", "")
                    if col_lower in ["nb_realise", "nb_realises", "realise", "nombre", "nbre", "quantite"]:
                        col_map[col] = "Nb_Realise"
                    elif col_lower in ["dr", "direction_regionale"]:
                        col_map[col] = "DR"
                    elif col_lower in ["secteur", "agence"]:
                        col_map[col] = "Secteur"
                    elif col_lower in ["site"]:
                        col_map[col] = "Site"
                    elif col_lower in ["gf", "groupe_facturation"]:
                        col_map[col] = "GF"
                    elif col_lower in ["collaborateur", "agent", "nom"]:
                        col_map[col] = "Collaborateur"
                    elif col_lower in ["semaine", "sem"]:
                        col_map[col] = "Semaine"
                    elif col_lower in ["date"]:
                        col_map[col] = "Date"

                df_upload = df_upload.rename(columns=col_map)

                # 3. S'assurer que toutes les colonnes minimales existent
                for c in ["Date", "Semaine", "Collaborateur", "DR", "Secteur", "Site", "GF", "Nb_Realise"]:
                    if c not in df_upload.columns:
                        df_upload[c] = 0 if c == "Nb_Realise" else ""

                # 4. Nettoyage approfondi des données textuelles
                for text_col in ["DR", "Secteur", "Site", "GF", "Collaborateur", "Semaine"]:
                    df_upload[text_col] = df_upload[text_col].astype(str).str.strip()

                # Normalisation des majuscules
                df_upload["DR"] = df_upload["DR"].str.upper()
                df_upload["GF"] = df_upload["GF"].str.upper()

                # Reconstitution automatique du Site si manquant ou incomplet
                mask_no_site = (df_upload["Site"] == "") | (df_upload["Site"].isna())
                df_upload.loc[mask_no_site, "Site"] = df_upload["DR"] + "_" + df_upload["Secteur"]

                # Conversion propre de Nb_Realise
                df_upload["Nb_Realise"] = pd.to_numeric(df_upload["Nb_Realise"], errors="coerce").fillna(0).astype(int)

                # Recommander la structure de colonnes
                cols_order = ["Date", "Semaine", "Collaborateur", "DR", "Secteur", "Site", "GF", "Nb_Realise"]
                st.session_state.df_suivi = df_upload[cols_order]
                save_persistent_data()

                st.success(f"✅ {len(df_upload)} lignes d'historique importées et synchronisées avec succès !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier : {e}")

# =============================================================================
# MODULE 2 — SUIVI DES DÉLAIS DE FACTURATION
# =============================================================================
with tab_delais:
    st.subheader("⏱️ Suivi des délais de facturation")
    st.caption("Pilotage des délais sur l'exercice courant, avec comparaison historique séparée par année, DR, secteur et GF.")

    st.info(
        "Le module distingue le GF0 (facturation mensuelle) des GF1, GF2 et GF3 (facturation trimestrielle). "
        "Les résultats de ces deux périodicités sont présentés séparément pour éviter toute comparaison trompeuse."
    )

    with st.expander("📥 Importer ou actualiser le fichier des délais", expanded=st.session_state.df_delais.empty):
        delay_file = st.file_uploader(
            "Choisir le fichier historique des délais (Excel ou CSV)",
            type=["xlsx", "xls", "csv"],
            key="uploader_historique_delais"
        )

        if delay_file is not None:
            file_bytes = delay_file.getvalue()
            try:
                is_excel = delay_file.name.lower().endswith((".xlsx", ".xls"))
                if is_excel:
                    workbook_probe = pd.ExcelFile(BytesIO(file_bytes))
                    # Détection souple : toute feuille annuelle 20xx respectant
                    # la structure DEXA est acceptée (y compris les exercices futurs).
                    year_sheet_names = detect_dexa_year_sheets(file_bytes)
                    wide_dexa = bool(year_sheet_names)
                else:
                    workbook_probe = None
                    wide_dexa = False

                if wide_dexa:
                    st.success(f"Structure DEXA détectée : {len(year_sheet_names)} feuille(s) annuelle(s) — {', '.join(map(str, year_sheet_names))}.")
                    st.caption("GF0 est importé comme cycle mensuel ; GF1, GF2 et GF3 comme cycles trimestriels. Les feuilles 20xx sont détectées automatiquement, y compris les nouvelles années. Les lignes de moyennes DR/DEXA et les colonnes « Ecart » sont exclues pour éviter les doubles comptages.")
                    st.warning("Chaque import remplace l'historique local des délais. À chaque mise à jour, importe le classeur maître COMPLET avec toutes les feuilles annuelles (2024, 2025, 2026, 2027…). N'importe pas uniquement la nouvelle feuille.")
                    prepared_preview = prepare_dexa_wide_workbook(file_bytes)
                    preview_years = sorted(prepared_preview["Annee"].unique().tolist())
                    preview_gfs = sorted(prepared_preview["GF"].unique().tolist())
                    p1, p2, p3 = st.columns(3)
                    p1.metric("Observations numériques détectées", f"{len(prepared_preview):,}")
                    p2.metric("Années", ", ".join(map(str, preview_years)))
                    p3.metric("Groupes détectés", ", ".join(preview_gfs))
                    st.dataframe(prepared_preview.head(12), use_container_width=True, hide_index=True)

                    import_year_label = f"{preview_years[0]}–{preview_years[-1]}" if preview_years else "années détectées"
                    if st.button("✅ Importer / remplacer l'historique DEXA complet", type="primary", key="btn_import_dexa_historique_complet"):
                        st.session_state.df_delais = prepared_preview
                        save_persistent_data()
                        st.success(f"{len(prepared_preview):,} observations importées pour {import_year_label} et sauvegardées. L'historique local a été remplacé par le contenu complet du classeur.")
                        st.rerun()
                else:
                    # Mode générique pour les fichiers déjà structurés en tableau vertical.
                    if delay_file.name.lower().endswith(".csv"):
                        try:
                            raw_delay_df = pd.read_csv(BytesIO(file_bytes), sep=None, engine="python")
                        except Exception:
                            raw_delay_df = pd.read_csv(BytesIO(file_bytes), sep=";")
                        selected_sheet = None
                    else:
                        selected_sheet = st.selectbox(
                            "Feuille Excel à importer",
                            options=workbook_probe.sheet_names,
                            key="sheet_historique_delais"
                        )
                        raw_delay_df = pd.read_excel(BytesIO(file_bytes), sheet_name=selected_sheet)

                    raw_delay_df.columns = [str(c).strip() for c in raw_delay_df.columns]
                    st.write(f"Aperçu de la feuille : **{selected_sheet or 'CSV'}** — {len(raw_delay_df):,} lignes")
                    st.dataframe(raw_delay_df.head(8), use_container_width=True)

                    source_columns = list(raw_delay_df.columns)
                    options_columns = ["— Non renseigné —"] + source_columns

                    def mapping_index(field):
                        guessed = guess_source_column(source_columns, field)
                        return options_columns.index(guessed) if guessed in options_columns else 0

                    st.markdown("**Associer les colonnes du fichier aux champs de l'application**")
                    map1, map2, map3 = st.columns(3)
                    with map1:
                        map_year = st.selectbox("Année", options_columns, index=mapping_index("Annee"), key="map_delai_annee")
                        map_period = st.selectbox("Période / mois / date", options_columns, index=mapping_index("Periode"), key="map_delai_periode")
                    with map2:
                        map_delay = st.selectbox("Délai moyen (en jours)", options_columns, index=mapping_index("Delai_Jours"), key="map_delai_valeur")
                        map_dr = st.selectbox("Direction Régionale", options_columns, index=mapping_index("DR"), key="map_delai_dr")
                    with map3:
                        map_sector = st.selectbox("Secteur / agence", options_columns, index=mapping_index("Secteur"), key="map_delai_secteur")
                        map_gf = st.selectbox("Groupe de facturation", options_columns, index=mapping_index("GF"), key="map_delai_gf")

                    if st.button("✅ Importer l'historique des délais", type="primary", key="btn_import_delais"):
                        mapping = {
                            "Annee": None if map_year.startswith("—") else map_year,
                            "Periode": None if map_period.startswith("—") else map_period,
                            "Delai_Jours": None if map_delay.startswith("—") else map_delay,
                            "DR": None if map_dr.startswith("—") else map_dr,
                            "Secteur": None if map_sector.startswith("—") else map_sector,
                            "GF": None if map_gf.startswith("—") else map_gf,
                        }
                        prepared = prepare_delay_data(raw_delay_df, mapping)
                        st.session_state.df_delais = prepared
                        save_persistent_data()
                        st.success(f"{len(prepared):,} lignes de délais importées et sauvegardées.")
                        st.rerun()

            except Exception as exc:
                st.error(f"Impossible de lire ou d'importer le fichier : {exc}")

        template_delais = pd.DataFrame(columns=["Annee", "Periode", "DR", "Secteur", "GF", "Delai_Jours"])
        st.download_button(
            "⬇️ Télécharger le modèle de fichier des délais",
            data=template_delais.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig"),
            file_name="modele_delais_facturation.csv",
            mime="text/csv",
            help="Le modèle indique les champs attendus. Le classeur DEXA est reconnu automatiquement dès qu'une feuille annuelle 20xx respecte la structure des mois et des GF."
        )

    df_delais = st.session_state.df_delais.copy()
    if not df_delais.empty:
        # Compatibilité avec les anciens CSV importés avant l'ajout de la périodicité.
        if "Periodicite" not in df_delais.columns:
            df_delais["Periodicite"] = np.where(
                df_delais["GF"].astype(str).str.upper().eq("GF0"),
                "Mensuelle",
                "Trimestrielle"
            )
        df_delais["GF"] = df_delais["GF"].astype(str).str.upper().str.strip()
        df_delais["Periodicite"] = np.where(df_delais["GF"].eq("GF0"), "Mensuelle", "Trimestrielle")
        required_delay_cols = ["Annee", "Periode", "DR", "Secteur", "GF", "Delai_Jours"]
        missing_delay_cols = [c for c in required_delay_cols if c not in df_delais.columns]
        if missing_delay_cols:
            st.warning("Le jeu de données sauvegardé ne possède pas toutes les colonnes attendues. Réimporte le fichier historique.")
        else:
            df_delais["Annee"] = pd.to_numeric(df_delais["Annee"], errors="coerce")
            df_delais["Delai_Jours"] = pd.to_numeric(df_delais["Delai_Jours"], errors="coerce")
            df_delais = df_delais.dropna(subset=["Annee", "Delai_Jours"])
            df_delais["Annee"] = df_delais["Annee"].astype(int)
            df_delais["Periode_Affichage"] = df_delais["Periode"].astype(str) + " " + df_delais["Annee"].astype(str)

            st.info(
                "GF0 correspond au cycle de facturation mensuel. GF1, GF2 et GF3 correspondent aux cycles trimestriels. "
                "Les deux périodicités sont analysées séparément : leurs moyennes ne sont jamais mélangées dans un même KPI. "
                "Les lignes de moyennes régionales et DEXA du classeur source ne sont pas recomptées."
            )
            st.markdown("#### 🎛️ Choix du cycle et filtres d'analyse")
            st.caption(f"Année de pilotage automatique : {datetime.now().year}. Les années antérieures sont réservées à la comparaison historique.")
            analysis_mode = st.radio(
                "Périmètre d'analyse",
                ["GF0 — Facturation mensuelle", "GF1, GF2, GF3 — Facturation trimestrielle"],
                horizontal=True,
                key="delay_frequency_mode"
            )
            is_monthly_mode = analysis_mode.startswith("GF0")
            eligible_gfs = ["GF0"] if is_monthly_mode else ["GF1", "GF2", "GF3"]
            available_gfs = sorted(df_delais["GF"].dropna().astype(str).unique().tolist())
            mode_gfs = [g for g in eligible_gfs if g in available_gfs]

            if is_monthly_mode:
                gf_delay_filter = mode_gfs
                st.caption("Analyse mensuelle : une observation GF0 est attendue pour chaque mois et chaque secteur.")
            else:
                st.caption("Analyse trimestrielle : GF1 (janvier/avril/juillet/octobre), GF2 (février/mai/août/novembre), GF3 (mars/juin/septembre/décembre).")

            # Les KPI principaux et le classement ne portent QUE sur l'année civile en cours.
            # Les années échues sont consultables dans une section historique séparée plus bas.
            current_year = datetime.now().year
            filt1, filt2, filt3, filt4 = st.columns(4)
            with filt1:
                st.metric("Année de pilotage", str(current_year))
                st.caption("Les KPI et le classement excluent automatiquement les exercices échus.")
            with filt2:
                dr_values = sorted(df_delais["DR"].dropna().astype(str).unique().tolist())
                dr_delay_filter = st.multiselect("DR", dr_values, key="filter_delais_dr")
            with filt3:
                sector_values = sorted(df_delais["Secteur"].dropna().astype(str).unique().tolist())
                sector_delay_filter = st.multiselect("Secteur", sector_values, key="filter_delais_sector")
            with filt4:
                if is_monthly_mode:
                    st.text_input("Groupe de facturation", value="GF0 — Mensuel", disabled=True)
                else:
                    gf_default = [g for g in ["GF1", "GF2", "GF3"] if g in mode_gfs]
                    selected_quarterly_gfs = st.multiselect(
                        "Groupes trimestriels",
                        mode_gfs,
                        default=gf_default,
                        key="filter_delais_gf_trimestriel"
                    )
                    gf_delay_filter = selected_quarterly_gfs

            # La cible est déterminée automatiquement selon la périodicité sélectionnée.
            # GF0 : facturation mensuelle (5 jours). GF1-GF3 : facturation trimestrielle (30 jours).
            target_days = 5.0 if is_monthly_mode else 30.0
            target_col, target_note = st.columns([1, 3])
            with target_col:
                st.metric("Cible officielle", f"≤ {target_days:.0f} jours")
            with target_note:
                if is_monthly_mode:
                    st.caption("GF0 : le délai moyen est comparé à une cible de 5 jours, applicable à chaque mois.")
                else:
                    st.caption("GF1, GF2 et GF3 : le délai moyen est comparé à une cible de 30 jours pour chaque cycle trimestriel.")

            filtered_delays = df_delais[
                df_delais["GF"].isin(gf_delay_filter)
                & df_delais["Annee"].eq(current_year)
            ].copy()
            if dr_delay_filter:
                filtered_delays = filtered_delays[filtered_delays["DR"].isin(dr_delay_filter)]
            if sector_delay_filter:
                filtered_delays = filtered_delays[filtered_delays["Secteur"].isin(sector_delay_filter)]

            if filtered_delays.empty:
                st.warning(
                    f"Aucune observation disponible pour {current_year} dans ce périmètre. "
                    "Les années précédentes ne sont pas utilisées dans les KPI de l'année en cours. "
                    "Elles restent visibles dans la comparaison historique ci-dessous."
                )
            else:
                # La moyenne DEXA du classeur source correspond à la moyenne des moyennes DR.
                # On applique la même lecture pour éviter qu'une DR avec davantage de lignes
                # valides ne pèse artificiellement plus lourd dans la synthèse globale.
                regional_kpis = filtered_delays.groupby("DR")["Delai_Jours"].mean()
                avg_delay = regional_kpis.mean() if not regional_kpis.empty else filtered_delays["Delai_Jours"].mean()
                share_target = (filtered_delays["Delai_Jours"] <= target_days).mean() * 100
                gap_target = avg_delay - target_days
                count_records = len(filtered_delays)
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Délai moyen", f"{avg_delay:.1f} jours", delta=f"{gap_target:+.1f} j vs repère", delta_color="inverse")
                k2.metric("Observations ≤ repère", f"{share_target:.1f} %", help=f"Part des observations dont le délai est inférieur ou égal au repère de {target_days:.0f} jours.")
                k3.metric("Lignes analysées", f"{count_records:,}")
                k4.metric("Cible applicable", f"≤ {target_days:.0f} jours")

                st.divider()
                chart_title = (
                    "Évolution mensuelle des délais — GF0"
                    if is_monthly_mode else
                    "Évolution des délais par cycle trimestriel — GF1, GF2 et GF3"
                )
                st.markdown("#### 📈 " + chart_title)
                trend_by_dr = (filtered_delays.groupby(["Annee", "Periode", "Periode_Affichage", "GF", "DR"], dropna=False)["Delai_Jours"]
                               .mean().reset_index())
                trend = (trend_by_dr.groupby(["Annee", "Periode", "Periode_Affichage", "GF"], dropna=False)["Delai_Jours"]
                         .mean().reset_index())
                if "Ordre_Periode" in filtered_delays.columns:
                    period_order = (filtered_delays.groupby(["Annee", "Periode_Affichage"])["Ordre_Periode"].min().reset_index())
                    trend = trend.merge(period_order, on=["Annee", "Periode_Affichage"], how="left")
                    trend = trend.sort_values(["Annee", "Ordre_Periode"])
                else:
                    trend = trend.sort_values(["Annee", "Periode"])
                fig_trend = px.line(
                    trend, x="Periode_Affichage", y="Delai_Jours", color="GF", markers=True,
                    title=chart_title,
                    labels={"Periode_Affichage": "Période", "Delai_Jours": "Délai (jours)", "GF": "Groupe de facturation"}
                )
                fig_trend.add_hline(y=target_days, line_dash="dash", annotation_text=f"Cible : {target_days:.0f} jours")
                fig_trend.update_layout(xaxis={"categoryorder": "array", "categoryarray": trend["Periode_Affichage"].drop_duplicates().tolist()})
                st.plotly_chart(fig_trend, use_container_width=True)

                left_chart, right_chart = st.columns(2)
                with left_chart:
                    st.markdown("#### 🏢 Comparaison des délais par secteur")
                    by_sector = (filtered_delays.groupby(["Secteur", "GF"])["Delai_Jours"].mean().reset_index())
                    by_sector = by_sector.sort_values("Delai_Jours", ascending=True)
                    fig_sector = px.bar(
                        by_sector, x="Secteur", y="Delai_Jours", color="GF", barmode="group",
                        title="Délai moyen par secteur et par GF",
                        labels={"Delai_Jours": "Délai (jours)", "Secteur": "Secteur"}
                    )
                    fig_sector.add_hline(y=target_days, line_dash="dash", annotation_text="Cible")
                    st.plotly_chart(fig_sector, use_container_width=True)

                with right_chart:
                    st.markdown("#### 🧭 Synthèse par Direction Régionale")
                    by_dr = filtered_delays.groupby("DR")["Delai_Jours"].mean().reset_index().sort_values("Delai_Jours")
                    fig_dr = px.bar(
                        by_dr, x="DR", y="Delai_Jours", color="Delai_Jours", color_continuous_scale="RdYlGn_r",
                        title="Délai moyen par DR", labels={"Delai_Jours": "Délai (jours)", "DR": "Direction Régionale"}
                    )
                    fig_dr.add_hline(y=target_days, line_dash="dash", annotation_text="Cible")
                    st.plotly_chart(fig_dr, use_container_width=True)

                st.divider()
                st.markdown("#### 📋 Tableau de pilotage par DR, secteur et GF")
                summary = (filtered_delays.groupby(["Annee", "DR", "Secteur", "GF", "Periodicite"], dropna=False)
                           .agg(Delai_Moyen=("Delai_Jours", "mean"), Nb_Observations=("Delai_Jours", "size"))
                           .reset_index())
                summary["Cible_Jours"] = summary["GF"].map(CIBLES_DELAIS_JOURS).fillna(target_days)
                summary["Ecart_Cible"] = summary["Delai_Moyen"] - summary["Cible_Jours"]
                summary["Statut"] = np.where(
                    summary["Delai_Moyen"] <= summary["Cible_Jours"],
                    "Dans la cible",
                    "Au-dessus de la cible"
                )
                summary["Delai_Moyen"] = summary["Delai_Moyen"].round(1)
                summary["Cible_Jours"] = summary["Cible_Jours"].round(1)
                summary["Ecart_Cible"] = summary["Ecart_Cible"].round(1)
                summary = summary.sort_values(["Delai_Moyen", "DR", "Secteur"])
                st.dataframe(
                    summary,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Delai_Moyen": st.column_config.NumberColumn("Délai moyen (jours)", format="%.1f j"),
                        "Cible_Jours": st.column_config.NumberColumn("Cible applicable", format="%.0f j"),
                        "Ecart_Cible": st.column_config.NumberColumn("Écart à la cible", format="%+.1f j"),
                        "Nb_Observations": st.column_config.NumberColumn("Observations", format="%d")
                    }
                )

                # -----------------------------------------------------------------
                # V3 — Classement, diagnostic comparatif et plan d'action
                # Les KPI restent strictement limités à l'année civile en cours.
                # La variation N-1 compare les mêmes périodes par agence et par GF.
                # -----------------------------------------------------------------
                st.divider()
                st.markdown("#### 🧠 Diagnostic managérial et classement des agences")
                history_for_diagnostic = df_delais.copy()
                if dr_delay_filter:
                    history_for_diagnostic = history_for_diagnostic[history_for_diagnostic["DR"].isin(dr_delay_filter)]
                if sector_delay_filter:
                    history_for_diagnostic = history_for_diagnostic[history_for_diagnostic["Secteur"].isin(sector_delay_filter)]
                if gf_delay_filter:
                    history_for_diagnostic = history_for_diagnostic[history_for_diagnostic["GF"].isin(gf_delay_filter)]

                agency_summary = build_managerial_diagnostics(filtered_delays, history_for_diagnostic, current_year)
                if agency_summary.empty:
                    st.info(f"Le diagnostic sera disponible dès que les premières observations de {current_year} seront importées pour le périmètre sélectionné.")
                else:
                    n_evaluated = len(agency_summary)
                    n_over = int((agency_summary["Ecart_Cible"] > 0).sum())
                    n_priority = int(agency_summary["Niveau_Action"].isin(["1 — Priorité haute", "2 — Action corrective"]).sum())
                    n_improved = int((agency_summary["Tendance"] == "Amélioration vs N-1").sum())
                    n_worsened = int((agency_summary["Tendance"] == "Dégradation vs N-1").sum())
                    d1, d2, d3, d4 = st.columns(4)
                    d1.metric("Agences / GF évalués", f"{n_evaluated}")
                    d2.metric("Moyenne au-dessus de la cible", f"{n_over}")
                    d3.metric("Actions correctives prioritaires", f"{n_priority}")
                    d4.metric("Améliorations vs N-1", f"{n_improved}", delta=f"{n_worsened} dégradations", delta_color="inverse")
                    st.caption(
                        f"Diagnostic calculé sur les observations disponibles de {current_year}. "
                        "Les comparaisons N-1 portent exclusivement sur les mêmes mois/cycles. "
                        "Les niveaux d'action sont des repères analytiques proposés, et non des seuils officiels SODECI."
                    )

                    st.markdown("##### 🏆 Classement des agences par groupe de facturation")
                    ranking_display = agency_summary[[
                        "GF", "Rang", "DR", "Secteur", "Delai_Moyen", "Cible_Jours", "Ecart_Cible",
                        "Nb_Observations", "Nb_Periodes_Hors_Cible", "Tendance"
                    ]].sort_values(["GF", "Rang", "DR", "Secteur"])
                    st.dataframe(
                        ranking_display, use_container_width=True, hide_index=True,
                        column_config={
                            "Delai_Moyen": st.column_config.NumberColumn("Délai moyen", format="%.1f j"),
                            "Cible_Jours": st.column_config.NumberColumn("Cible", format="%.0f j"),
                            "Ecart_Cible": st.column_config.NumberColumn("Écart à la cible", format="%+.1f j"),
                            "Nb_Observations": st.column_config.NumberColumn("Périodes renseignées", format="%d"),
                            "Nb_Periodes_Hors_Cible": st.column_config.NumberColumn("Périodes hors cible", format="%d"),
                        }
                    )

                    left_rank, right_rank = st.columns([1.15, 1])
                    with left_rank:
                        st.markdown("##### 📊 Comparaison visuelle des agences")
                        rank_chart = agency_summary.sort_values(["GF", "Delai_Moyen"], ascending=[True, False])
                        fig_rank = px.bar(
                            rank_chart, x="Delai_Moyen", y="Agence", color="Niveau_Action",
                            facet_col="GF", facet_col_wrap=1, orientation="h",
                            hover_data={"Cible_Jours": True, "Ecart_Cible": ":+.1f",
                                        "Nb_Observations": True, "Taux_Periodes_Hors_Cible": ":.1f", "Tendance": True},
                            title=f"Délai moyen par agence — {current_year}",
                            labels={"Delai_Moyen": "Délai moyen (jours)", "Agence": "Agence", "Niveau_Action": "Niveau d'action"}
                        )
                        fig_rank.add_vline(x=target_days, line_dash="dash", annotation_text=f"Cible : {target_days:.0f} j")
                        fig_rank.update_layout(height=max(430, 270 * len(mode_gfs)), showlegend=True)
                        st.plotly_chart(fig_rank, use_container_width=True)

                    with right_rank:
                        st.markdown("##### 🧭 Lecture par Direction Régionale")
                        dr_summary = agency_summary.groupby(["GF", "DR"], dropna=False).agg(
                            Delai_Moyen_DR=("Delai_Moyen", "mean"),
                            Nb_Secteurs=("Secteur", "nunique"),
                            Nb_Secteurs_Hors_Cible=("Ecart_Cible", lambda values: int((values > 0).sum()))
                        ).reset_index()
                        worst_sector = (agency_summary.sort_values("Delai_Moyen", ascending=False)
                            .drop_duplicates(["GF", "DR"])[["GF", "DR", "Secteur", "Delai_Moyen"]]
                            .rename(columns={"Secteur": "Secteur_Le_Plus_Long", "Delai_Moyen": "Delai_Max_Secteur"}))
                        dr_summary = dr_summary.merge(worst_sector, on=["GF", "DR"], how="left")
                        dr_summary["Cible_Jours"] = dr_summary["GF"].map(CIBLES_DELAIS_JOURS)
                        dr_summary["Ecart_Cible"] = dr_summary["Delai_Moyen_DR"] - dr_summary["Cible_Jours"]
                        dr_summary["Part_Secteurs_Hors_Cible"] = np.where(
                            dr_summary["Nb_Secteurs"] > 0,
                            dr_summary["Nb_Secteurs_Hors_Cible"] / dr_summary["Nb_Secteurs"] * 100, 0)
                        dr_summary = dr_summary.sort_values(["GF", "Ecart_Cible"], ascending=[True, False])
                        st.caption("Le délai moyen DR est calculé à partir des moyennes des secteurs présents dans le filtre, pour donner un poids égal à chaque secteur observé.")
                        st.dataframe(
                            dr_summary, use_container_width=True, hide_index=True,
                            column_config={
                                "Delai_Moyen_DR": st.column_config.NumberColumn("Délai moyen DR", format="%.1f j"),
                                "Cible_Jours": st.column_config.NumberColumn("Cible", format="%.0f j"),
                                "Ecart_Cible": st.column_config.NumberColumn("Écart", format="%+.1f j"),
                                "Delai_Max_Secteur": st.column_config.NumberColumn("Délai secteur le plus long", format="%.1f j"),
                                "Part_Secteurs_Hors_Cible": st.column_config.NumberColumn("Secteurs hors cible", format="%.1f %%"),
                            }
                        )

                    st.divider()
                    st.markdown("##### 🔎 Améliorations et dégradations par rapport à N-1")
                    trend_display = agency_summary[[
                        "GF", "DR", "Secteur", "Delai_Courant_Comparable", "Delai_N1_Comparable",
                        "Variation_vs_N1", "Nb_Periodes_Comparees", "Tendance"
                    ]].sort_values("Variation_vs_N1", ascending=False, na_position="last")
                    st.dataframe(
                        trend_display, use_container_width=True, hide_index=True,
                        column_config={
                            "Delai_Courant_Comparable": st.column_config.NumberColumn("Année courante — périodes comparables", format="%.1f j"),
                            "Delai_N1_Comparable": st.column_config.NumberColumn("N-1 — mêmes périodes", format="%.1f j"),
                            "Variation_vs_N1": st.column_config.NumberColumn("Variation du délai", format="%+.1f j"),
                            "Nb_Periodes_Comparees": st.column_config.NumberColumn("Périodes comparées", format="%d"),
                        }
                    )
                    st.caption("Variation négative = baisse du délai (amélioration). Variation positive = hausse du délai (dégradation). Les agences sans période commune avec N-1 ne reçoivent pas de tendance.")

                    st.divider()
                    st.markdown("##### 🚦 Diagnostic et plan d'action managérial proposé")
                    action_display = agency_summary[[
                        "Niveau_Action", "GF", "DR", "Secteur", "Diagnostic", "Delai_Moyen", "Cible_Jours",
                        "Ecart_Cible", "Taux_Periodes_Hors_Cible", "Tendance", "Action_Conseillée"
                    ]].sort_values(["Niveau_Action", "Ecart_Cible", "Taux_Periodes_Hors_Cible"], ascending=[True, False, False])
                    st.dataframe(
                        action_display, use_container_width=True, hide_index=True,
                        column_config={
                            "Delai_Moyen": st.column_config.NumberColumn("Délai moyen", format="%.1f j"),
                            "Cible_Jours": st.column_config.NumberColumn("Cible", format="%.0f j"),
                            "Ecart_Cible": st.column_config.NumberColumn("Écart", format="%+.1f j"),
                            "Taux_Periodes_Hors_Cible": st.column_config.NumberColumn("Périodes hors cible", format="%.1f %%"),
                        }
                    )
                    priority_actions = action_display[action_display["Niveau_Action"].isin([
                        "1 — Priorité haute", "2 — Action corrective", "3 — Vigilance"
                    ])].head(5)
                    if not priority_actions.empty:
                        with st.expander("📌 Les cinq actions à examiner en premier", expanded=True):
                            for _, item in priority_actions.iterrows():
                                st.markdown(
                                    f"**{item['Niveau_Action']} — {item['DR']} / {item['Secteur']} ({item['GF']})**  \n"
                                    f"{item['Diagnostic']} : {item['Delai_Moyen']:.1f} j pour une cible de "
                                    f"{item['Cible_Jours']:.0f} j (écart {item['Ecart_Cible']:+.1f} j).  \n"
                                    f"Action proposée : {item['Action_Conseillée']}"
                                )
                    export_cols = ["GF", "Rang", "DR", "Secteur", "Delai_Moyen", "Cible_Jours", "Ecart_Cible",
                                   "Nb_Observations", "Nb_Periodes_Hors_Cible", "Taux_Periodes_Hors_Cible", "Delai_Max",
                                   "Delai_Courant_Comparable", "Delai_N1_Comparable", "Variation_vs_N1",
                                   "Nb_Periodes_Comparees", "Tendance", "Diagnostic", "Niveau_Action", "Action_Conseillée"]
                    st.download_button(
                        "⬇️ Exporter le diagnostic et le plan d'action (CSV)",
                        data=agency_summary[export_cols].to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig"),
                        file_name=f"diagnostic_managerial_delais_{current_year}.csv", mime="text/csv",
                        key="download_v3_managerial_diagnostic"
                    )

                st.download_button(
                    "⬇️ Exporter la synthèse filtrée (CSV)",
                    data=summary.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig"),
                    file_name=("synthese_delais_GF0_mensuel.csv" if is_monthly_mode else "synthese_delais_GF1_GF2_GF3_trimestriel.csv"),
                    mime="text/csv"
                )

                with st.expander("🔎 Consulter les données détaillées de l'année en cours"):
                    st.dataframe(filtered_delays, use_container_width=True, hide_index=True)

            # -----------------------------------------------------------------
            # HISTORIQUE — section distincte : les exercices échus ne contribuent
            # jamais aux KPI ni au classement de l'année courante.
            # -----------------------------------------------------------------
            st.divider()
            st.markdown("#### 🗂️ Comparaison historique des exercices")
            st.caption(
                "Cette lecture compare séparément les années disponibles. Elle ne modifie pas les KPI "
                f"de pilotage {current_year}, qui restent calculés exclusivement sur {current_year}. "
                "Les moyennes annuelles sont calculées comme la moyenne des moyennes par DR, "
                "pour conserver une pondération régionale égale."
            )
            history = df_delais[df_delais["GF"].isin(gf_delay_filter)].copy()
            if dr_delay_filter:
                history = history[history["DR"].isin(dr_delay_filter)]
            if sector_delay_filter:
                history = history[history["Secteur"].isin(sector_delay_filter)]

            if history.empty:
                st.info("Aucune donnée historique disponible pour les filtres sélectionnés.")
            else:
                hist_dr = (
                    history.groupby(["Annee", "GF", "DR"], dropna=False)["Delai_Jours"]
                    .mean().reset_index(name="Delai_Moyen_DR")
                )
                hist_summary = (
                    hist_dr.groupby(["Annee", "GF"], dropna=False)
                    .agg(Delai_Moyen_DEXA=("Delai_Moyen_DR", "mean"), Nb_DR=("DR", "nunique"))
                    .reset_index()
                )
                hist_summary["Cible_Jours"] = hist_summary["GF"].map(CIBLES_DELAIS_JOURS)
                hist_summary["Ecart_Cible"] = hist_summary["Delai_Moyen_DEXA"] - hist_summary["Cible_Jours"]
                hist_summary["Delai_Moyen_DEXA"] = hist_summary["Delai_Moyen_DEXA"].round(1)
                hist_summary["Ecart_Cible"] = hist_summary["Ecart_Cible"].round(1)

                hist_fig = px.line(
                    hist_summary,
                    x="Annee",
                    y="Delai_Moyen_DEXA",
                    color="GF",
                    markers=True,
                    title=("Comparaison annuelle GF0 — facturation mensuelle" if is_monthly_mode
                           else "Comparaison annuelle GF1, GF2 et GF3 — facturation trimestrielle"),
                    labels={"Annee": "Exercice", "Delai_Moyen_DEXA": "Délai moyen annuel (jours)", "GF": "Groupe de facturation"},
                    hover_data={"Nb_DR": True, "Cible_Jours": True, "Ecart_Cible": ":+.1f"}
                )
                hist_fig.add_hline(y=target_days, line_dash="dash", annotation_text=f"Cible : {target_days:.0f} jours")
                hist_fig.update_xaxes(dtick=1)
                st.plotly_chart(hist_fig, use_container_width=True)
                st.dataframe(
                    hist_summary.sort_values(["GF", "Annee"]),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Delai_Moyen_DEXA": st.column_config.NumberColumn("Délai moyen annuel", format="%.1f j"),
                        "Cible_Jours": st.column_config.NumberColumn("Cible", format="%.0f j"),
                        "Ecart_Cible": st.column_config.NumberColumn("Écart à la cible", format="%+.1f j"),
                        "Nb_DR": st.column_config.NumberColumn("DR prises en compte", format="%d")
                    }
                )
                st.caption(
                    "Attention : une année en cours est partielle. Sa moyenne annuelle est une moyenne des seules périodes "
                    "déjà renseignées et ne doit pas être interprétée comme un exercice clôturé."
                )
                st.download_button(
                    "⬇️ Exporter la comparaison historique (CSV)",
                    data=hist_summary.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig"),
                    file_name=f"comparaison_historique_delais_{'GF0' if is_monthly_mode else 'GF1_GF2_GF3'}.csv",
                    mime="text/csv",
                    key="download_history_delay_csv"
                )

            if st.button("🗑️ Effacer l'historique des délais importé", key="delete_delay_history"):
                st.session_state.df_delais = pd.DataFrame()
                if os.path.exists(DATA_DELAIS_FILE):
                    os.remove(DATA_DELAIS_FILE)
                st.success("Historique des délais effacé.")
                st.rerun()
    else:
        st.info("En attente du fichier historique. Dépose-le dans la zone d'import ci-dessus pour activer les indicateurs et les graphiques.")


with tab_rapport:
    st.subheader("📑 Rapport mensuel de pilotage — DEXA")
    st.caption(
        "Rapport consolidé : avancement de la recodification, activité des cinq dernières semaines, "
        "évolution des délais et lecture de concordance entre les semaines de saisie et les résultats observés."
    )

    df_sites_report = st.session_state.df_sites.copy()
    df_suivi_report = st.session_state.df_suivi.copy()
    df_delais_report = st.session_state.df_delais.copy()

    # Date d'arrêté par défaut : dernière date de saisie exploitable ; sinon date du jour.
    if not df_suivi_report.empty and "Date" in df_suivi_report.columns:
        report_dates = parse_report_date_series(df_suivi_report["Date"]).dropna()
    else:
        report_dates = pd.Series(dtype="datetime64[ns]")
    default_report_date = report_dates.max().date() if not report_dates.empty else datetime.now().date()

    with st.container():
        control_col, info_col = st.columns([1, 2])
        with control_col:
            report_cutoff = st.date_input(
                "Date d'arrêté du rapport",
                value=default_report_date,
                key="report_dexa_cutoff_date",
                help="Les saisies postérieures à cette date sont exclues du point d'avancement et du suivi hebdomadaire."
            )
        with info_col:
            mois_fr_rapport = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"][report_cutoff.month - 1]
            st.info(
                f"Rapport de {mois_fr_rapport} {report_cutoff.year} — arrêté au {report_cutoff.strftime('%d/%m/%Y')}. "
                "Les délais sont limités à l'exercice de cette date et comparés à N-1 sur les mêmes mois disponibles."
            )

    payload = build_monthly_report_data(
        df_sites_report, df_suivi_report, df_delais_report, report_cutoff
    )
    global_row = payload["global"].iloc[0] if not payload["global"].empty else {}
    stock_total = float(global_row.get("Stock_Initial", 0) or 0)
    realised_total = float(global_row.get("Nb_Realise", 0) or 0)
    remaining_total = float(global_row.get("Reste_A_Faire", 0) or 0)
    progress_total = global_row.get("Taux_Avancement", np.nan)

    st.markdown("### 1. Point d'avancement global de la recodification")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Stock initial DEXA", f"{stock_total:,.0f}")
    k2.metric("Nombre recodifié", f"{realised_total:,.0f}")
    k3.metric("Nombre restant", f"{remaining_total:,.0f}")
    k4.metric("Taux d'avancement", f"{progress_total:.1f} %" if pd.notna(progress_total) else "—")
    st.caption(
        "Le reste à faire est plafonné à zéro ; les éventuels volumes réalisés au-delà du stock configuré sont isolés dans la colonne Dépassement. Le taux DEXA est recalculé sur les totaux des quatre DR : nombre réalisé total / stock initial total."
    )
    reconciliation = payload.get("reconciliation", {})
    recon_dr_ok = all(reconciliation.get("par_dr", {}).values()) if reconciliation else False
    recon_gf_ok = all(reconciliation.get("par_gf", {}).values()) if reconciliation else False
    if recon_dr_ok and recon_gf_ok:
        st.success("Contrôle de cohérence validé : les totaux DEXA concordent avec la somme des quatre DR et la somme des GF.")
    else:
        st.warning(
            "Écart de réconciliation détecté entre DEXA, les DR et/ou les GF. Vérifie le référentiel des stocks et les saisies importées. "
            f"Écarts DR : {reconciliation.get('ecarts_dr', {})} — Écarts GF : {reconciliation.get('ecarts_gf', {})}"
        )

    if not payload["dr"].empty:
        dr_display = payload["dr"].copy()
        dr_display["Périmètre"] = dr_display["DR"]
        dr_display = dr_display[[
            "Périmètre", "Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Taux_Avancement",
            "Statut_Recodification", "Depassement", "Nb_Saisies", "Date_Derniere_Saisie_DR", "Semaine_Derniere_Saisie_DR"
        ]]
        st.markdown("#### Avancement DEXA et par Direction Régionale")
        dexadr = pd.DataFrame([{
            "Périmètre": "DEXA", "Stock_Initial": stock_total, "Nb_Realise": realised_total,
            "Reste_A_Faire": remaining_total, "Taux_Avancement": progress_total,
            "Statut_Recodification": report_status_from_progress(progress_total, stock_total),
            "Depassement": float(global_row.get("Depassement", 0) or 0),
            "Nb_Saisies": int(global_row.get("Nb_Saisies", 0) or 0),
            "Date_Derniere_Saisie_DR": pd.NaT, "Semaine_Derniere_Saisie_DR": "—"
        }])
        report_dr_table = pd.concat([dexadr, dr_display], ignore_index=True)
        st.dataframe(
            report_dr_table, use_container_width=True, hide_index=True,
            column_config={
                "Stock_Initial": st.column_config.NumberColumn("Nombre initial", format="%,.0f"),
                "Nb_Realise": st.column_config.NumberColumn("Nombre réalisé", format="%,.0f"),
                "Reste_A_Faire": st.column_config.NumberColumn("Nombre restant", format="%,.0f"),
                "Taux_Avancement": st.column_config.ProgressColumn("Taux d'avancement", format="%.1f %%", min_value=0, max_value=100),
                "Depassement": st.column_config.NumberColumn("Dépassement du stock", format="%,.0f"),
                "Nb_Saisies": st.column_config.NumberColumn("Nb de lignes de saisie", format="%d"),
                "Date_Derniere_Saisie_DR": st.column_config.DateColumn("Dernière saisie DR", format="DD/MM/YYYY"),
            }
        )
        progress_chart = payload["dr"].sort_values("Taux_Avancement", ascending=True, na_position="first")
        fig_progress = px.bar(
            progress_chart, x="Taux_Avancement", y="DR", orientation="h", text="Taux_Avancement",
            hover_data={"Stock_Initial": True, "Nb_Realise": True, "Reste_A_Faire": True},
            title="Taux d'avancement de la recodification par DR",
            labels={"Taux_Avancement": "Avancement (%)", "DR": "Direction Régionale"}
        )
        fig_progress.add_vline(x=100, line_dash="dash", annotation_text="Stock initial traité")
        fig_progress.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_progress.update_layout(xaxis_range=[0, max(110, float(progress_chart["Taux_Avancement"].fillna(0).max()) * 1.15)])
        st.plotly_chart(fig_progress, use_container_width=True)
    else:
        st.info("Aucun référentiel de stock disponible pour calculer l'avancement par DR.")

    st.markdown("### 2. Point d'avancement des saisies par GF, DR et secteur")
    if not payload["gf"].empty:
        gf_view = payload["gf"].copy()
        st.markdown("#### Synthèse DEXA par GF")
        st.caption("Cette synthèse agrège l'intégralité des quatre DR pour chaque GF, y compris les secteurs/GF sans saisie. Elle doit donc se réconcilier avec le total global DEXA.")
        st.dataframe(
            gf_view[["GF", "Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Taux_Avancement", "Statut_Recodification", "Depassement"]],
            use_container_width=True, hide_index=True,
            column_config={
                "Stock_Initial": st.column_config.NumberColumn("Nombre initial", format="%,.0f"),
                "Nb_Realise": st.column_config.NumberColumn("Nombre saisi / réalisé", format="%,.0f"),
                "Reste_A_Faire": st.column_config.NumberColumn("Nombre restant", format="%,.0f"),
                "Taux_Avancement": st.column_config.ProgressColumn("Avancement", format="%.1f %%", min_value=0, max_value=100),
                "Depassement": st.column_config.NumberColumn("Dépassement", format="%,.0f"),
            }
        )
    if not payload["dr_gf"].empty:
        st.markdown("#### Avancement par DR et par GF")
        st.caption("Seules les combinaisons DR/GF ayant au moins une saisie enregistrée sont affichées. Le stock global par DR reste présenté intégralement dans la section précédente.")
        st.dataframe(
            payload["dr_gf"], use_container_width=True, hide_index=True,
            column_config={
                "Stock_Initial": st.column_config.NumberColumn("Nombre initial", format="%,.0f"),
                "Nb_Realise": st.column_config.NumberColumn("Nombre saisi / réalisé", format="%,.0f"),
                "Reste_A_Faire": st.column_config.NumberColumn("Nombre restant", format="%,.0f"),
                "Taux_Avancement": st.column_config.ProgressColumn("Avancement", format="%.1f %%", min_value=0, max_value=100),
                "Depassement": st.column_config.NumberColumn("Dépassement", format="%,.0f"),
            }
        )
    st.markdown("#### Détail par secteur et par GF")
    st.caption("Seuls les secteurs/GF ayant déjà au moins une saisie sont présentés dans ce tableau.")
    st.dataframe(
        payload["secteur_gf"], use_container_width=True, hide_index=True,
        column_config={
            "Stock_Initial": st.column_config.NumberColumn("Nombre initial", format="%,.0f"),
            "Nb_Realise": st.column_config.NumberColumn("Nombre saisi / réalisé", format="%,.0f"),
            "Reste_A_Faire": st.column_config.NumberColumn("Nombre restant", format="%,.0f"),
            "Taux_Avancement": st.column_config.ProgressColumn("Avancement", format="%.1f %%", min_value=0, max_value=100),
            "Depassement": st.column_config.NumberColumn("Dépassement", format="%,.0f"),
            "Derniere_Saisie": st.column_config.DateColumn("Dernière saisie", format="DD/MM/YYYY"),
        }
    )

    st.markdown("### 3. Point des saisies hebdomadaires")
    st.caption("Les semaines sont reprises directement de la colonne « Semaine » du suivi de production, comme dans le récapitulatif Collaborateur × Semaine du Dashboard & KPI. Les cinq dernières semaines réellement renseignées sont présentées.")
    weekly_display = payload["weekly"].copy()
    st.markdown("#### Activité des cinq dernières semaines")
    st.caption("« Nombre de lignes de saisie » compte les enregistrements ; « Quantité recodifiée » correspond à la somme de Nb_Realise, comme dans le tableau récapitulatif du Dashboard & KPI.")
    st.dataframe(
        weekly_display[["Libelle_Semaine", "Nb_Saisies", "Nb_Realise", "Nb_DR", "Nb_Secteurs"]],
        use_container_width=True, hide_index=True,
        column_config={
            "Nb_Saisies": st.column_config.NumberColumn("Nombre de lignes de saisie", format="%d"),
            "Nb_Realise": st.column_config.NumberColumn("Quantité recodifiée", format="%,.0f"),
            "Nb_DR": st.column_config.NumberColumn("DR actives", format="%d"),
            "Nb_Secteurs": st.column_config.NumberColumn("Secteurs actifs", format="%d"),
        }
    )
    if not payload["weekly_dr"].empty:
        weekly_chart = payload["weekly_dr"].copy()
        fig_week_report = px.bar(
            weekly_chart, x="Libelle_Semaine", y="Nb_Realise", color="DR", barmode="stack",
            title="Volume de recodification par semaine et par DR",
            labels={"Libelle_Semaine": "Semaine", "Nb_Realise": "Quantité recodifiée"}
        )
        st.plotly_chart(fig_week_report, use_container_width=True)
        st.markdown("#### Détail hebdomadaire par DR et par GF")
        weekly_dr_gf_view = payload["weekly_dr_gf"].copy()
        st.dataframe(
            weekly_dr_gf_view[["Libelle_Semaine", "DR", "GF", "Nb_Saisies", "Nb_Realise"]],
            use_container_width=True, hide_index=True
        )
    else:
        st.info("Aucune saisie datée dans les cinq semaines qui précèdent la date d'arrêté.")

    if payload.get("saisies_sans_semaine", 0) > 0:
        st.warning(f"{payload['saisies_sans_semaine']} ligne(s) de suivi n'ont pas de semaine exploitable dans la colonne Semaine et ne peuvent pas être affectées aux cinq dernières semaines.")

    if payload["saisies_sans_date"] > 0:
        st.warning(
            f"{payload['saisies_sans_date']} ligne(s), représentant {payload['volume_saisies_sans_date']:,.0f} élément(s), "
            "n'ont pas de date exploitable : elles sont exclues des indicateurs d'avancement arrêtés à une date donnée. "
            "Le suivi hebdomadaire, lui, reprend la colonne Semaine lorsqu'elle est renseignée."
        )

    st.markdown("### 4. Évolution des délais et lecture de l'impact de la recodification")
    st.caption(
        f"Les délais sont calculés sur {payload['annee']} jusqu'au mois de l'arrêté ({payload['mois']}) et comparés à {payload['annee'] - 1} "
        "sur les mêmes périodes. GF0 conserve sa cible de 5 jours ; GF1, GF2 et GF3 conservent leur cible de 30 jours."
    )
    if payload["delay_current"].empty:
        st.info("Aucune donnée de délai disponible sur l'exercice et les périodes retenus pour cette date d'arrêté.")
    else:
        fig_dexa_evolution, fig_dr_evolution = build_report_delay_figures(payload)
        if fig_dexa_evolution is not None:
            st.markdown("#### Évolution du délai moyen DEXA par GF — comparaison avec N-1")
            st.caption("Chaque DR a le même poids dans la moyenne DEXA ; la ligne pointillée indique la cible du GF concerné.")
            st.plotly_chart(fig_dexa_evolution, use_container_width=True)
        if fig_dr_evolution is not None:
            st.markdown("#### Évolution des délais par DR et par GF")
            st.caption("Une courbe par DR ; GF0 est suivi mensuellement et GF1, GF2, GF3 selon leurs cycles trimestriels.")
            st.plotly_chart(fig_dr_evolution, use_container_width=True)


    if not payload["delay_dexa_impact"].empty:
        st.markdown("#### Synthèse de l'évolution des délais au niveau DEXA par GF")
        st.caption("Le délai DEXA est la moyenne des moyennes régionales : chaque DR a ainsi le même poids dans cette synthèse.")
        dexa_delay_cols = [
            "GF", "Delai_Moyen_DEXA", "Cible_Jours", "Ecart_Cible", "Delai_N1_DEXA_Comparable",
            "Variation_vs_N1", "Nb_DR_Avec_Delai", "Taux_Avancement_DEXA_GF", "Statut_Recodification_DEXA_GF"
        ]
        st.dataframe(
            payload["delay_dexa_impact"][dexa_delay_cols], use_container_width=True, hide_index=True,
            column_config={
                "Delai_Moyen_DEXA": st.column_config.NumberColumn(f"Délai DEXA {payload['annee']}", format="%.1f j"),
                "Cible_Jours": st.column_config.NumberColumn("Cible", format="%.0f j"),
                "Ecart_Cible": st.column_config.NumberColumn("Écart à la cible", format="%+.1f j"),
                "Delai_N1_DEXA_Comparable": st.column_config.NumberColumn(f"Délai DEXA {payload['annee'] - 1}", format="%.1f j"),
                "Variation_vs_N1": st.column_config.NumberColumn("Évolution vs N-1", format="%+.1f j"),
                "Taux_Avancement_DEXA_GF": st.column_config.NumberColumn("Avancement recodification GF", format="%.1f %%"),
            }
        )

    if not payload["delay_dr_impact"].empty:
        st.markdown("#### Lecture de concordance par DR et GF")
        impact_cols = [
            c for c in ["DR", "GF", "Statut_DR", "Taux_Avancement_DR", "Statut_Recodification", "Taux_Avancement",
                        "Stock_Initial", "Nb_Realise", "Reste_A_Faire", "Semaine_Derniere_Saisie_DR_GF",
                        "Date_Derniere_Saisie_DR_GF", "Semaine_Derniere_Saisie_DR", "Date_Derniere_Saisie_DR", "Delai_Moyen_Courant",
                        "Delai_N1_Comparable", "Variation_vs_N1", "Cible_Jours", "Ecart_Cible",
                        "Nb_Periodes_Comparees", "Lecture_Impact"]
            if c in payload["delay_dr_impact"].columns
        ]
        impact_view = payload["delay_dr_impact"].sort_values(["GF", "DR"])
        st.dataframe(
            impact_view[impact_cols], use_container_width=True, hide_index=True,
            column_config={
                "Taux_Avancement_DR": st.column_config.NumberColumn("Avancement total DR", format="%.1f %%"),
                "Taux_Avancement": st.column_config.NumberColumn("Avancement DR/GF", format="%.1f %%"),
                "Date_Derniere_Saisie_DR_GF": st.column_config.DateColumn("Dernière saisie DR/GF", format="DD/MM/YYYY"),
                "Date_Derniere_Saisie_DR": st.column_config.DateColumn("Dernière saisie DR", format="DD/MM/YYYY"),
                "Stock_Initial": st.column_config.NumberColumn("Stock initial DR/GF", format="%,.0f"),
                "Nb_Realise": st.column_config.NumberColumn("Réalisé DR/GF", format="%,.0f"),
                "Reste_A_Faire": st.column_config.NumberColumn("Reste DR/GF", format="%,.0f"),
                "Delai_Moyen_Courant": st.column_config.NumberColumn(f"Délai {payload['annee']}", format="%.1f j"),
                "Delai_N1_Comparable": st.column_config.NumberColumn(f"Délai {payload['annee'] - 1}", format="%.1f j"),
                "Variation_vs_N1": st.column_config.NumberColumn("Évolution vs N-1", format="%+.1f j"),
                "Cible_Jours": st.column_config.NumberColumn("Cible", format="%.0f j"),
                "Ecart_Cible": st.column_config.NumberColumn("Écart cible", format="%+.1f j"),
            }
        )
    else:
        st.info("Le rapprochement entre les délais et l'avancement n'est pas disponible : vérifie les données de délais et les saisies de recodification.")

    if not payload["delay_sector_impact"].empty:
        with st.expander("🔎 Analyse détaillée de l'impact par secteur et GF"):
            sector_cols = [c for c in [
                "DR", "Secteur", "GF", "Statut_Recodification", "Taux_Avancement", "Nb_Realise", "Reste_A_Faire",
                "Semaine_Derniere_Saisie", "Delai_Moyen_Courant", "Delai_N1_Comparable", "Variation_vs_N1",
                "Cible_Jours", "Ecart_Cible", "Nb_Periodes_Comparees", "Lecture_Impact"
            ] if c in payload["delay_sector_impact"].columns]
            st.dataframe(payload["delay_sector_impact"][sector_cols], use_container_width=True, hide_index=True)

    st.info(
        "Interprétation : la mise en regard des délais et des semaines de saisie permet d'observer une amélioration ou une dégradation "
        "pendant/à la suite de la recodification. Elle ne suffit pas à prouver un lien causal exclusif ; d'autres facteurs opérationnels "
        "peuvent également influencer les délais."
    )

    st.divider()
    st.markdown("### 5. Export du rapport mensuel")
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        try:
            report_excel_bytes = build_monthly_report_excel(payload)
            st.download_button(
                "⬇️ Télécharger le rapport et ses annexes Excel",
                data=report_excel_bytes,
                file_name=f"Rapport_DEXA_{report_cutoff:%Y_%m_%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_rapport_dexa_excel"
            )
        except Exception as exc:
            st.error(f"Impossible de préparer le classeur Excel : {exc}")
    with export_col2:
        report_html = build_monthly_report_html(payload)
        st.download_button(
            "⬇️ Télécharger le rapport imprimable (HTML)",
            data=report_html.encode("utf-8"),
            file_name=f"Rapport_DEXA_{report_cutoff:%Y_%m_%d}.html",
            mime="text/html",
            use_container_width=True,
            key="download_rapport_dexa_html"
        )
        st.caption("Ouvre le fichier HTML dans ton navigateur, puis utilise Imprimer → Enregistrer au format PDF pour obtenir une version PDF.")

