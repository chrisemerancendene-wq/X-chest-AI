import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import json
from supabase import create_client, Client

# RÉCUPÉRATION DES SECRETS (Configuration sécurisée)
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_KEY"]
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')
except Exception as e:
    st.error("Erreur de configuration des Secrets. Vérifiez votre tableau de bord Streamlit.")
    st.stop()

# DESIGN DARK MODE (Léo)
st.set_page_config(page_title="CXR Jamot", layout="wide")
st.markdown("<style>.stApp { background-color: #0E1117; color: white; }</style>", unsafe_allow_html=True)

st.title("🩻 Assistant Radio - Master 2")

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📝 Nouveau Patient")
    p_id = st.text_input("ID Radio")
    p_age = st.number_input("Âge", 0, 120, 25)
    p_sexe = st.selectbox("Sexe", ["Masculin", "Féminin"])
    img_file = st.file_uploader("Radio", type=['jpg', 'jpeg', 'png'])

    if st.button("🚀 ANALYSER ET SAUVEGARDER"):
        if img_file and p_id:
            img = Image.open(img_file)
            with st.spinner("Analyse en cours..."):
                prompt = "Analyse cette radio. Format JSON strict : qualite (objet: symetrie, inspiration, collimation) et diagnostic (objet: conclusion, description_semiologique). Pas de nom de maladie."
                response = model.generate_content([prompt, img])
                try:
                    data = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                    # Sauvegarde Supabase
                    supabase.table("analyses").insert({
                        "patient_id": p_id, "age": p_age, "sexe": p_sexe,
                        "qualite": data['qualite']['symetrie']['status'],
                        "diagnostic": data['diagnostic']['conclusion'],
                        "description": data['diagnostic']['description_semiologique']
                    }).execute()
                    st.success(f"Données de {p_id} sécurisées !")
                except:
                    st.error("Erreur d'analyse.")

with col2:
    st.subheader("📜 Historique")
    try:
        history = supabase.table("analyses").select("*").order('created_at', desc=True).limit(5).execute()
        for row in history.data:
            st.info(f"ID: {row['patient_id']} | {row['diagnostic']}")
    except:
        st.write("Aucune donnée.")
