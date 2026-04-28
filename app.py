import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import json
from supabase import create_client, Client

# ══════════════════════════════════════════════════════
# CONFIGURATION DE LA PAGE
# st.set_page_config doit être la première commande Streamlit.
# ══════════════════════════════════════════════════════
st.set_page_config(page_title="RadioIA — Jamot", layout="wide", page_icon="🫁")

# ══════════════════════════════════════════════════════
# CONFIGURATION — SECRETS & IA
# ══════════════════════════════════════════════════════
supabase = None
model = None

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_KEY"]

    # Connexion Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Configuration Gemini
    genai.configure(api_key=GEMINI_KEY)
    
    # On utilise un modèle Flash récent compatible avec generateContent.
    MODEL_NAME = 'gemini-2.5-flash'
    model = genai.GenerativeModel(model_name=MODEL_NAME)

except Exception as e:
    st.error(f"Erreur de configuration (Vérifiez vos Secrets) : {e}")

# ══════════════════════════════════════════════════════
# DESIGN DARK MODE
# ══════════════════════════════════════════════════════
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
    "champ_radiographique": {"resultat": "OUI", "justification": "..."},
    "symetrie": {"resultat": "OUI", "justification": "..."},
    "inspiration": {"resultat": "OUI", "justification": "..."},
    "conclusion_globale": "Acceptable"
  },
  "diagnostic": {
    "conclusion": "Normale",
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

with col1:
    st.subheader("📝 Identification")
    p_id = st.text_input("🏷️ Identifiant radio", placeholder="RAD_001")
    p_age = st.number_input("🎂 Âge du patient", min_value=18, max_value=120, value=30)
    p_sexe = st.selectbox("👤 Sexe", ["Masculin", "Féminin"])
    img_file = st.file_uploader("🩻 Uploader la radiographie", type=['jpg', 'jpeg', 'png'])

    if img_file:
        img_file.seek(0)
        img_preview = Image.open(img_file)
        st.image(img_preview, caption=f"Radio chargée — {p_id}", use_container_width=True)

    if st.button("🚀 ANALYSER ET SAUVEGARDER"):
        if model is None or supabase is None:
            st.error("⚠️ Configuration incomplète : vérifiez vos Secrets Streamlit.")
        elif not img_file:
            st.warning("⚠️ Veuillez uploader une radiographie.")
        elif not p_id:
            st.warning("⚠️ Veuillez renseigner l'identifiant radio.")
        else:
            img_file.seek(0)
            img = Image.open(img_file)
            with st.spinner("🔬 Analyse en cours..."):
                try:
                    response = model.generate_content([PROMPT, img])
                    
                    # Nettoyage du JSON au cas où l'IA ajoute des balises.
                    clean_text = response.text.replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean_text)

                    # Extraction
                    qc = data['qualite']
                    diag = data['diagnostic']

                    # Affichage
                    st.success(f"✅ Analyse terminée pour {p_id}")
                    st.json(data) # Optionnel : afficher le JSON brut pour vérifier

                    # Sauvegarde Supabase
                    supabase.table("analyses").insert({
                        "patient_id": p_id,
                        "age": p_age,
                        "sexe": p_sexe,
                        "champ_radiographique": qc['champ_radiographique']['resultat'],
                        "champ_justification": qc['champ_radiographique']['justification'],
                        "symetrie": qc['symetrie']['resultat'],
                        "symetrie_justification": qc['symetrie']['justification'],
                        "inspiration": qc['inspiration']['resultat'],
                        "inspiration_justification": qc['inspiration']['justification'],
                        "conclusion_qc": qc['conclusion_globale'],
                        "diagnostic": diag['conclusion'],
                        "description": diag['description_semiologique']
                    }).execute()
                    
                    st.success("💾 Données sauvegardées avec succès !")

                except json.JSONDecodeError as e:
                    st.error(f"⚠️ L'IA n'a pas renvoyé un JSON valide : {e}")
                    if 'response' in locals():
                        st.code(response.text, language="text")
                except KeyError as e:
                    st.error(f"⚠️ Clé manquante dans la réponse JSON : {e}")
                    if 'data' in locals():
                        st.json(data)
                except Exception as e:
                    st.error(f"⚠️ Erreur lors de l'analyse : {e}")

with col2:
    st.subheader("📜 Historique des analyses")
    try:
        if supabase is None:
            st.info("En attente de configuration Supabase...")
        else:
            history = supabase.table("analyses").select("*").order('created_at', desc=True).limit(10).execute()
            if history.data:
                for row in history.data:
                    with st.expander(f"📁 {row['patient_id']} - {row['diagnostic']}"):
                        st.write(f"**Description :** {row['description']}")
            else:
                st.info("Aucun historique disponible.")
    except Exception as e:
        st.info(f"En attente de données... ({e})")
