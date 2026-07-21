import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as io
from datetime import datetime
import os

# Streamlit Page Config
st.set_page_config(
    page_title="Suivi Recodification - Sites & GF",
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

LISTE_COLLABORATEURS = [
    "Gokon Fabrice",
    "Taper Yasmine",
    "Konan Yao",
    "Kodjo Anick",
    "Gnahoua Kader"
]

DATA_SUIVI_FILE = "data_suivi_recodification.csv"
DATA_SITES_FILE = "data_referentiel_sites.csv"


def save_persistent_data():
    """Sauvegarde automatiquement les DataFrames dans des fichiers CSV locaux."""
    if "df_sites" in st.session_state:
        st.session_state.df_sites.to_csv(DATA_SITES_FILE, index=False, encoding="utf-8")
    if "df_suivi" in st.session_state:
        st.session_state.df_suivi.to_csv(DATA_SUIVI_FILE, index=False, encoding="utf-8")


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


st.title("📌 Suivi de Recodification des Sites par GF")
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

tab_dash, tab_saisie, tab_stock, tab_data = st.tabs([
    "📊 Dashboard & KPI",
    "📝 Saisie Production",
    "⚙️ Configuration Stocks Initial",
    "📁 Gestion des Données"
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