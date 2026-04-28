import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image, ImageDraw
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
    "conclusion": "Normal ou Pathologique",
    "description_semiologique": "Explication en 2 à 3 phrases des signes radiologiques observés."
  },
  "reperes_visuels": {
    "symetrie": {
      "ligne_mediane": [[500, 80], [500, 900]],
      "lignes_clavicules": [
        [[380, 210], [470, 260]],
        [[620, 210], [530, 260]]
      ]
    },
    "inspiration": {
      "arcs_costaux": [
        {"bbox": [180, 180, 480, 520], "start": 210, "end": 330},
        {"bbox": [520, 180, 820, 520], "start": 210, "end": 330}
      ]
    },
    "pathologie": {
      "fleches": [
        {"depart": [850, 250], "arrivee": [650, 430], "label": "anomalie suspecte"}
      ]
    }
  }
}

Critères d'évaluation :
- Champ radiographique : les apex pulmonaires et les culs de sac costo-diaphragmatiques sont-ils entièrement visibles ?
- Symétrie : les bords internes des clavicules sont-ils équidistants des apophyses épineuses ?
- Inspiration : au moins 7 à 9 arcs costaux postérieurs sont-ils visibles ?
- Diagnostic : la conclusion doit être exactement "Normal" ou "Pathologique".

Instructions pour les repères visuels :
- Utilise des coordonnées normalisées de 0 à 1000, où [0,0] correspond au coin supérieur gauche de l'image et [1000,1000] au coin inférieur droit.
- Les repères doivent être approximatifs mais cohérents avec l'image.
- ligne_mediane illustre l'axe de symétrie thoracique.
- lignes_clavicules illustrent la comparaison des clavicules pour la symétrie.
- arcs_costaux illustre les arcs costaux visibles pour l'inspiration.
- fleches indique uniquement les anomalies visibles. Si aucune anomalie n'est visible, retourne "fleches": []."""


def dessiner_reperes_visuels(image, data):
    annotated = image.convert("RGB").copy()
    draw = ImageDraw.Draw(annotated)
    width, height = annotated.size
    line_width = max(3, width // 180)

    def point(coord):
        x = max(0, min(1000, float(coord[0])))
        y = max(0, min(1000, float(coord[1])))
        return int(x * width / 1000), int(y * height / 1000)

    def box(coords):
        x1, y1 = point(coords[:2])
        x2, y2 = point(coords[2:])
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def arrow(start, end, color):
        x1, y1 = point(start)
        x2, y2 = point(end)
        draw.line((x1, y1, x2, y2), fill=color, width=line_width)
        dx, dy = x2 - x1, y2 - y1
        length = max((dx * dx + dy * dy) ** 0.5, 1)
        ux, uy = dx / length, dy / length
        size = line_width * 5
        left = (x2 - ux * size - uy * size * 0.6, y2 - uy * size + ux * size * 0.6)
        right = (x2 - ux * size + uy * size * 0.6, y2 - uy * size - ux * size * 0.6)
        draw.polygon([(x2, y2), left, right], fill=color)

    reperes = data.get("reperes_visuels", {})
    symetrie = reperes.get("symetrie", {})
    inspiration = reperes.get("inspiration", {})
    pathologie = reperes.get("pathologie", {})

    if symetrie.get("ligne_mediane"):
        p1, p2 = symetrie["ligne_mediane"]
        draw.line((*point(p1), *point(p2)), fill=(0, 180, 255), width=line_width)

    for ligne in symetrie.get("lignes_clavicules", []):
        if len(ligne) == 2:
            draw.line((*point(ligne[0]), *point(ligne[1])), fill=(255, 210, 0), width=line_width)

    for arc in inspiration.get("arcs_costaux", []):
        if "bbox" in arc:
            draw.arc(
                box(arc["bbox"]),
                start=int(arc.get("start", 200)),
                end=int(arc.get("end", 340)),
                fill=(0, 255, 120),
                width=line_width,
            )

    for fleche in pathologie.get("fleches", []):
        if fleche.get("depart") and fleche.get("arrivee"):
            arrow(fleche["depart"], fleche["arrivee"], (255, 40, 40))
            label = fleche.get("label", "anomalie")
            tx, ty = point(fleche["depart"])
            draw.text((tx + 8, ty + 8), label, fill=(255, 40, 40))

    return annotated

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
                    img_annotee = dessiner_reperes_visuels(img, data)
                    st.image(img_annotee, caption="Radiographie avec repères visuels proposés par l'IA", use_container_width=True)
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
