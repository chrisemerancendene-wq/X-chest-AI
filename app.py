import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image, ImageDraw
import json
import time
import io
import base64
import html
import tempfile
import streamlit.components.v1 as components
from supabase import create_client, Client

try:
    import pyreadstat
except Exception:
    pyreadstat = None

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
    generation_config = {
        "temperature": 0,
        "response_mime_type": "application/json",
    }
    MODEL_NAME = 'gemini-2.5-flash'
    model = genai.GenerativeModel(model_name=MODEL_NAME, generation_config=generation_config)

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


def afficher_critere(titre, resultat, justification):
    resultat_clean = str(resultat).strip().upper()
    is_ok = resultat_clean == "OUI"
    color = "#22c55e" if is_ok else "#ef4444"
    bg = "rgba(34, 197, 94, 0.14)" if is_ok else "rgba(239, 68, 68, 0.14)"
    border = "rgba(34, 197, 94, 0.45)" if is_ok else "rgba(239, 68, 68, 0.45)"
    st.markdown(
        f"""
        <div style="border-left: 4px solid {color}; background: {bg}; border: 1px solid {border}; padding: 0.85rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 1rem;">
                <strong style="font-size: 1rem; color: #ffffff;">{html.escape(titre)}</strong>
                <span style="background: {color}; color: white; padding: 0.2rem 0.65rem; border-radius: 999px; font-weight: 800;">{html.escape(resultat_clean)}</span>
            </div>
            <div style="margin-top: 0.45rem; color: #d7deea; line-height: 1.45;">{html.escape(str(justification))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def afficher_classification(conclusion, description):
    conclusion_clean = str(conclusion).strip()
    is_normal = conclusion_clean.lower() == "normal"
    color = "#22c55e" if is_normal else "#ef4444"
    bg = "rgba(34, 197, 94, 0.14)" if is_normal else "rgba(239, 68, 68, 0.14)"
    st.markdown(
        f"""
        <div style="background: {bg}; border: 1px solid {color}; border-radius: 12px; padding: 1rem; margin-bottom: 0.75rem;">
            <div style="font-size: 1rem; color: #d7deea;">Classification</div>
            <div style="font-size: 1.5rem; font-weight: 900; color: {color}; margin-top: 0.15rem;">{html.escape(conclusion_clean)}</div>
            <div style="margin-top: 0.75rem; color: #ffffff; line-height: 1.5;">{html.escape(str(description))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def afficher_conformite_globale(conclusion):
    conclusion_clean = str(conclusion).strip()
    is_ok = conclusion_clean.lower() == "conforme"
    color = "#22c55e" if is_ok else "#ef4444"
    bg = "rgba(34, 197, 94, 0.14)" if is_ok else "rgba(239, 68, 68, 0.14)"
    st.markdown(
        f"""
        <div style="background: {bg}; border: 1px solid {color}; border-radius: 10px; padding: 0.9rem 1rem; margin: 0.75rem 0 1rem 0;">
            <div style="font-size: 0.95rem; color: #d7deea;">Conclusion QC globale</div>
            <div style="font-size: 1.35rem; font-weight: 900; color: {color}; margin-top: 0.15rem;">{html.escape(conclusion_clean)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def afficher_image_zoomable(image, caption="Radiographie annotée"):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    components.html(
        f"""
        <div style="font-family: sans-serif; color: white; background: #0E1117; padding: 0;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 0.6rem;">
                <strong>{html.escape(caption)}</strong>
                <label style="font-size: 0.9rem; color: #cbd5e1;">Zoom : <span id="zoomValue">140%</span></label>
            </div>
            <input id="zoomSlider" type="range" min="80" max="300" value="140" step="10" style="width: 100%; margin-bottom: 0.75rem;">
            <div style="height: 620px; overflow: auto; border: 1px solid #1a3050; border-radius: 12px; background: #05070c;">
                <img id="radioImage" src="data:image/png;base64,{encoded}" style="width: 140%; max-width: none; display: block;">
            </div>
            <script>
                const slider = document.getElementById('zoomSlider');
                const image = document.getElementById('radioImage');
                const value = document.getElementById('zoomValue');
                slider.addEventListener('input', function() {{
                    image.style.width = slider.value + '%';
                    value.textContent = slider.value + '%';
                }});
            </script>
        </div>
        """,
        height=710,
    )


def dataframe_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="analyses")
    return output.getvalue()


def dataframe_to_sav_bytes(df):
    if pyreadstat is None:
        return None
    clean_df = df.copy()
    for column in clean_df.columns:
        clean_df[column] = clean_df[column].astype(str)
    with tempfile.NamedTemporaryFile(suffix=".sav", delete=True) as temp_file:
        pyreadstat.write_sav(clean_df, temp_file.name)
        temp_file.seek(0)
        return temp_file.read()


def concordance(valeur_ia, valeur_radio):
    return "Oui" if str(valeur_ia).strip().lower() == str(valeur_radio).strip().lower() else "Non"

# ══════════════════════════════════════════════════════
# PROMPT COMPLET ET PRÉCIS
# ══════════════════════════════════════════════════════
PROMPT = """Tu es un radiologue expert en contrôle qualité de radiographies thoraciques.
Ta priorité est d'abord le contrôle qualité du cliché, puis seulement le diagnostic.
Analyse cette radiographie thoracique de face (PA).
Réponds UNIQUEMENT en JSON strict, sans markdown, sans backticks, sans texte supplémentaire :

{
  "qualite": {
    "champ_radiographique": {"resultat": "OUI", "justification": "..."},
    "symetrie": {"resultat": "OUI", "justification": "..."},
    "inspiration": {"resultat": "OUI", "justification": "..."},
    "conclusion_globale": "Conforme ou Non conforme"
  },
  "diagnostic": {
    "conclusion": "Normal ou Pathologique",
    "description_semiologique": "Explication en 2 à 3 phrases des signes radiologiques observés."
  }
}

Critères d'évaluation :
- Champ radiographique : réponds "OUI" uniquement si les deux apex pulmonaires ET les deux culs de sac costo-diaphragmatiques sont entièrement visibles. Réponds "NON" si un apex est coupé, si un apex est partiellement hors champ, si un cul de sac costo-diaphragmatique est coupé, si la base pulmonaire est tronquée, ou si tu as un doute.
- Symétrie : les bords internes des clavicules sont-ils équidistants des apophyses épineuses ?
- Inspiration : au moins 7 à 9 arcs costaux postérieurs sont-ils visibles ?
- Conclusion QC globale : réponds exactement "Conforme" si et seulement si champ_radiographique, symetrie et inspiration sont tous les trois à "OUI". Si au moins un seul critère est à "NON", réponds exactement "Non conforme".
- Diagnostic : la conclusion doit être exactement "Normal" ou "Pathologique".

Règles strictes pour le champ radiographique :
- Si le bord supérieur de l'image coupe les sommets pulmonaires, champ_radiographique = "NON".
- Si le bord inférieur ou latéral de l'image coupe un angle costo-diaphragmatique, champ_radiographique = "NON".
- Si les apex ou les culs de sac ne sont pas visibles clairement, champ_radiographique = "NON".
- Ne déduis pas qu'un élément est visible s'il est hors champ. Ne sois pas permissif.
- Dans la justification du champ, cite explicitement les apex et les culs de sac costo-diaphragmatiques."""


def dessiner_reperes_visuels(image, data, params=None):
    annotated = image.convert("RGB").copy()
    draw = ImageDraw.Draw(annotated)
    width, height = annotated.size
    line_width = max(3, width // 180)
    qc = data.get("qualite", {})
    params = params or {}

    def px(value):
        return int(float(value) * width / 1000)

    def py(value):
        return int(float(value) * height / 1000)

    def resultat(critere):
        valeur = qc.get(critere, {}).get("resultat", "")
        return str(valeur).upper() if valeur else "?"

    # Les repères de qualité sont dessinés avec des proportions anatomiques
    # simples pour éviter les coordonnées trop variables renvoyées par l'IA.
    field_color = (190, 120, 255)
    field_left = px(params.get("field_left", 80))
    field_right = px(params.get("field_right", 920))
    top_y = py(params.get("field_top", 80))
    bottom_y = py(params.get("field_bottom", 920))
    draw.rectangle((field_left, top_y, field_right, bottom_y), outline=field_color, width=line_width)
    draw.text((field_left + 8, top_y + 8), f"Champ radiographique: {resultat('champ_radiographique')}", fill=field_color)
    draw.text((field_left + 8, top_y + py(40)), "apex visibles", fill=field_color)
    draw.text((field_left + 8, bottom_y - py(50)), "culs-de-sac costo-diaphragmatiques", fill=field_color)

    mid_x = px(params.get("axis_x", 500))
    draw.line((mid_x, top_y, mid_x, bottom_y), fill=(0, 180, 255), width=line_width)
    draw.text((mid_x + 10, top_y), f"Symetrie: {resultat('symetrie')}", fill=(0, 180, 255))
    draw.text((mid_x + 10, top_y + py(40)), "axe epineux median", fill=(0, 180, 255))

    clav_y = params.get("clavicle_y", 230)
    clav_width = params.get("clavicle_width", 190)
    clav_gap = params.get("clavicle_gap", 35)
    clav_slope = params.get("clavicle_slope", 55)
    left_clavicle = (px(params.get("axis_x", 500) - clav_width), py(clav_y), px(params.get("axis_x", 500) - clav_gap), py(clav_y + clav_slope))
    right_clavicle = (px(params.get("axis_x", 500) + clav_width), py(clav_y), px(params.get("axis_x", 500) + clav_gap), py(clav_y + clav_slope))
    draw.line(left_clavicle, fill=(255, 210, 0), width=line_width)
    draw.line(right_clavicle, fill=(255, 210, 0), width=line_width)
    draw.line((left_clavicle[2], left_clavicle[3], mid_x, left_clavicle[3]), fill=(255, 210, 0), width=max(1, line_width // 2))
    draw.line((right_clavicle[2], right_clavicle[3], mid_x, right_clavicle[3]), fill=(255, 210, 0), width=max(1, line_width // 2))
    draw.text((px(params.get("axis_x", 500) - 250), py(clav_y - 50)), "clavicules equidistantes de l'axe", fill=(255, 210, 0))

    rib_color = (0, 255, 120)
    rib_count = int(params.get("rib_count", 7))
    rib_top = params.get("rib_top", 350)
    rib_spacing = params.get("rib_spacing", 75)
    rib_width = params.get("rib_width", 190)
    rib_height = params.get("rib_height", 300)
    for side in (params.get("left_rib_center", 330), params.get("right_rib_center", 670)):
        for i in range(rib_count):
            y = rib_top + i * rib_spacing
            bbox = (
                px(side - rib_width),
                py(y - 120),
                px(side + rib_width),
                py(y - 120 + rib_height),
            )
            draw.arc(bbox, start=205, end=335, fill=rib_color, width=line_width)
            if side < 500:
                draw.text((px(side - rib_width - 35), py(y + 20)), str(i + 1), fill=rib_color)
    draw.text((px(80), py(620)), f"Inspiration: {resultat('inspiration')} - {rib_count} arcs posterieurs", fill=rib_color)

    def point(coord):
        x = max(0, min(1000, float(coord[0])))
        y = max(0, min(1000, float(coord[1])))
        return int(x * width / 1000), int(y * height / 1000)

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

    diagnostic = data.get("diagnostic", {})
    conclusion = str(diagnostic.get("conclusion", "")).lower()

    if not params.get("show_pathology_arrow", False) or "path" not in conclusion:
        return annotated

    arrow(
        [params.get("arrow_start_x", 850), params.get("arrow_start_y", 250)],
        [params.get("arrow_end_x", 650), params.get("arrow_end_y", 430)],
        (255, 40, 40),
    )
    draw.text((px(params.get("arrow_start_x", 850)) + 8, py(params.get("arrow_start_y", 250)) + 8), "zone suspecte", fill=(255, 40, 40))
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

    repere_params = {
        "field_left": 80, "field_right": 920, "field_top": 80, "field_bottom": 920,
        "axis_x": 500, "clavicle_y": 230, "clavicle_width": 190, "clavicle_gap": 35,
        "clavicle_slope": 55, "rib_count": 7, "rib_top": 350, "rib_spacing": 75,
        "rib_width": 190, "rib_height": 300, "left_rib_center": 330, "right_rib_center": 670,
        "show_pathology_arrow": False, "arrow_start_x": 850, "arrow_start_y": 250,
        "arrow_end_x": 650, "arrow_end_y": 430,
    }

    if img_file:
        img_file.seek(0)
        img_preview = Image.open(img_file)
        st.image(img_preview, caption=f"Radio chargée — {p_id}", use_container_width=True)

        with st.expander("🎯 Réglage précis des repères visuels", expanded=False):
            st.caption("Ajustez les repères avant ou après l'analyse. Les valeurs sont normalisées de 0 à 1000.")
            col_a, col_b = st.columns(2)
            with col_a:
                repere_params["field_left"] = st.slider("Champ - limite gauche", 0, 400, 80, 5)
                repere_params["field_top"] = st.slider("Champ - limite haute", 0, 300, 80, 5)
                repere_params["axis_x"] = st.slider("Axe médian", 350, 650, 500, 5)
                repere_params["clavicle_y"] = st.slider("Hauteur des clavicules", 100, 400, 230, 5)
                repere_params["rib_top"] = st.slider("Début des arcs costaux", 200, 550, 350, 5)
                repere_params["rib_count"] = st.slider("Nombre d'arcs affichés", 5, 9, 7, 1)
            with col_b:
                repere_params["field_right"] = st.slider("Champ - limite droite", 600, 1000, 920, 5)
                repere_params["field_bottom"] = st.slider("Champ - limite basse", 650, 1000, 920, 5)
                repere_params["clavicle_width"] = st.slider("Longueur visuelle des clavicules", 80, 300, 190, 5)
                repere_params["clavicle_slope"] = st.slider("Inclinaison des clavicules", 0, 120, 55, 5)
                repere_params["rib_spacing"] = st.slider("Espacement des arcs", 35, 110, 75, 5)
                repere_params["rib_width"] = st.slider("Largeur des arcs", 80, 280, 190, 5)

            repere_params["show_pathology_arrow"] = st.checkbox("Afficher une flèche rouge de pathologie", value=False)
            if repere_params["show_pathology_arrow"]:
                col_c, col_d = st.columns(2)
                with col_c:
                    repere_params["arrow_start_x"] = st.slider("Flèche - départ X", 0, 1000, 850, 5)
                    repere_params["arrow_start_y"] = st.slider("Flèche - départ Y", 0, 1000, 250, 5)
                with col_d:
                    repere_params["arrow_end_x"] = st.slider("Flèche - pointe X", 0, 1000, 650, 5)
                    repere_params["arrow_end_y"] = st.slider("Flèche - pointe Y", 0, 1000, 430, 5)

            st.image(
                dessiner_reperes_visuels(img_preview, {}, repere_params),
                caption="Aperçu des repères réglables",
                use_container_width=True,
            )

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

                    criteres_qc = [
                        str(qc['champ_radiographique']['resultat']).strip().upper(),
                        str(qc['symetrie']['resultat']).strip().upper(),
                        str(qc['inspiration']['resultat']).strip().upper(),
                    ]
                    qc['conclusion_globale'] = "Conforme" if all(c == "OUI" for c in criteres_qc) else "Non conforme"

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
                        "conclusion_qc_radiologue": "En attente",
                        "diagnostic": diag['conclusion'],
                        "description": diag['description_semiologique']
                    }

                    image_buffer = io.BytesIO()
                    img.save(image_buffer, format="PNG")
                    st.session_state["last_analysis_data"] = data
                    st.session_state["last_analysis_image"] = image_buffer.getvalue()

                    if "recent_analyses" not in st.session_state:
                        st.session_state["recent_analyses"] = []
                    st.session_state["recent_analyses"].insert(0, row_data)
                    st.session_state["recent_analyses"] = st.session_state["recent_analyses"][:10]

                    st.success(f"✅ Analyse terminée pour {p_id}")

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

    if "last_analysis_data" in st.session_state and "last_analysis_image" in st.session_state:
        data = st.session_state["last_analysis_data"]
        qc = data["qualite"]
        diag = data["diagnostic"]
        img_result = Image.open(io.BytesIO(st.session_state["last_analysis_image"]))

        st.markdown("### Résultat de l'analyse")
        img_annotee = dessiner_reperes_visuels(img_result, data, repere_params)
        afficher_image_zoomable(img_annotee, caption="Radiographie annotée avec repères visuels")

        st.markdown("### Résultats qualité")
        afficher_critere(
            "Champ radiographique",
            qc['champ_radiographique']['resultat'],
            qc['champ_radiographique']['justification'],
        )
        afficher_critere(
            "Symétrie",
            qc['symetrie']['resultat'],
            qc['symetrie']['justification'],
        )
        afficher_critere(
            "Inspiration",
            qc['inspiration']['resultat'],
            qc['inspiration']['justification'],
        )
        afficher_conformite_globale(qc['conclusion_globale'])

        st.markdown("### Lecture des repères visuels")
        st.markdown(
            "- **Violet :** vérifie que le champ inclut les apex et les culs-de-sac costo-diaphragmatiques.\n"
            "- **Bleu/jaune :** compare l'axe médian aux clavicules pour juger la rotation et la symétrie.\n"
            "- **Vert :** matérialise le comptage des arcs costaux postérieurs pour l'inspiration.\n"
            "- **Rouge :** flèche manuelle à activer seulement si vous voulez marquer une zone suspecte."
        )

        st.markdown("### Diagnostic")
        afficher_classification(diag['conclusion'], diag['description_semiologique'])

        if st.checkbox("Afficher les données techniques JSON", value=False):
            st.json(data)

with col2:
    st.subheader("📜 Historique des analyses")
    history_rows = []
    try:
        if supabase is None:
            st.info("En attente de configuration Supabase...")
        else:
            history = supabase.table("analyses").select("*").order('created_at', desc=True).limit(1000).execute()
            if history.data:
                history_rows = history.data
                for row in history.data[:10]:
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

    if history_rows:
        st.markdown("### Validation radiologue différée")
        selected_row = st.selectbox(
            "Choisir une analyse à valider",
            history_rows,
            format_func=lambda row: f"{row.get('patient_id', 'Sans ID')} - IA: {row.get('diagnostic', 'N/A')} - QC: {row.get('conclusion_qc', 'N/A')}",
        )

        if selected_row:
            st.caption("Renseignez ici le compte rendu radiologue lorsque vous l'obtenez. La ligne Supabase existante sera mise à jour.")
            champ_radio = st.selectbox(
                "Champ radiographique radiologue",
                ["OUI", "NON"],
                key="champ_radio_validation",
            )
            sym_radio = st.selectbox(
                "Symétrie radiologue",
                ["OUI", "NON"],
                key="sym_radio_validation",
            )
            insp_radio = st.selectbox(
                "Inspiration radiologue",
                ["OUI", "NON"],
                key="insp_radio_validation",
            )
            qc_radio = "Conforme" if all(v == "OUI" for v in [champ_radio, sym_radio, insp_radio]) else "Non conforme"
            diag_radio = st.selectbox(
                "Diagnostic radiologue",
                ["Normal", "Pathologique"],
                key="diag_radio_validation",
            )
            commentaire_radio = st.text_area(
                "Commentaire / conclusion radiologue",
                key="commentaire_radio_validation",
            )
            afficher_conformite_globale(qc_radio)

            if st.button("💾 Enregistrer la validation radiologue"):
                update_data = {
                    "champ_radiographique_radiologue": champ_radio,
                    "symetrie_radiologue": sym_radio,
                    "inspiration_radiologue": insp_radio,
                    "conclusion_qc_radiologue": qc_radio,
                    "diagnostic_radiologue": diag_radio,
                    "commentaire_radiologue": commentaire_radio,
                    "concordance_champ": concordance(selected_row.get("champ_radiographique"), champ_radio),
                    "concordance_symetrie": concordance(selected_row.get("symetrie"), sym_radio),
                    "concordance_inspiration": concordance(selected_row.get("inspiration"), insp_radio),
                    "concordance_qc": concordance(selected_row.get("conclusion_qc"), qc_radio),
                    "concordance_diagnostic": concordance(selected_row.get("diagnostic"), diag_radio),
                    "statut_validation": "Validé",
                }

                try:
                    query = supabase.table("analyses").update(update_data)
                    if selected_row.get("id") is not None:
                        query = query.eq("id", selected_row["id"])
                    else:
                        query = query.eq("patient_id", selected_row["patient_id"])
                    query.execute()
                    st.success("Validation radiologue enregistrée avec succès.")
                    st.rerun()
                except Exception as update_error:
                    st.error(f"Impossible d'enregistrer la validation radiologue : {update_error}")

    export_rows = history_rows if history_rows else local_history
    if export_rows:
        st.markdown("### Export des données")
        export_df = pd.DataFrame(export_rows)

        try:
            excel_bytes = dataframe_to_excel_bytes(export_df)
            st.download_button(
                "📥 Télécharger en Excel (.xlsx)",
                data=excel_bytes,
                file_name="historique_analyses_radioia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as export_error:
            st.warning(f"Export Excel indisponible : {export_error}")

        csv_bytes = export_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "📥 Télécharger en CSV compatible SPSS",
            data=csv_bytes,
            file_name="historique_analyses_radioia_spss.csv",
            mime="text/csv",
        )

        sav_bytes = dataframe_to_sav_bytes(export_df)
        if sav_bytes:
            st.download_button(
                "📥 Télécharger en SPSS (.sav)",
                data=sav_bytes,
                file_name="historique_analyses_radioia.sav",
                mime="application/octet-stream",
            )
        else:
            st.caption("Pour obtenir un fichier SPSS .sav direct, ajoutez `pyreadstat` dans requirements.txt. Sinon, le CSV s'importe dans SPSS.")
