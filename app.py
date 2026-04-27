import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import json
from supabase import create_client, Client

# ══════════════════════════════════════════════════════
# CONFIGURATION — SECRETS (ne pas modifier)
# ══════════════════════════════════════════════════════
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_KEY"]

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("⚠️ Erreur de configuration des Secrets. Vérifiez votre tableau de bord Streamlit.")
    st.stop()

# ══════════════════════════════════════════════════════
# DESIGN DARK MODE
# ══════════════════════════════════════════════════════
st.set_page_config(page_title="RadioIA — Jamot", layout="wide", page_icon="🫁")
st.markdown("""
<style>
.stApp { background-color: #0E1117; color: white; }
.stButton>button {
    background: linear-gradient(135deg, #2d7cf6, #00c2e0);
    color: white; border: none; border-radius: 10px;
    font-weight: 700; font-size: 1rem; padding: 0.6rem 1.2rem;
    width: 100%;
}
.stButton>button:hover { opacity: 0.88; }
.result-card {
    background: #1a2235; border-radius: 12px;
    padding: 1rem; margin-bottom: 0.75rem;
    border: 1px solid #1a3050;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# PROMPT COMPLET ET PRÉCIS
# ══════════════════════════════════════════════════════
PROMPT = """Tu es un radiologue expert en analyse de radiographies thoraciques.
Analyse cette radiographie thoracique de face (PA).
Réponds UNIQUEMENT en JSON strict, sans markdown, sans backticks, sans texte supplémentaire :

{
  "qualite": {
    "champ_radiographique": {"resultat": "OUI" ou "NON", "justification": "..."},
    "symetrie": {"resultat": "OUI" ou "NON", "justification": "..."},
    "inspiration": {"resultat": "OUI" ou "NON", "justification": "..."},
    "conclusion_globale": "Acceptable" ou "Non acceptable"
  },
  "diagnostic": {
    "conclusion": "Normale" ou "Pathologique",
    "description_semiologique": "Explication en 2 à 3 phrases des signes radiologiques observés."
  }
}

Critères d'évaluation :
- Champ radiographique : les apex pulmonaires et les culs de sac costo-diaphragmatiques sont-ils entièrement visibles ?
- Symétrie : les bords internes des clavicules sont-ils équidistants des apophyses épineuses ?
- Inspiration : au moins 7 à 9 arcs costaux postérieurs sont-ils visibles ?"""

# ══════════════════════════════════════════════════════
# TITRE
# ══════════════════════════════════════════════════════
st.markdown("# 🫁 RadioIA — Assistant Radiographie Thoracique")
st.markdown("*Mémoire de Master en Radiologie et Imagerie Médicale — Hôpital Jamot de Yaoundé*")
st.divider()

# ══════════════════════════════════════════════════════
# LAYOUT PRINCIPAL
# ══════════════════════════════════════════════════════
col1, col2 = st.columns([1, 1.5])

# ──────────────────────────────────────────────────────
# COLONNE GAUCHE — Formulaire + Upload
# ──────────────────────────────────────────────────────
with col1:
    st.subheader("📝 Identification de la radiographie")

    p_id = st.text_input("🏷️ Identifiant radio", placeholder="RAD_001")
    p_age = st.number_input("🎂 Âge du patient", min_value=18, max_value=120, value=30)
    p_sexe = st.selectbox("👤 Sexe", ["Masculin", "Féminin"])
    img_file = st.file_uploader("🩻 Uploader la radiographie", type=['jpg', 'jpeg', 'png'])

    # Aperçu de l'image uploadée
    if img_file:
        img_preview = Image.open(img_file)
        st.image(img_preview, caption=f"Radio chargée — {p_id}", use_column_width=True)

    # Bouton analyser
    if st.button("🚀 ANALYSER ET SAUVEGARDER"):
        if not img_file:
            st.warning("⚠️ Veuillez uploader une radiographie.")
        elif not p_id:
            st.warning("⚠️ Veuillez renseigner l'identifiant radio.")
        else:
            img = Image.open(img_file)

            with st.spinner("🔬 Gemini analyse la radiographie..."):
                try:
                    # ── Appel API Gemini ──
                    response = model.generate_content([PROMPT, img])
                    raw = response.text.replace('```json', '').replace('```', '').strip()
                    data = json.loads(raw)

                    # ── Extraction des résultats ──
                    qc = data['qualite']
                    diag = data['diagnostic']

                    champ = qc['champ_radiographique']
                    symetrie = qc['symetrie']
                    inspiration = qc['inspiration']
                    conclusion_qc = qc['conclusion_globale']
                    classification = diag['conclusion']
                    description = diag['description_semiologique']

                    # ── Affichage des résultats ──
                    st.markdown("---")
                    st.markdown("### 📊 Résultats de l'analyse")

                    # Contrôle qualité
                    st.markdown("#### 📐 Contrôle Qualité")
                    qc_col1, qc_col2, qc_col3 = st.columns(3)

                    with qc_col1:
                        icon = "✅" if champ['resultat'] == "OUI" else "❌"
                        couleur = "success" if champ['resultat'] == "OUI" else "error"
                        getattr(st, couleur)(f"{icon} **Champ radio**\n\n{champ['resultat']}\n\n*{champ['justification']}*")

                    with qc_col2:
                        icon = "✅" if symetrie['resultat'] == "OUI" else "❌"
                        couleur = "success" if symetrie['resultat'] == "OUI" else "error"
                        getattr(st, couleur)(f"{icon} **Symétrie**\n\n{symetrie['resultat']}\n\n*{symetrie['justification']}*")

                    with qc_col3:
                        icon = "✅" if inspiration['resultat'] == "OUI" else "❌"
                        couleur = "success" if inspiration['resultat'] == "OUI" else "error"
                        getattr(st, couleur)(f"{icon} **Inspiration**\n\n{inspiration['resultat']}\n\n*{inspiration['justification']}*")

                    # Conclusion QC globale
                    if conclusion_qc == "Acceptable":
                        st.success(f"✅ **Conclusion QC globale : {conclusion_qc}**")
                    else:
                        st.error(f"❌ **Conclusion QC globale : {conclusion_qc}**")

                    st.markdown("---")

                    # Classification sémiologique
                    st.markdown("#### 🔍 Classification sémiologique")
                    if classification == "Normale":
                        st.success(f"## ✅ {classification}")
                    else:
                        st.error(f"## ⚠️ {classification}")

                    st.info(f"**📝 Justification de l'IA :**\n\n{description}")

                    st.markdown("---")

                    # ── Sauvegarde Supabase ──
                    supabase.table("analyses").insert({
                        "patient_id": p_id,
                        "age": p_age,
                        "sexe": p_sexe,
                        "champ_radiographique": champ['resultat'],
                        "champ_justification": champ['justification'],
                        "symetrie": symetrie['resultat'],
                        "symetrie_justification": symetrie['justification'],
                        "inspiration": inspiration['resultat'],
                        "inspiration_justification": inspiration['justification'],
                        "conclusion_qc": conclusion_qc,
                        "diagnostic": classification,
                        "description": description,
                        "classification_radiologue": "",
                        "conclusion_qc_radiologue": "",
                        "delai_minutes": None
                    }).execute()

                    st.success(f"✅ Analyse de **{p_id}** sauvegardée dans Supabase !")

                except json.JSONDecodeError:
                    st.error("⚠️ Réponse de l'IA non interprétable. Veuillez réessayer.")
                except Exception as e:
                    st.error(f"⚠️ Erreur : {str(e)}")

# ──────────────────────────────────────────────────────
# COLONNE DROITE — Historique
# ──────────────────────────────────────────────────────
with col2:
    st.subheader("📜 Historique des analyses")

    try:
        history = supabase.table("analyses").select("*").order('created_at', desc=True).limit(10).execute()

        if history.data:
            for row in history.data:
                icon = "✅" if row.get('diagnostic') == "Normale" else "⚠️"
                qc_icon = "✅" if row.get('conclusion_qc') == "Acceptable" else "❌"
                with st.expander(f"{icon} {row['patient_id']} — {row.get('diagnostic', '?')} | QC : {qc_icon} {row.get('conclusion_qc', '?')}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Âge :** {row.get('age', '?')} ans")
                        st.write(f"**Sexe :** {row.get('sexe', '?')}")
                        st.write(f"**Champ radio :** {row.get('champ_radiographique', '?')}")
                        st.write(f"**Symétrie :** {row.get('symetrie', '?')}")
                        st.write(f"**Inspiration :** {row.get('inspiration', '?')}")
                    with col_b:
                        st.write(f"**Conclusion QC :** {row.get('conclusion_qc', '?')}")
                        st.write(f"**Classification :** {row.get('diagnostic', '?')}")
                        st.write(f"**CR Radiologue :** {row.get('classification_radiologue') or '— à compléter'}")
                        st.write(f"**Délai (min) :** {row.get('delai_minutes') or '— à compléter'}")
                    st.caption(f"📝 {row.get('description', '')}")
        else:
            st.info("Aucune analyse effectuée pour le moment.")

    except Exception as e:
        st.error(f"Erreur de chargement de l'historique : {str(e)}")

    # ── Export CSV ──
    st.markdown("---")
    st.subheader("📊 Export des données")
    if st.button("⬇️ Télécharger toutes les analyses (CSV)"):
        try:
            all_data = supabase.table("analyses").select("*").order('created_at', desc=True).execute()
            if all_data.data:
                df = pd.DataFrame(all_data.data)
                cols = ['patient_id', 'age', 'sexe', 'champ_radiographique', 'symetrie',
                        'inspiration', 'conclusion_qc', 'diagnostic', 'description',
                        'classification_radiologue', 'conclusion_qc_radiologue', 'delai_minutes', 'created_at']
                df = df[[c for c in cols if c in df.columns]]
                df.columns = ['ID_Radio', 'Age', 'Sexe', 'Champ_IA', 'Symetrie_IA',
                              'Inspiration_IA', 'Conclusion_QC_IA', 'Classification_IA', 'Justification_IA',
                              'Classification_Radiologue', 'Conclusion_QC_Radiologue', 'Delai_minutes', 'Date']
                csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button(
                    label="📥 Cliquez ici pour télécharger",
                    data=csv,
                    file_name="RadioIA_Export.csv",
                    mime="text/csv"
                )
            else:
                st.info("Aucune donnée à exporter.")
        except Exception as e:
            st.error(f"Erreur d'export : {str(e)}")
