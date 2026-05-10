import streamlit as st

# PAGE CONFIG — DOIT ÊTRE EN PREMIER
st.set_page_config(page_title="RadioIA — Jamot", layout="wide", page_icon="🫁")

import google.generativeai as genai
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import json
import io
from datetime import datetime
from supabase import create_client, Client

# ══════════════════════════════════════════════════════
# INITIALISATION GEMINI (CACHÉE)
# ══════════════════════════════════════════════════════
@st.cache_resource
def initialiser_gemini(api_key):
    genai.configure(api_key=api_key)
    modeles_preferes = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash",
        "models/gemini-1.5-pro",
    ]
    modeles_disponibles = []
    for m in genai.list_models():
        methodes = getattr(m, "supported_generation_methods", [])
        if "generateContent" in methodes:
            modeles_disponibles.append(m.name)
    for nom in modeles_preferes:
        if nom in modeles_disponibles:
            return genai.GenerativeModel(model_name=nom), nom
    if modeles_disponibles:
        nom = modeles_disponibles[0]
        return genai.GenerativeModel(model_name=nom), nom
    raise RuntimeError("Aucun modèle compatible disponible.")

# ══════════════════════════════════════════════════════
# INITIALISATION SUPABASE (CACHÉE)
# ══════════════════════════════════════════════════════
@st.cache_resource
def initialiser_supabase(url, key):
    return create_client(url, key)

