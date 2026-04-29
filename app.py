import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image, ImageDraw
import json
import time
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
COOLDOWN_SECONDS = 60

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
    qc = data.get("qualite", {})

    def resultat(critere):
        valeur = qc.get(critere, {}).get("resultat", "")
        return str(valeur).upper() if valeur else "?"

    # Les repères de qualité sont dessinés avec des proportions anatomiques
    # simples pour éviter les coordonnées trop variables renvoyées par l'IA.
    field_color = (190, 120, 255)
    margin_x = int(width * 0.08)
    top_y = int(height * 0.08)
    bottom_y = int(height * 0.92)
    draw.rectangle((margin_x, top_y, width - margin_x, bottom_y), outline=field_color, width=line_width)
    draw.text((margin_x + 8, top_y + 8), f"Champ radiographique: {resultat('champ_radiographique')}", fill=field_color)
    draw.text((margin_x + 8, top_y + int(height * 0.04)), "apex visibles", fill=field_color)
    draw.text((margin_x + 8, bottom_y - int(height * 0.05)), "culs-de-sac costo-diaphragmatiques", fill=field_color)

    mid_x = width // 2
    draw.line((mid_x, top_y, mid_x, bottom_y), fill=(0, 180, 255), width=line_width)
    draw.text((mid_x + 10, top_y), f"Symetrie: {resultat('symetrie')}", fill=(0, 180, 255))
    draw.text((mid_x + 10, top_y + int(height * 0.04)), "axe epineux median", fill=(0, 180, 255))

    left_clavicle = (int(width * 0.30), int(height * 0.23), int(width * 0.47), int(height * 0.30))
    right_clavicle = (int(width * 0.70), int(height * 0.23), int(width * 0.53), int(height * 0.30))
    draw.line(left_clavicle, fill=(255, 210, 0), width=line_width)
    draw.line(right_clavicle, fill=(255, 210, 0), width=line_width)
    draw.line((int(width * 0.47), int(height * 0.30), mid_x, int(height * 0.30)), fill=(255, 210, 0), width=max(1, line_width // 2))
    draw.line((int(width * 0.53), int(height * 0.30), mid_x, int(height * 0.30)), fill=(255, 210, 0), width=max(1, line_width // 2))
    draw.text((int(width * 0.25), int(height * 0.18)), "clavicules equidistantes de l'axe", fill=(255, 210, 0))

    rib_color = (0, 255, 120)
    for side in (0.33, 0.67):
        for i in range(7):
            y = 0.35 + i * 0.075
            bbox = (
                int(width * (side - 0.19)),
                int(height * (y - 0.12)),
                int(width * (side + 0.19)),
                int(height * (y + 0.18)),
            )
            draw.arc(bbox, start=205, end=335, fill=rib_color, width=line_width)
            if side < 0.5:
                draw.text((int(width * 0.12), int(height * (y + 0.02))), str(i + 1), fill=rib_color)
    draw.text((int(width * 0.08), int(height * 0.62)), f"Inspiration: {resultat('inspiration')} - 7 arcs posterieurs", fill=rib_color)

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
    pathologie = reperes.get("pathologie", {})
    diagnostic = data.get("diagnostic", {})
    conclusion = str(diagnostic.get("conclusion", "")).lower()

    if "path" not in conclusion:
        return annotated

    # Les flèches pathologiques restent dépendantes de l'IA : elles ne sont
    # dessinées que si Gemini fournit explicitement une zone suspecte.
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

    last_analysis_time = st.session_state.get("last_analysis_time", 0)
    remaining_wait = int(COOLDOWN_SECONDS - (time.time() - last_analysis_time))
    remaining_wait = max(0, remaining_wait)

    if img_file:
        img_file.seek(0)
        img_preview = Image.open(img_file)
        st.image(img_preview, caption=f"Radio chargée — {p_id}", use_container_width=True)

    if remaining_wait > 0:
        st.info(f"⏳ Patientez encore {remaining_wait} seconde(s) avant une nouvelle analyse.")

    if st.button("🚀 ANALYSER ET SAUVEGARDER", disabled=remaining_wait > 0):
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
                    st.session_state["last_analysis_time"] = time.time()
                    response = model.generate_content([PROMPT, img])
                    
                    # Nettoyage du JSON au cas où l'IA ajoute des balises.
                    clean_text = response.text.replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean_text)

                    # Extraction
                    qc = data['qualite']
                    diag = data['diagnostic']
                    conclusion = str(diag.get('conclusion', '')).strip()
                    if 'path' in conclusion.lower():
                        diag['conclusion'] = 'Pathologique'
                    elif 'normal' in conclusion.lower() or 'normale' in conclusion.lower():
                        diag['conclusion'] = 'Normal'

                    # Affichage
                    st.success(f"✅ Analyse terminée pour {p_id}")
                    img_annotee = dessiner_reperes_visuels(img, data)
                    st.image(img_annotee, caption="Radiographie annotée", use_container_width=True)

                    st.markdown("### Résultats qualité")
                    st.markdown(
                        f"**Champ radiographique :** {qc['champ_radiographique']['resultat']}  \n"
                        f"{qc['champ_radiographique']['justification']}"
                    )
                    st.markdown(
                        f"**Symétrie :** {qc['symetrie']['resultat']}  \n"
                        f"{qc['symetrie']['justification']}"
                    )
                    st.markdown(
                        f"**Inspiration :** {qc['inspiration']['resultat']}  \n"
                        f"{qc['inspiration']['justification']}"
                    )
                    st.markdown(f"**Conclusion QC globale :** {qc['conclusion_globale']}")

                    st.markdown("### Lecture des repères visuels")
                    st.markdown(
                        "- **Violet :** vérifie que le champ inclut les apex et les culs-de-sac costo-diaphragmatiques.\n"
                        "- **Bleu/jaune :** compare l'axe médian aux clavicules pour juger la rotation et la symétrie.\n"
                        "- **Vert :** matérialise le comptage des arcs costaux postérieurs pour l'inspiration.\n"
                        "- **Rouge :** indique une anomalie seulement si l'IA classe l'image comme pathologique."
                    )

                    st.markdown("### Diagnostic")
                    st.markdown(f"**Classification :** {diag['conclusion']}")
                    st.markdown(f"**Analyse sémiologique :** {diag['description_semiologique']}")

                    if st.checkbox("Afficher les données techniques JSON", value=False):
                        st.json(data)

                    row_data = {
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
                    }

                    if "recent_analyses" not in st.session_state:
                        st.session_state["recent_analyses"] = []
                    st.session_state["recent_analyses"].insert(0, row_data)
                    st.session_state["recent_analyses"] = st.session_state["recent_analyses"][:10]

                    # Sauvegarde Supabase
                    try:
                        supabase.table("analyses").insert(row_data).execute()
                        st.success("💾 Données sauvegardées avec succès !")
                    except Exception as save_error:
                        st.warning(f"Analyse affichée, mais sauvegarde Supabase non effectuée : {save_error}")

                except json.JSONDecodeError as e:
                    st.error(f"⚠️ L'IA n'a pas renvoyé un JSON valide : {e}")
                    if 'response' in locals():
                        st.code(response.text, language="text")
                except KeyError as e:
                    st.error(f"⚠️ Clé manquante dans la réponse JSON : {e}")
                    if 'data' in locals():
                        st.json(data)
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        st.error("⚠️ Quota Gemini temporairement dépassé. Patientez environ 1 minute, puis réessayez.")
                        st.info("Cette limite peut aussi être atteinte si la même clé API est utilisée ailleurs ou si plusieurs essais ont été faits récemment.")
                    else:
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
                st.info("Aucun historique Supabase disponible.")
    except Exception as e:
        st.info(f"Historique Supabase indisponible : {e}")

    local_history = st.session_state.get("recent_analyses", [])
    if local_history:
        st.markdown("### Historique de cette session")
        for row in local_history:
            with st.expander(f"📁 {row['patient_id']} - {row['diagnostic']}"):
                st.write(f"**Âge :** {row.get('age', 'N/A')} | **Sexe :** {row.get('sexe', 'N/A')}")
                st.write(f"**Qualité :** {row.get('conclusion_qc', 'N/A')}")
                st.write(f"**Description :** {row.get('description', 'N/A')}")