# ══════════════════════════════════════════════════════
# FONCTION POUR ANNOTER L'IMAGE
# ══════════════════════════════════════════════════════
def annoter_image(img, data):
    img_annotee = img.copy()
    draw = ImageDraw.Draw(img_annotee)
    W, H = img_annotee.size
    ep = max(3, int(min(W, H) / 200))

    try:
        taille_label = max(16, int(H / 32))
        taille_petit = max(14, int(H / 40))
        taille_bandeau = max(22, int(H / 18))
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", taille_label)
        petite_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", taille_petit)
        font_bandeau = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", taille_bandeau)
    except:
        font = ImageFont.load_default()
        petite_font = font
        font_bandeau = font

    qc = data.get('qualite', {})
    diag = data.get('diagnostic', {})
    classification = diag.get('classification', 'INDÉTERMINÉ')

    # 1. BANDEAU CLASSIFICATION
    bandeau_h = max(40, int(H / 12))
    if classification == "NORMAL":
        couleur_b = (0, 140, 50)
        texte_b = "NORMAL"
    elif classification == "PATHOLOGIQUE":
        couleur_b = (190, 20, 20)
        texte_b = "PATHOLOGIQUE"
    else:
        couleur_b = (140, 140, 0)
        texte_b = "INDÉTERMINÉ"
    draw.rectangle([0, 0, W, bandeau_h], fill=couleur_b)
    bbox_b = font_bandeau.getbbox(texte_b)
    tw_b = bbox_b[2] - bbox_b[0]
    draw.text(((W - tw_b) // 2, 8), texte_b, fill=(255, 255, 255), font=font_bandeau)

    # 2. CHAMP RADIOGRAPHIQUE
    bleu = (80, 160, 255)
    res_champ = qc.get('champ_radiographique', {}).get('resultat', '')
    couleur_champ = (0, 230, 0) if res_champ == "OUI" else (255, 80, 80)

    apex_y1 = bandeau_h + 5
    apex_y2 = int(H * 0.18)
    draw.rectangle([10, apex_y1, W - 10, apex_y2], outline=couleur_champ, width=ep)
    label_apex = "ZONE APEX PULMONAIRES"
    if res_champ == "OUI":
        label_apex += " ✓"
    else:
        label_apex += " ✗"
    draw.rectangle([15, apex_y1 + 5, 320, apex_y1 + taille_label + 12], fill=(20, 40, 80))
    draw.text((20, apex_y1 + 8), label_apex, fill=couleur_champ, font=petite_font)

    cds_y1 = int(H * 0.82)
    cds_y2 = int(H * 0.95)
    draw.rectangle([10, cds_y1, W - 10, cds_y2], outline=couleur_champ, width=ep)
    label_cds = "ZONE CULS-DE-SAC"
    if res_champ == "OUI":
        label_cds += " ✓"
    else:
        label_cds += " ✗"
    draw.rectangle([15, cds_y1 + 5, 250, cds_y1 + taille_label + 12], fill=(20, 40, 80))
    draw.text((20, cds_y1 + 8), label_cds, fill=couleur_champ, font=petite_font)

    # 3. SYMÉTRIE
    vert = (0, 230, 0)
    jaune = (255, 220, 0)
    res_sym = qc.get('symetrie', {}).get('resultat', '')

    x_centre = W // 2
    y_sym_start = int(H * 0.12)
    y_sym_end = int(H * 0.35)

    tiret = max(10, int(H / 50))
    for y in range(y_sym_start, y_sym_end, tiret * 2):
        draw.line([(x_centre, y), (x_centre, min(y + tiret, y_sym_end))], fill=vert, width=ep)

    sym_zone_x1 = int(W * 0.25)
    sym_zone_x2 = int(W * 0.75)
    sym_zone_y1 = int(H * 0.10)
    sym_zone_y2 = int(H * 0.22)
    draw.rectangle([sym_zone_x1, sym_zone_y1, sym_zone_x2, sym_zone_y2], outline=jaune, width=ep)

    draw.rectangle([sym_zone_x1, sym_zone_y1 - taille_label - 8, sym_zone_x1 + 200, sym_zone_y1 - 2], fill=(50, 50, 20))
    draw.text((sym_zone_x1 + 5, sym_zone_y1 - taille_label - 5), "ZONE CLAVICULAIRE", fill=jaune, font=petite_font)

    y_d = sym_zone_y2 + 15
    draw.line([(sym_zone_x1, y_d), (x_centre, y_d)], fill=jaune, width=ep)
    draw.line([(x_centre, y_d), (sym_zone_x2, y_d)], fill=jaune, width=ep)
    draw.line([(sym_zone_x1, y_d - 6), (sym_zone_x1, y_d + 6)], fill=jaune, width=ep)
    draw.line([(x_centre, y_d - 6), (x_centre, y_d + 6)], fill=vert, width=ep)
    draw.line([(sym_zone_x2, y_d - 6), (sym_zone_x2, y_d + 6)], fill=jaune, width=ep)

    draw.rectangle([(sym_zone_x1 + x_centre) // 2 - 20, y_d - 20, (sym_zone_x1 + x_centre) // 2 + 20, y_d - 5], fill=(50, 50, 20))
    draw.text(((sym_zone_x1 + x_centre) // 2 - 12, y_d - 20), "D1", fill=jaune, font=petite_font)
    draw.rectangle([(x_centre + sym_zone_x2) // 2 - 20, y_d - 20, (x_centre + sym_zone_x2) // 2 + 20, y_d - 5], fill=(50, 50, 20))
    draw.text(((x_centre + sym_zone_x2) // 2 - 12, y_d - 20), "D2", fill=jaune, font=petite_font)

    if res_sym == "OUI":
        verdict = "D1 ≈ D2 (Symétrique) ✓"
        couleur_v = vert
    else:
        verdict = "D1 ≠ D2 (Asymétrique) ✗"
        couleur_v = (255, 80, 80)
    bbox_v = font.getbbox(verdict)
    tw_v = bbox_v[2] - bbox_v[0]
    draw.rectangle([x_centre - tw_v // 2 - 10, y_d + 8, x_centre + tw_v // 2 + 10, y_d + taille_label + 15], fill=(30, 30, 40))
    draw.text((x_centre - tw_v // 2, y_d + 10), verdict, fill=couleur_v, font=font)

    # 4. INSPIRATION
    cyan = (0, 220, 230)
    res_insp = qc.get('inspiration', {}).get('resultat', '')
    annotations = data.get('annotations', {})
    nb_arcs = annotations.get('arcs_costaux', {}).get('nombre_visible', 0)

    arc_zone_x1 = int(W * 0.75)
    arc_zone_x2 = W - 10
    arc_zone_y1 = int(H * 0.25)
    arc_zone_y2 = int(H * 0.75)
    draw.rectangle([arc_zone_x1, arc_zone_y1, arc_zone_x2, arc_zone_y2], outline=cyan, width=ep)

    draw.rectangle([arc_zone_x1, arc_zone_y1 - taille_label - 8, arc_zone_x1 + 180, arc_zone_y1 - 2], fill=(20, 50, 50))
    draw.text((arc_zone_x1 + 5, arc_zone_y1 - taille_label - 5), "ZONE ARCS COSTAUX", fill=cyan, font=petite_font)

    if res_insp == "OUI":
        bilan = f"{nb_arcs} arcs (>=7) ✓"
        couleur_insp = vert
    else:
        bilan = f"{nb_arcs} arcs (<7) ✗"
        couleur_insp = (255, 80, 80)

    bbox_bilan = font.getbbox(bilan)
    tw_bilan = bbox_bilan[2] - bbox_bilan[0]
    y_bilan = arc_zone_y2 + 10
    draw.rectangle([arc_zone_x1, y_bilan, arc_zone_x1 + tw_bilan + 20, y_bilan + taille_label + 10], fill=(30, 30, 40))
    draw.text((arc_zone_x1 + 10, y_bilan + 5), bilan, fill=couleur_insp, font=font)

    # 5. PATHOLOGIES
    pathologies = annotations.get('pathologies', [])
    if pathologies:
        for patho in pathologies:
            px = int(W * patho.get('x', 50) / 100)
            py = int(H * patho.get('y', 50) / 100)
            label = patho.get('label', 'Anomalie')
            rayon = max(20, int(min(W, H) / 15))
            rouge = (255, 40, 40)
            draw.ellipse([px - rayon, py - rayon, px + rayon, py + rayon], outline=rouge, width=ep + 2)
            draw.ellipse([px - rayon - 6, py - rayon - 6, px + rayon + 6, py + rayon + 6], outline=(255, 100, 100), width=ep)
            lx = px + rayon + 20
            ly = py - rayon - 15
            draw.line([(px + rayon, py - rayon // 2), (lx, ly)], fill=rouge, width=ep + 1)
            bbox_l = font.getbbox(label)
            tw_l = bbox_l[2] - bbox_l[0]
            th_l = bbox_l[3] - bbox_l[1]
            draw.rectangle([lx - 5, ly - th_l - 10, lx + tw_l + 12, ly + 8], fill=(160, 0, 0))
            draw.text((lx + 3, ly - th_l - 5), label, fill=(255, 255, 255), font=font)

    # 6. LÉGENDE
    legende_h = max(50, int(H / 12))
    y_leg = H - legende_h
    draw.rectangle([0, y_leg, W, H], fill=(15, 15, 25))

    items = [
        ((80, 160, 255), "Champ"),
        ((0, 230, 0), "Médiane"),
        ((255, 220, 0), "Symétrie"),
        ((0, 220, 230), "Arcs"),
        ((255, 40, 40), "Pathologie"),
    ]
    x_pos = 15
    for couleur, texte in items:
        draw.rectangle([x_pos, y_leg + 8, x_pos + 14, y_leg + 22], fill=couleur)
        draw.text((x_pos + 18, y_leg + 6), texte, fill=(220, 220, 220), font=petite_font)
        bbox_it = petite_font.getbbox(texte)
        x_pos += (bbox_it[2] - bbox_it[0]) + 40

    note = "Repères pédagogiques — Zones d'évaluation schématiques"
    draw.text((15, y_leg + 28), note, fill=(150, 150, 150), font=petite_font)

    return img_annotee

# ══════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_KEY"]

    supabase = initialiser_supabase(SUPABASE_URL, SUPABASE_KEY)
    model, MODEL_NAME = initialiser_gemini(GEMINI_KEY)

except Exception as e:
    st.error(f"Erreur de configuration (Vérifiez vos Secrets) : {e}")
    st.stop()

# ══════════════════════════════════════════════════════
# DESIGN
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
.critere-oui {
    background: linear-gradient(135deg, #0d3d0d, #1a5a1a);
    border-radius: 10px; padding: 0.9rem; margin-bottom: 0.6rem;
    border-left: 5px solid #00c853; color: #ffffff;
}
.critere-oui strong { color: #4ade80; }
.critere-non {
    background: linear-gradient(135deg, #3d0d0d, #5a1a1a);
    border-radius: 10px; padding: 0.9rem; margin-bottom: 0.6rem;
    border-left: 5px solid #ff1744; color: #ffffff;
}
.critere-non strong { color: #ff6b6b; }
.qc-conforme {
    background: linear-gradient(135deg, #0d3d0d, #1a5a1a);
    border-radius: 10px; padding: 1rem; margin: 0.8rem 0;
    border: 2px solid #00c853; text-align: center;
    font-size: 1.2rem; font-weight: bold; color: #4ade80;
}
.qc-non-conforme {
    background: linear-gradient(135deg, #3d0d0d, #5a1a1a);
    border-radius: 10px; padding: 1rem; margin: 0.8rem 0;
    border: 2px solid #ff1744; text-align: center;
    font-size: 1.2rem; font-weight: bold; color: #ff6b6b;
}
.classif-normal {
    background: linear-gradient(135deg, #0a4a0a, #15751a);
    padding: 1rem; border-radius: 12px; text-align: center;
    font-size: 1.4rem; font-weight: bold; color: #4ade80;
    border: 3px solid #00c853; margin-bottom: 1rem;
}
.classif-patho {
    background: linear-gradient(135deg, #4a0a0a, #751515);
    padding: 1rem; border-radius: 12px; text-align: center;
    font-size: 1.4rem; font-weight: bold; color: #ff6b6b;
    border: 3px solid #ff1744; margin-bottom: 1rem;
}
.principe { color: #a0a0a0; font-size: 0.85rem; font-style: italic; margin-bottom: 0.3rem; }
.justification { color: #e0e0e0; margin-top: 0.4rem; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# PROMPT STRICT
# ══════════════════════════════════════════════════════
PROMPT = """Tu es un radiologue EXPERT en contrôle qualité des radiographies thoraciques.
Analyse cette radiographie thoracique de face (PA).

Réponds UNIQUEMENT en JSON strict, sans markdown, sans backticks :

{
  "qualite": {
    "champ_radiographique": {"resultat": "OUI ou NON", "justification": "..."},
    "symetrie": {"resultat": "OUI ou NON", "justification": "..."},
    "inspiration": {"resultat": "OUI ou NON", "justification": "..."},
    "conclusion_globale": "Conforme ou Non conforme"
  },
  "diagnostic": {
    "classification": "NORMAL ou PATHOLOGIQUE",
    "conclusion": "Diagnostic principal en une phrase",
    "description_semiologique": "Description détaillée en 2 à 4 phrases."
  },
  "annotations": {
    "arcs_costaux": {"nombre_visible": 8},
    "pathologies": []
  }
}

════════════════════════════════════════════════════════
CRITÈRE 1 : CHAMP RADIOGRAPHIQUE
════════════════════════════════════════════════════════

DÉFINITION : Le champ radiographique évalue si l'IMAGE est correctement CADRÉE.
C'est un critère TECHNIQUE (qualité du cliché), PAS un critère pathologique.

MÉTHODE D'ÉVALUATION — Regarde les BORDS EXTRÊMES de l'image :

Pour les APEX (haut) :
- Regarde le BORD SUPÉRIEUR de l'image.
- Les sommets des deux poumons doivent être ENTIÈREMENT INCLUS dans l'image.
- "COUPÉ" signifie que le BORD DE L'IMAGE tranche/coupe le tissu pulmonaire.
- Si le tissu pulmonaire continue jusqu'au bord de l'image et semble tronqué → NON.
- Si tu vois de l'espace (noir ou tissu mou) au-dessus des apex → les apex sont inclus → OUI.

Pour les CULS-DE-SAC COSTO-DIAPHRAGMATIQUES (bas) :
- Regarde le BORD INFÉRIEUR de l'image.
- Les angles formés entre le diaphragme et la paroi costale doivent être INCLUS dans l'image.
- "COUPÉ" signifie que le BORD DE L'IMAGE coupe cette zone.

DISTINCTION CRUCIALE — Ne PAS confondre :
- COUPÉ par le bord de l'image (= problème TECHNIQUE de cadrage) → champ = NON
- EFFACÉ ou COMBLÉ par une pathologie comme un épanchement pleural (= problème MÉDICAL) → champ = OUI (l'image est bien cadrée, c'est la maladie qui masque la structure)

EXEMPLES :
- Un cul-de-sac est COMBLÉ par un épanchement pleural mais la zone est dans l'image → champ = OUI (pathologie à signaler dans le diagnostic)
- Un cul-de-sac est COUPÉ car le bord inférieur de l'image s'arrête trop haut → champ = NON
- Un apex est OPACIFIÉ par une lésion mais visible dans l'image → champ = OUI
- Un apex est TRONQUÉ car le bord supérieur de l'image coupe le sommet du poumon → champ = NON

EN RÉSUMÉ : Champ = "Est-ce que l'image CONTIENT toute la zone thoracique ?"
- OUI = toute la cage thoracique est dans le cadre de l'image (même si des structures sont masquées par une maladie)
- NON = le cadrage de l'image est trop serré et coupe des zones anatomiques

════════════════════════════════════════════════════════
CRITÈRE 2 : SYMÉTRIE
════════════════════════════════════════════════════════

Évalue si le patient était bien CENTRÉ lors de la prise du cliché.
- Les bords INTERNES (médiaux) des deux clavicules doivent être à ÉGALE DISTANCE de la ligne des apophyses épineuses.
- Si une clavicule est nettement plus proche de la ligne médiane → rotation du patient → NON.
- Si les distances sont approximativement égales → OUI.

════════════════════════════════════════════════════════
CRITÈRE 3 : INSPIRATION
════════════════════════════════════════════════════════

Évalue la profondeur de l'inspiration du patient.
- Compte les arcs costaux POSTÉRIEURS visibles AU-DESSUS du diaphragme, du côté DROIT.
- Bonne inspiration = 7 à 9 arcs → OUI.
- Moins de 7 arcs → inspiration insuffisante → NON.
- Indique le nombre exact dans la justification et dans annotations.arcs_costaux.nombre_visible.

════════════════════════════════════════════════════════
CRITÈRE 4 : CLASSIFICATION DIAGNOSTIQUE
════════════════════════════════════════════════════════

- "NORMAL" = transparence pulmonaire normale, silhouette cardiaque normale, médiastin normal, pas d'anomalie osseuse.
- "PATHOLOGIQUE" = toute anomalie observée (opacité, épanchement, cardiomégalie, condensation, nodule, fracture, etc.)
- Si un cul-de-sac est COMBLÉ par un épanchement → classification = PATHOLOGIQUE (pas un problème de champ).

════════════════════════════════════════════════════════
RÈGLE FINALE
════════════════════════════════════════════════════════
conclusion_globale = "Conforme" UNIQUEMENT si les 3 critères de qualité sont TOUS "OUI". Sinon "Non conforme"."""

# ══════════════════════════════════════════════════════
# NAVIGATION
# ══════════════════════════════════════════════════════
st.sidebar.title("🫁 RadioIA")
page = st.sidebar.radio("Navigation", [
    "🩻 Analyse IA",
    "👨‍⚕️ Validation Radiologue",
    "📊 Export & Statistiques"
], key="nav_main")

# ══════════════════════════════════════════════════════
# PAGE 1 : ANALYSE IA
# ══════════════════════════════════════════════════════
if page == "🩻 Analyse IA":
    st.markdown("# 🫁 RadioIA — Assistant Radiographie Thoracique")
    st.markdown("*Mémoire de Master en Radiologie et Imagerie Médicale — Hôpital Jamot de Yaoundé*")
    st.divider()

    col_gauche, col_droite = st.columns([1, 1.5])

    with col_gauche:
        st.subheader("📝 Nouvelle analyse")
        
        # Upload HORS du formulaire
        img_file = st.file_uploader("🩻 Uploader la radiographie", type=['jpg', 'jpeg', 'png'], key="uploader_radio")

        if img_file is not None:
            img_file.seek(0)
            st.session_state['image_bytes'] = img_file.read()
            st.session_state['image_name'] = img_file.name
        
        if 'image_bytes' in st.session_state:
            img_preview = Image.open(io.BytesIO(st.session_state['image_bytes'])).convert("RGB")
            st.image(img_preview, caption="Radio chargée", use_container_width=True)

        # Formulaire
        with st.form("formulaire_analyse", clear_on_submit=False):
            p_id = st.text_input("🏷️ Identifiant radio", placeholder="RAD_001")
            p_age = st.number_input("🎂 Âge du patient", min_value=18, max_value=120, value=30)
            p_sexe = st.selectbox("👤 Sexe", ["Masculin", "Féminin"])
            submitted = st.form_submit_button("🚀 ANALYSER ET SAUVEGARDER")

        if submitted:
            if 'image_bytes' not in st.session_state:
                st.warning("⚠️ Veuillez uploader une radiographie.")
            elif not p_id:
                st.warning("⚠️ Veuillez renseigner l'identifiant radio.")
            else:
                img = Image.open(io.BytesIO(st.session_state['image_bytes'])).convert("RGB")
                with st.spinner("🔬 Analyse IA en cours..."):
                    try:
                        response = model.generate_content([PROMPT, img])
                        clean_text = response.text.replace('```json', '').replace('```', '').strip()
                        debut = clean_text.find("{")
                        fin = clean_text.rfind("}")
                        if debut != -1 and fin != -1:
                            clean_text = clean_text[debut:fin + 1]
                        data = json.loads(clean_text)

                        qc = data['qualite']
                        diag = data['diagnostic']
                        classification = diag.get('classification', 'INDÉTERMINÉ')

                        res_champ = qc['champ_radiographique']['resultat'].upper().strip()
                        res_sym = qc['symetrie']['resultat'].upper().strip()
                        res_insp = qc['inspiration']['resultat'].upper().strip()

                        if res_champ == "OUI" and res_sym == "OUI" and res_insp == "OUI":
                            qc['conclusion_globale'] = "Conforme"
                        else:
                            qc['conclusion_globale'] = "Non conforme"

                        img_annotee = annoter_image(img, data)

                        st.session_state['derniere_analyse'] = {
                            'img_annotee': img_annotee,
                            'data': data,
                            'patient_id': p_id
                        }

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
                            "classification": classification,
                            "description": diag['description_semiologique']
                        }).execute()

                        st.success("✅ Analyse terminée — 💾 Sauvegardée !")

                    except Exception as e:
                        st.error(f"⚠️ Erreur lors de l'analyse : {e}")

        # Bouton Nouvelle Analyse
        if 'derniere_analyse' in st.session_state:
            st.markdown("")
            if st.button("🔄 NOUVELLE ANALYSE", key="btn_nouvelle"):
                if 'derniere_analyse' in st.session_state:
                    del st.session_state['derniere_analyse']
                if 'image_bytes' in st.session_state:
                    del st.session_state['image_bytes']
                if 'image_name' in st.session_state:
                    del st.session_state['image_name']
                st.rerun()

    with col_droite:
        if 'derniere_analyse' in st.session_state:
            analyse = st.session_state['derniere_analyse']
            data = analyse['data']
            qc = data['qualite']
            diag = data['diagnostic']
            classification = diag.get('classification', 'INDÉTERMINÉ')

            st.subheader(f"🔍 Résultat — {analyse['patient_id']}")

            st.image(analyse['img_annotee'], use_container_width=True)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                with st.expander("🔎 ZOOM"):
                    st.image(analyse['img_annotee'], use_container_width=True)

            with col_btn2:
                img_bytes = io.BytesIO()
                analyse['img_annotee'].save(img_bytes, format='PNG')
                img_bytes.seek(0)
                st.download_button(
                    label="💾 Télécharger",
                    data=img_bytes,
                    file_name=f"radio_{analyse['patient_id']}.png",
                    mime="image/png"
                )

            if classification == "NORMAL":
                st.markdown('<div class="classif-normal">✅ CLASSIFICATION : NORMAL</div>', unsafe_allow_html=True)
            elif classification == "PATHOLOGIQUE":
                st.markdown('<div class="classif-patho">⚠️ CLASSIFICATION : PATHOLOGIQUE</div>', unsafe_allow_html=True)

            st.markdown("### 📋 Critères de qualité")

            res_champ = qc['champ_radiographique']['resultat']
            classe_champ = "critere-oui" if res_champ == "OUI" else "critere-non"
            icone_champ = "✅" if res_champ == "OUI" else "❌"
            st.markdown(f"""<div class="{classe_champ}">
                <strong>{icone_champ} CHAMP RADIOGRAPHIQUE : {res_champ}</strong>
                <div class="principe">Principe : apex pulmonaires et culs-de-sac entièrement visibles.</div>
                <div class="justification">→ {qc['champ_radiographique']['justification']}</div>
            </div>""", unsafe_allow_html=True)

            res_sym = qc['symetrie']['resultat']
            classe_sym = "critere-oui" if res_sym == "OUI" else "critere-non"
            icone_sym = "✅" if res_sym == "OUI" else "❌"
            st.markdown(f"""<div class="{classe_sym}">
                <strong>{icone_sym} SYMÉTRIE : {res_sym}</strong>
                <div class="principe">Principe : bords internes des clavicules équidistants des épineuses.</div>
                <div class="justification">→ {qc['symetrie']['justification']}</div>
            </div>""", unsafe_allow_html=True)

            res_insp = qc['inspiration']['resultat']
            classe_insp = "critere-oui" if res_insp == "OUI" else "critere-non"
            icone_insp = "✅" if res_insp == "OUI" else "❌"
            st.markdown(f"""<div class="{classe_insp}">
                <strong>{icone_insp} INSPIRATION : {res_insp}</strong>
                <div class="principe">Principe : au moins 7 arcs costaux postérieurs visibles.</div>
                <div class="justification">→ {qc['inspiration']['justification']}</div>
            </div>""", unsafe_allow_html=True)

            concl_qc = qc['conclusion_globale']
            if concl_qc == "Conforme":
                st.markdown('<div class="qc-conforme">✅ CONFORMITÉ GLOBALE : CONFORME</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="qc-non-conforme">❌ CONFORMITÉ GLOBALE : NON CONFORME</div>', unsafe_allow_html=True)

            st.markdown("### 🩺 Diagnostic")
            st.markdown(f"**Conclusion :** {diag['conclusion']}")
            st.markdown(f"**Description :** {diag['description_semiologique']}")

            pathologies = data.get('annotations', {}).get('pathologies', [])
            if pathologies:
                st.markdown("**Anomalies :**")
                for p in pathologies:
                    st.markdown(f"- 🔴 **{p.get('label', 'Anomalie')}**")

        # Historique
        st.divider()
        st.subheader("📜 Historique")
        try:
            history = supabase.table("analyses").select("*").order('created_at', desc=True).limit(15).execute()
            if history.data:
                for row in history.data:
                    classif = row.get('classification', 'N/A')
                    valide = row.get('valide_par_radiologue', False)
                    emoji = "✅" if classif == "NORMAL" else "⚠️" if classif == "PATHOLOGIQUE" else "❓"
                    badge = "✔ Validé" if valide else "⏳"
                    conformite = row.get('conclusion_qc', 'N/A')
                    
                    with st.expander(f"{emoji} {row['patient_id']} — {classif} — {conformite} {badge}"):
                        st.markdown(f"**Patient :** {row['patient_id']} | **Âge :** {row.get('age', 'N/A')} | **Sexe :** {row.get('sexe', 'N/A')}")
                        st.markdown("---")
                        r_champ = row.get('champ_radiographique', 'N/A')
                        ic_champ = "✅" if r_champ == "OUI" else "❌"
                        st.markdown(f"{ic_champ} **Champ :** {r_champ}")
                        st.caption(f"{row.get('champ_justification', '')}")
                        r_sym = row.get('symetrie', 'N/A')
                        ic_sym = "✅" if r_sym == "OUI" else "❌"
                        st.markdown(f"{ic_sym} **Symétrie :** {r_sym}")
                        st.caption(f"{row.get('symetrie_justification', '')}")
                        r_insp = row.get('inspiration', 'N/A')
                        ic_insp = "✅" if r_insp == "OUI" else "❌"
                        st.markdown(f"{ic_insp} **Inspiration :** {r_insp}")
                        st.caption(f"{row.get('inspiration_justification', '')}")
                        st.markdown(f"**Conformité :** {conformite}")
                        st.markdown("---")
                        st.markdown(f"**Classification :** {classif}")
                        st.markdown(f"**Diagnostic :** {row.get('diagnostic', 'N/A')}")
                        st.markdown(f"**Description :** {row.get('description', 'N/A')}")
                        if valide:
                            st.markdown("---")
                            st.markdown("**👨‍⚕️ Avis Radiologue :**")
                            st.markdown(f"Champ: {row.get('champ_radiologue', 'N/A')} | Symétrie: {row.get('symetrie_radiologue', 'N/A')} | Inspiration: {row.get('inspiration_radiologue', 'N/A')}")
                            st.markdown(f"**Conformité :** {row.get('conformite_radiologue', 'N/A')}")
                            st.markdown(f"**Classification :** {row.get('classification_radiologue', 'N/A')}")
            else:
                st.info("📭 Aucune analyse.")
        except Exception as e:
            st.warning(f"Historique indisponible : {e}")

# ══════════════════════════════════════════════════════
# PAGE 2 : VALIDATION RADIOLOGUE
# ══════════════════════════════════════════════════════
elif page == "👨‍⚕️ Validation Radiologue":
    st.markdown("# 👨‍⚕️ Validation par le Radiologue")
    st.markdown("*Sélectionnez une analyse pour saisir l'avis du radiologue.*")
    st.divider()

    try:
        analyses = supabase.table("analyses").select("*").order('created_at', desc=True).execute()

        if not analyses.data:
            st.info("📭 Aucune analyse à valider.")
        else:
            filtre = st.radio("Filtrer", ["⏳ En attente", "✅ Validées", "📋 Toutes"], horizontal=True)

            if filtre == "⏳ En attente":
                liste = [r for r in analyses.data if not r.get('valide_par_radiologue', False)]
            elif filtre == "✅ Validées":
                liste = [r for r in analyses.data if r.get('valide_par_radiologue', False)]
            else:
                liste = analyses.data

            if not liste:
                st.info("Aucune analyse dans cette catégorie.")
            else:
                st.info(f"📁 **{len(liste)} analyse(s)**")

                options = [f"{r['patient_id']} — {r.get('classification', 'N/A')} — {'✔' if r.get('valide_par_radiologue') else '⏳'}" for r in liste]
                choix = st.selectbox("Sélectionner", options)
                idx = options.index(choix)
                row = liste[idx]

                col_ia, col_radio = st.columns(2)

                with col_ia:
                    st.markdown("### 🤖 Résultat IA")
                    st.markdown(f"**Patient :** {row['patient_id']}")
                    st.markdown(f"**Âge :** {row.get('age', 'N/A')} | **Sexe :** {row.get('sexe', 'N/A')}")
                    st.divider()
                    st.markdown(f"**Champ :** {row.get('champ_radiographique', 'N/A')}")
                    st.caption(row.get('champ_justification', ''))
                    st.markdown(f"**Symétrie :** {row.get('symetrie', 'N/A')}")
                    st.caption(row.get('symetrie_justification', ''))
                    st.markdown(f"**Inspiration :** {row.get('inspiration', 'N/A')}")
                    st.caption(row.get('inspiration_justification', ''))
                    st.divider()
                    st.markdown(f"**Conformité IA :** {row.get('conclusion_qc', 'N/A')}")
                    st.markdown(f"**Classification IA :** {row.get('classification', 'N/A')}")
                    st.markdown(f"**Diagnostic :** {row.get('diagnostic', 'N/A')}")

                with col_radio:
                    st.markdown("### 👨‍⚕️ Avis Radiologue")

                    with st.form(f"form_validation_{row['id']}"):
                        r_champ = st.selectbox("Champ", ["OUI", "NON"], index=0 if row.get('champ_radiologue', 'OUI') == 'OUI' else 1)
                        r_sym = st.selectbox("Symétrie", ["OUI", "NON"], index=0 if row.get('symetrie_radiologue', 'OUI') == 'OUI' else 1)
                        r_insp = st.selectbox("Inspiration", ["OUI", "NON"], index=0 if row.get('inspiration_radiologue', 'OUI') == 'OUI' else 1)

                        if r_champ == "OUI" and r_sym == "OUI" and r_insp == "OUI":
                            conformite_radio = "Conforme"
                        else:
                            conformite_radio = "Non conforme"
                        st.markdown(f"**Conformité : {conformite_radio}**")

                        r_classif = st.selectbox("Classification", ["NORMAL", "PATHOLOGIQUE"], index=0 if row.get('classification_radiologue', 'NORMAL') == 'NORMAL' else 1)
                        r_conclusion = st.text_area("Conclusion", value=row.get('conclusion_qc_radiologue', ''))

                        if st.form_submit_button("💾 SAUVEGARDER"):
                            try:
                                supabase.table("analyses").update({
                                    "champ_radiologue": r_champ,
                                    "symetrie_radiologue": r_sym,
                                    "inspiration_radiologue": r_insp,
                                    "conformite_radiologue": conformite_radio,
                                    "classification_radiologue": r_classif,
                                    "conclusion_qc_radiologue": r_conclusion,
                                    "valide_par_radiologue": True,
                                    "date_validation": datetime.now().isoformat()
                                }).eq('id', row['id']).execute()

                                st.success(f"✅ Avis sauvegardé pour {row['patient_id']} !")
                                st.rerun()

                            except Exception as e:
                                st.error(f"Erreur : {e}")

                if row.get('valide_par_radiologue', False):
                    st.divider()
                    st.markdown("### 📊 Concordance IA vs Radiologue")
                    concordances = {
                        "Champ": (row.get('champ_radiographique'), row.get('champ_radiologue')),
                        "Symétrie": (row.get('symetrie'), row.get('symetrie_radiologue')),
                        "Inspiration": (row.get('inspiration'), row.get('inspiration_radiologue')),
                        "Conformité": (row.get('conclusion_qc'), row.get('conformite_radiologue')),
                        "Classification": (row.get('classification'), row.get('classification_radiologue')),
                    }
                    cols = st.columns(5)
                    for i, (critere, (ia, radio)) in enumerate(concordances.items()):
                        with cols[i]:
                            accord = "✅" if ia == radio else "❌"
                            st.metric(critere, accord)

    except Exception as e:
        st.error(f"Erreur : {e}")

# ══════════════════════════════════════════════════════
# PAGE 3 : EXPORT
# ══════════════════════════════════════════════════════
elif page == "📊 Export & Statistiques":
    st.markdown("# 📊 Export & Statistiques")
    st.divider()

    try:
        history = supabase.table("analyses").select("*").order('created_at', desc=True).execute()

        if not history.data:
            st.info("📭 Aucune donnée.")
        else:
            df = pd.DataFrame(history.data)

            total = len(df)
            valides = len(df[df['valide_par_radiologue'] == True]) if 'valide_par_radiologue' in df.columns else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Total", total)
            col2.metric("Validées", valides)
            col3.metric("En attente", total - valides)

            if valides > 0:
                st.markdown("### 📈 Concordance globale")
                df_v = df[df['valide_par_radiologue'] == True]
                for critere, col_ia, col_r in [
                    ("Champ", "champ_radiographique", "champ_radiologue"),
                    ("Symétrie", "symetrie", "symetrie_radiologue"),
                    ("Inspiration", "inspiration", "inspiration_radiologue"),
                    ("Conformité", "conclusion_qc", "conformite_radiologue"),
                    ("Classification", "classification", "classification_radiologue"),
                ]:
                    if col_ia in df_v.columns and col_r in df_v.columns:
                        accords = (df_v[col_ia] == df_v[col_r]).sum()
                        taux = round(accords / len(df_v) * 100, 1)
                        st.write(f"**{critere}** : {accords}/{len(df_v)} ({taux}%)")

            st.markdown("---")
            st.markdown("### 💾 Exporter")

            colonnes = {
                'patient_id': 'ID', 'age': 'Age', 'sexe': 'Sexe',
                'champ_radiographique': 'Champ_IA', 'symetrie': 'Sym_IA', 'inspiration': 'Insp_IA',
                'conclusion_qc': 'Conf_IA', 'classification': 'Class_IA',
                'champ_radiologue': 'Champ_R', 'symetrie_radiologue': 'Sym_R', 'inspiration_radiologue': 'Insp_R',
                'conformite_radiologue': 'Conf_R', 'classification_radiologue': 'Class_R',
                'valide_par_radiologue': 'Valide', 'created_at': 'Date'
            }
            cols_export = [c for c in colonnes if c in df.columns]
            df_exp = df[cols_export].rename(columns=colonnes)

            # Codes numériques
            for col, code in [('Champ_IA', 'Champ_IA_C'), ('Sym_IA', 'Sym_IA_C'), ('Insp_IA', 'Insp_IA_C')]:
                if col in df_exp.columns:
                    df_exp[code] = df_exp[col].apply(lambda x: 1 if str(x).upper() == 'OUI' else 0)
            if 'Conf_IA' in df_exp.columns:
                df_exp['Conf_IA_C'] = df_exp['Conf_IA'].apply(lambda x: 1 if 'conforme' in str(x).lower() and 'non' not in str(x).lower() else 0)
            if 'Class_IA' in df_exp.columns:
                df_exp['Class_IA_C'] = df_exp['Class_IA'].apply(lambda x: 1 if str(x).upper() == 'NORMAL' else 0)

            col_a, col_b = st.columns(2)
            with col_a:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w:
                    df_exp.to_excel(w, index=False)
                buf.seek(0)
                st.download_button("📗 Excel", buf, f"radioia_{datetime.now().strftime('%Y%m%d')}.xlsx")

            with col_b:
                csv = df_exp.to_csv(index=False, sep=';')
                st.download_button("📊 CSV (SPSS)", csv, f"radioia_{datetime.now().strftime('%Y%m%d')}.csv")

            with st.expander("👁️ Aperçu"):
                st.dataframe(df_exp, use_container_width=True)

    except Exception as e:
        st.error(f"Erreur : {e}")
        
