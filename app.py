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
# INITIALISATION GEMINI (CACHÉE — 1 SEUL APPEL)
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
# FONCTION POUR ANNOTER L'IMAGE (REPÈRES PÉDAGOGIQUES)
# ══════════════════════════════════════════════════════
def annoter_image(img, data):
    """
    Dessine des repères PÉDAGOGIQUES sur l'image.
    Ces repères illustrent les PRINCIPES d'évaluation de la qualité,
    pas la position anatomique exacte (qui nécessiterait un modèle de segmentation).
    """
    img_annotee = img.copy()
    draw = ImageDraw.Draw(img_annotee)
    W, H = img_annotee.size
    ep = max(3, int(min(W, H) / 200))

    # Polices
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

    # ─────────────────────────────────────────────────
    # 1. BANDEAU CLASSIFICATION en haut
    # ─────────────────────────────────────────────────
    bandeau_h = max(40, int(H / 12))
    if classification == "NORMAL":
        couleur_b = (0, 140, 50)
        texte_b = "✓ NORMAL"
    elif classification == "PATHOLOGIQUE":
        couleur_b = (190, 20, 20)
        texte_b = "⚠ PATHOLOGIQUE"
    else:
        couleur_b = (140, 140, 0)
        texte_b = "? INDÉTERMINÉ"
    draw.rectangle([0, 0, W, bandeau_h], fill=couleur_b)
    bbox_b = font_bandeau.getbbox(texte_b)
    tw_b = bbox_b[2] - bbox_b[0]
    draw.text(((W - tw_b) // 2, 8), texte_b, fill=(255, 255, 255), font=font_bandeau)

    # ─────────────────────────────────────────────────
    # 2. CHAMP RADIOGRAPHIQUE — Zones à vérifier
    #    Repères pédagogiques : encadrés indiquant où
    #    regarder pour les apex et culs-de-sac
    # ─────────────────────────────────────────────────
    bleu = (80, 160, 255)
    res_champ = qc.get('champ_radiographique', {}).get('resultat', '')
    
    # Zone APEX (haut de l'image)
    apex_y1 = bandeau_h + 5
    apex_y2 = int(H * 0.18)
    draw.rectangle([10, apex_y1, W - 10, apex_y2], outline=bleu, width=ep)
    # Label apex
    label_apex = "ZONE APEX PULMONAIRES"
    if res_champ == "OUI":
        label_apex += " ✓"
    draw.rectangle([15, apex_y1 + 5, 280, apex_y1 + taille_label + 12], fill=(20, 40, 80))
    draw.text((20, apex_y1 + 8), label_apex, fill=bleu, font=petite_font)
    
    # Zone CDS (bas de l'image)
    cds_y1 = int(H * 0.82)
    cds_y2 = int(H * 0.95)
    draw.rectangle([10, cds_y1, W - 10, cds_y2], outline=bleu, width=ep)
    # Label CDS
    label_cds = "ZONE CULS-DE-SAC COSTO-DIAPHRAGMATIQUES"
    if res_champ == "OUI":
        label_cds += " ✓"
    draw.rectangle([15, cds_y1 + 5, 420, cds_y1 + taille_label + 12], fill=(20, 40, 80))
    draw.text((20, cds_y1 + 8), label_cds, fill=bleu, font=petite_font)

    # ─────────────────────────────────────────────────
    # 3. SYMÉTRIE — Zone claviculaire schématique
    #    Repère pédagogique : zone où évaluer la symétrie
    # ─────────────────────────────────────────────────
    vert = (0, 230, 0)
    jaune = (255, 220, 0)
    res_sym = qc.get('symetrie', {}).get('resultat', '')
    
    # Ligne médiane centrale (schématique)
    x_centre = W // 2
    y_sym_start = int(H * 0.12)
    y_sym_end = int(H * 0.35)
    
    # Ligne médiane pointillée
    tiret = max(10, int(H / 50))
    for y in range(y_sym_start, y_sym_end, tiret * 2):
        draw.line([(x_centre, y), (x_centre, min(y + tiret, y_sym_end))], fill=vert, width=ep)
    
    # Zone d'évaluation de symétrie (rectangle)
    sym_zone_x1 = int(W * 0.25)
    sym_zone_x2 = int(W * 0.75)
    sym_zone_y1 = int(H * 0.10)
    sym_zone_y2 = int(H * 0.22)
    draw.rectangle([sym_zone_x1, sym_zone_y1, sym_zone_x2, sym_zone_y2], outline=jaune, width=ep)
    
    # Labels
    draw.rectangle([sym_zone_x1, sym_zone_y1 - taille_label - 8, sym_zone_x1 + 200, sym_zone_y1 - 2], fill=(50, 50, 20))
    draw.text((sym_zone_x1 + 5, sym_zone_y1 - taille_label - 5), "ZONE CLAVICULAIRE", fill=jaune, font=petite_font)
    
    # Indication D1 = D2
    y_d = sym_zone_y2 + 15
    draw.line([(sym_zone_x1, y_d), (x_centre, y_d)], fill=jaune, width=ep)
    draw.line([(x_centre, y_d), (sym_zone_x2, y_d)], fill=jaune, width=ep)
    draw.line([(sym_zone_x1, y_d - 6), (sym_zone_x1, y_d + 6)], fill=jaune, width=ep)
    draw.line([(x_centre, y_d - 6), (x_centre, y_d + 6)], fill=vert, width=ep)
    draw.line([(sym_zone_x2, y_d - 6), (sym_zone_x2, y_d + 6)], fill=jaune, width=ep)
    
    # Labels D1 D2
    draw.rectangle([(sym_zone_x1 + x_centre) // 2 - 20, y_d - 20, (sym_zone_x1 + x_centre) // 2 + 20, y_d - 5], fill=(50, 50, 20))
    draw.text(((sym_zone_x1 + x_centre) // 2 - 12, y_d - 20), "D1", fill=jaune, font=petite_font)
    draw.rectangle([(x_centre + sym_zone_x2) // 2 - 20, y_d - 20, (x_centre + sym_zone_x2) // 2 + 20, y_d - 5], fill=(50, 50, 20))
    draw.text(((x_centre + sym_zone_x2) // 2 - 12, y_d - 20), "D2", fill=jaune, font=petite_font)
    
    # Verdict
    if res_sym == "OUI":
        verdict = "✓ D1 ≈ D2 (Symétrique)"
        couleur_v = vert
    else:
        verdict = "✗ D1 ≠ D2 (Asymétrique)"
        couleur_v = (255, 80, 80)
    bbox_v = font.getbbox(verdict)
    tw_v = bbox_v[2] - bbox_v[0]
    draw.rectangle([x_centre - tw_v // 2 - 10, y_d + 8, x_centre + tw_v // 2 + 10, y_d + taille_label + 15], fill=(30, 30, 40))
    draw.text((x_centre - tw_v // 2, y_d + 10), verdict, fill=couleur_v, font=font)

    # ─────────────────────────────────────────────────
    # 4. INSPIRATION — Zone de comptage des arcs
    #    Repère pédagogique : zone latérale où compter
    # ─────────────────────────────────────────────────
    cyan = (0, 220, 230)
    res_insp = qc.get('inspiration', {}).get('resultat', '')
    annotations = data.get('annotations', {})
    nb_arcs = annotations.get('arcs_costaux', {}).get('nombre_visible', 0)
    
    # Zone de comptage (côté droit)
    arc_zone_x1 = int(W * 0.75)
    arc_zone_x2 = W - 10
    arc_zone_y1 = int(H * 0.25)
    arc_zone_y2 = int(H * 0.75)
    draw.rectangle([arc_zone_x1, arc_zone_y1, arc_zone_x2, arc_zone_y2], outline=cyan, width=ep)
    
    # Label zone
    draw.rectangle([arc_zone_x1, arc_zone_y1 - taille_label - 8, arc_zone_x1 + 180, arc_zone_y1 - 2], fill=(20, 50, 50))
    draw.text((arc_zone_x1 + 5, arc_zone_y1 - taille_label - 5), "ZONE ARCS COSTAUX", fill=cyan, font=petite_font)
    
    # Indication du nombre d'arcs comptés
    if res_insp == "OUI":
        bilan = f"✓ {nb_arcs} arcs (≥7)"
        couleur_insp = vert
    else:
        bilan = f"✗ {nb_arcs} arcs (<7)"
        couleur_insp = (255, 80, 80)
    
    bbox_bilan = font.getbbox(bilan)
    tw_bilan = bbox_bilan[2] - bbox_bilan[0]
    y_bilan = arc_zone_y2 + 10
    draw.rectangle([arc_zone_x1, y_bilan, arc_zone_x1 + tw_bilan + 20, y_bilan + taille_label + 10], fill=(30, 30, 40))
    draw.text((arc_zone_x1 + 10, y_bilan + 5), bilan, fill=couleur_insp, font=font)

    # ─────────────────────────────────────────────────
    # 5. PATHOLOGIES (si présentes)
    # ─────────────────────────────────────────────────
    pathologies = annotations.get('pathologies', [])
    if pathologies:
        for patho in pathologies:
            px = int(W * patho.get('x', 50) / 100)
            py = int(H * patho.get('y', 50) / 100)
            label = patho.get('label', 'Anomalie')
            rayon = max(20, int(min(W, H) / 15))
            rouge = (255, 40, 40)
            # Double cercle
            draw.ellipse([px - rayon, py - rayon, px + rayon, py + rayon], outline=rouge, width=ep + 2)
            draw.ellipse([px - rayon - 6, py - rayon - 6, px + rayon + 6, py + rayon + 6], outline=(255, 100, 100), width=ep)
            # Ligne + label
            lx = px + rayon + 20
            ly = py - rayon - 15
            draw.line([(px + rayon, py - rayon // 2), (lx, ly)], fill=rouge, width=ep + 1)
            bbox_l = font.getbbox(label)
            tw_l = bbox_l[2] - bbox_l[0]
            th_l = bbox_l[3] - bbox_l[1]
            draw.rectangle([lx - 5, ly - th_l - 10, lx + tw_l + 12, ly + 8], fill=(160, 0, 0))
            draw.text((lx + 3, ly - th_l - 5), label, fill=(255, 255, 255), font=font)

    # ─────────────────────────────────────────────────
    # 6. LÉGENDE + NOTE en bas
    # ─────────────────────────────────────────────────
    legende_h = max(50, int(H / 12))
    y_leg = H - legende_h
    draw.rectangle([0, y_leg, W, H], fill=(15, 15, 25))
    
    # Items de légende
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
    
    # Note
    note = "Repères pédagogiques — Zones d'évaluation schématiques"
    draw.text((15, y_leg + 28), note, fill=(150, 150, 150), font=petite_font)

    return img_annotee

# ══════════════════════════════════════════════════════
# CONFIGURATION — SECRETS & IA
# ══════════════════════════════════════════════════════
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_KEY"]

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    model, MODEL_NAME = initialiser_gemini(GEMINI_KEY)

except Exception as e:
    st.error(f"Erreur de configuration (Vérifiez vos Secrets) : {e}")
    st.stop()

# ══════════════════════════════════════════════════════
# DESIGN DARK MODE + COULEURS
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

/* Critères OUI = Vert */
.critere-oui {
    background: linear-gradient(135deg, #0d3d0d, #1a5a1a);
    border-radius: 10px;
    padding: 0.9rem;
    margin-bottom: 0.6rem;
    border-left: 5px solid #00c853;
    color: #ffffff;
}
.critere-oui strong { color: #4ade80; }

/* Critères NON = Rouge */
.critere-non {
    background: linear-gradient(135deg, #3d0d0d, #5a1a1a);
    border-radius: 10px;
    padding: 0.9rem;
    margin-bottom: 0.6rem;
    border-left: 5px solid #ff1744;
    color: #ffffff;
}
.critere-non strong { color: #ff6b6b; }

/* QC Global */
.qc-conforme {
    background: linear-gradient(135deg, #0d3d0d, #1a5a1a);
    border-radius: 10px;
    padding: 1rem;
    margin: 0.8rem 0;
    border: 2px solid #00c853;
    text-align: center;
    font-size: 1.2rem;
    font-weight: bold;
    color: #4ade80;
}
.qc-non-conforme {
    background: linear-gradient(135deg, #3d0d0d, #5a1a1a);
    border-radius: 10px;
    padding: 1rem;
    margin: 0.8rem 0;
    border: 2px solid #ff1744;
    text-align: center;
    font-size: 1.2rem;
    font-weight: bold;
    color: #ff6b6b;
}

/* Classification NORMAL = Vert */
.classif-normal {
    background: linear-gradient(135deg, #0a4a0a, #15751a);
    padding: 1rem;
    border-radius: 12px;
    text-align: center;
    font-size: 1.4rem;
    font-weight: bold;
    color: #4ade80;
    border: 3px solid #00c853;
    margin-bottom: 1rem;
    text-shadow: 0 0 10px rgba(0,200,83,0.5);
}

/* Classification PATHOLOGIQUE = Rouge */
.classif-patho {
    background: linear-gradient(135deg, #4a0a0a, #751515);
    padding: 1rem;
    border-radius: 12px;
    text-align: center;
    font-size: 1.4rem;
    font-weight: bold;
    color: #ff6b6b;
    border: 3px solid #ff1744;
    margin-bottom: 1rem;
    text-shadow: 0 0 10px rgba(255,23,68,0.5);
}

/* Principe en gris */
.principe {
    color: #a0a0a0;
    font-size: 0.85rem;
    font-style: italic;
    margin-bottom: 0.3rem;
}

/* Justification */
.justification {
    color: #e0e0e0;
    margin-top: 0.4rem;
}

/* Export buttons */
.export-section {
    background: #1a2235;
    border-radius: 10px;
    padding: 1rem;
    margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# PROMPT
# ══════════════════════════════════════════════════════
PROMPT = """Tu es un radiologue expert en analyse de radiographies thoraciques.
Analyse cette radiographie thoracique de face (PA).

Réponds UNIQUEMENT en JSON strict, sans markdown, sans backticks :

{
  "qualite": {
    "champ_radiographique": {"resultat": "OUI ou NON", "justification": "Expliquer si les apex pulmonaires (sommets des poumons) et les culs-de-sac costo-diaphragmatiques (angles entre les côtes et le diaphragme) sont entièrement visibles sur l'image."},
    "symetrie": {"resultat": "OUI ou NON", "justification": "Expliquer si les bords internes (médiaux) des clavicules sont équidistants de la ligne des apophyses épineuses (ligne médiane vertébrale). Mentionner si le patient était bien centré."},
    "inspiration": {"resultat": "OUI ou NON", "justification": "Compter précisément le nombre d'arcs costaux postérieurs visibles au-dessus du diaphragme du côté droit. Une bonne inspiration montre 7 à 9 arcs."},
    "conclusion_globale": "Conforme ou Non conforme"
  },
  "diagnostic": {
    "classification": "NORMAL ou PATHOLOGIQUE",
    "conclusion": "Diagnostic principal en une phrase",
    "description_semiologique": "Description détaillée en 2 à 4 phrases : transparence pulmonaire, silhouette cardiaque, médiastin, plèvre, structures osseuses."
  },
  "annotations": {
    "arcs_costaux": {"nombre_visible": 8},
    "pathologies": []
  }
}

RÈGLES IMPORTANTES :
1. classification est OBLIGATOIRE : "NORMAL" ou "PATHOLOGIQUE"
2. Si NORMAL, pathologies = []
3. Si PATHOLOGIQUE, lister les anomalies : [{"x": position_horizontale_en_pourcentage, "y": position_verticale_en_pourcentage, "label": "nom court de la pathologie"}]
4. arcs_costaux.nombre_visible = nombre exact d'arcs costaux postérieurs comptés au-dessus du diaphragme
5. conclusion_globale = "Conforme" UNIQUEMENT si les 3 critères sont "OUI". Sinon "Non conforme"."""

# ══════════════════════════════════════════════════════
# TITRE
# ══════════════════════════════════════════════════════
st.markdown("# 🫁 RadioIA — Assistant Radiographie Thoracique")
st.markdown("*Mémoire de Master en Radiologie et Imagerie Médicale — Hôpital Jamot de Yaoundé*")
st.divider()

# ══════════════════════════════════════════════════════
# LAYOUT PRINCIPAL
# ══════════════════════════════════════════════════════
col_gauche, col_droite = st.columns([1, 1.5])

with col_gauche:
    st.subheader("📝 Identification")
    p_id = st.text_input("🏷️ Identifiant radio", placeholder="RAD_001")
    p_age = st.number_input("🎂 Âge du patient", min_value=18, max_value=120, value=30)
    p_sexe = st.selectbox("👤 Sexe", ["Masculin", "Féminin"])
    img_file = st.file_uploader("🩻 Uploader la radiographie", type=['jpg', 'jpeg', 'png'])

    if img_file:
        img_file.seek(0)
        img_preview = Image.open(img_file).convert("RGB")
        st.image(img_preview, caption=f"Radio chargée — {p_id}", use_container_width=True)

    if st.button("🚀 ANALYSER ET SAUVEGARDER"):
        if not img_file:
            st.warning("⚠️ Veuillez uploader une radiographie.")
        elif not p_id:
            st.warning("⚠️ Veuillez renseigner l'identifiant radio.")
        else:
            img_file.seek(0)
            img = Image.open(img_file).convert("RGB")
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

                    # Calcul de la conformité : Conforme si et seulement si les 3 critères sont OUI
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

with col_droite:
    # ══════════════════════════════════════════════════
    # RÉSULTAT DE L'ANALYSE
    # ══════════════════════════════════════════════════
    if 'derniere_analyse' in st.session_state:
        analyse = st.session_state['derniere_analyse']
        data = analyse['data']
        qc = data['qualite']
        diag = data['diagnostic']
        classification = diag.get('classification', 'INDÉTERMINÉ')

        st.subheader(f"🔍 Résultat — {analyse['patient_id']}")

        # Image annotée
        st.image(analyse['img_annotee'], use_container_width=True)

        # Boutons zoom et téléchargement
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            with st.expander("🔎 ZOOM — Voir en grand"):
                st.image(analyse['img_annotee'], use_container_width=True)
                st.info("💡 Clic droit → 'Ouvrir l'image dans un nouvel onglet' pour zoomer davantage")
        
        with col_btn2:
            img_bytes = io.BytesIO()
            analyse['img_annotee'].save(img_bytes, format='PNG')
            img_bytes.seek(0)
            st.download_button(
                label="💾 Télécharger l'image",
                data=img_bytes,
                file_name=f"radio_annotee_{analyse['patient_id']}.png",
                mime="image/png"
            )

        st.markdown("")

        # Classification
        if classification == "NORMAL":
            st.markdown('<div class="classif-normal">✅ CLASSIFICATION : NORMAL</div>', unsafe_allow_html=True)
        elif classification == "PATHOLOGIQUE":
            st.markdown('<div class="classif-patho">⚠️ CLASSIFICATION : PATHOLOGIQUE</div>', unsafe_allow_html=True)
        else:
            st.warning(f"Classification : {classification}")

        # Critères de qualité
        st.markdown("### 📋 Critères de qualité")

        # Champ radiographique
        res_champ = qc['champ_radiographique']['resultat']
        classe_champ = "critere-oui" if res_champ == "OUI" else "critere-non"
        icone_champ = "✅" if res_champ == "OUI" else "❌"
        st.markdown(f"""<div class="{classe_champ}">
            <strong>{icone_champ} CHAMP RADIOGRAPHIQUE : {res_champ}</strong>
            <div class="principe">Principe : les apex pulmonaires et les culs-de-sac costo-diaphragmatiques doivent être entièrement visibles.</div>
            <div class="justification">→ {qc['champ_radiographique']['justification']}</div>
        </div>""", unsafe_allow_html=True)

        # Symétrie
        res_sym = qc['symetrie']['resultat']
        classe_sym = "critere-oui" if res_sym == "OUI" else "critere-non"
        icone_sym = "✅" if res_sym == "OUI" else "❌"
        st.markdown(f"""<div class="{classe_sym}">
            <strong>{icone_sym} SYMÉTRIE : {res_sym}</strong>
            <div class="principe">Principe : les bords internes des clavicules doivent être équidistants des apophyses épineuses (D1 ≈ D2).</div>
            <div class="justification">→ {qc['symetrie']['justification']}</div>
        </div>""", unsafe_allow_html=True)

        # Inspiration
        res_insp = qc['inspiration']['resultat']
        classe_insp = "critere-oui" if res_insp == "OUI" else "critere-non"
        icone_insp = "✅" if res_insp == "OUI" else "❌"
        st.markdown(f"""<div class="{classe_insp}">
            <strong>{icone_insp} INSPIRATION : {res_insp}</strong>
            <div class="principe">Principe : au moins 7 à 9 arcs costaux postérieurs doivent être visibles.</div>
            <div class="justification">→ {qc['inspiration']['justification']}</div>
        </div>""", unsafe_allow_html=True)

        # Conformité globale
        concl_qc = qc['conclusion_globale']
        if concl_qc == "Conforme":
            st.markdown('<div class="qc-conforme">✅ CONFORMITÉ GLOBALE : CONFORME</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="qc-non-conforme">❌ CONFORMITÉ GLOBALE : NON CONFORME</div>', unsafe_allow_html=True)

        # Diagnostic
        st.markdown("### 🩺 Diagnostic")
        st.markdown(f"**Conclusion :** {diag['conclusion']}")
        st.markdown(f"**Description sémiologique :** {diag['description_semiologique']}")

        pathologies = data.get('annotations', {}).get('pathologies', [])
        if pathologies:
            st.markdown("**Anomalies détectées :**")
            for i, p in enumerate(pathologies, 1):
                st.markdown(f"- 🔴 **{p.get('label', 'Anomalie')}**")

    # ══════════════════════════════════════════════════
    # HISTORIQUE + EXPORT
    # ══════════════════════════════════════════════════
    st.divider()
    st.subheader("📜 Historique des analyses")
    
    try:
        history = supabase.table("analyses").select("*").order('created_at', desc=True).execute()
        
        if history.data:
            # Affichage des 10 dernières
            for row in history.data[:10]:
                classif = row.get('classification', 'N/A')
                emoji = "✅" if classif == "NORMAL" else "⚠️" if classif == "PATHOLOGIQUE" else "❓"
                with st.expander(f"{emoji} {row['patient_id']} — {classif} — {row.get('diagnostic', '')}"):
                    st.write(f"**Âge :** {row.get('age', 'N/A')} | **Sexe :** {row.get('sexe', 'N/A')}")
                    st.write(f"**Conformité :** {row.get('conclusion_qc', 'N/A')}")
                    st.write(f"**Description :** {row.get('description', 'N/A')}")
            
            # ══════════════════════════════════════════
            # SECTION EXPORT
            # ══════════════════════════════════════════
            st.markdown("---")
            st.markdown("### 📊 Exporter les données")
            
            # Préparer le DataFrame
            df = pd.DataFrame(history.data)
            
            # Renommer les colonnes pour plus de clarté
            colonnes_renommees = {
                'patient_id': 'ID_Patient',
                'age': 'Age',
                'sexe': 'Sexe',
                'champ_radiographique': 'Champ_Resultat',
                'champ_justification': 'Champ_Justification',
                'symetrie': 'Symetrie_Resultat',
                'symetrie_justification': 'Symetrie_Justification',
                'inspiration': 'Inspiration_Resultat',
                'inspiration_justification': 'Inspiration_Justification',
                'conclusion_qc': 'Conformite_Globale',
                'diagnostic': 'Diagnostic',
                'classification': 'Classification',
                'description': 'Description_Semiologique',
                'created_at': 'Date_Analyse'
            }
            
            # Sélectionner et renommer les colonnes existantes
            colonnes_export = [col for col in colonnes_renommees.keys() if col in df.columns]
            df_export = df[colonnes_export].rename(columns=colonnes_renommees)
            
            # Ajouter des colonnes codées pour SPSS (numériques)
            if 'Champ_Resultat' in df_export.columns:
                df_export['Champ_Code'] = df_export['Champ_Resultat'].apply(lambda x: 1 if str(x).upper() == 'OUI' else 0)
            if 'Symetrie_Resultat' in df_export.columns:
                df_export['Symetrie_Code'] = df_export['Symetrie_Resultat'].apply(lambda x: 1 if str(x).upper() == 'OUI' else 0)
            if 'Inspiration_Resultat' in df_export.columns:
                df_export['Inspiration_Code'] = df_export['Inspiration_Resultat'].apply(lambda x: 1 if str(x).upper() == 'OUI' else 0)
            if 'Conformite_Globale' in df_export.columns:
                df_export['Conformite_Code'] = df_export['Conformite_Globale'].apply(lambda x: 1 if str(x).lower() == 'conforme' else 0)
            if 'Classification' in df_export.columns:
                df_export['Classification_Code'] = df_export['Classification'].apply(lambda x: 1 if str(x).upper() == 'NORMAL' else 0)
            if 'Sexe' in df_export.columns:
                df_export['Sexe_Code'] = df_export['Sexe'].apply(lambda x: 1 if str(x).lower() == 'masculin' else 2)
            
            st.info(f"📁 **{len(df_export)} analyses** disponibles à l'export")
            
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                # Export Excel
                buffer_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Analyses')
                buffer_excel.seek(0)
                
                st.download_button(
                    label="📗 Télécharger Excel (.xlsx)",
                    data=buffer_excel,
                    file_name=f"radioia_analyses_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col_exp2:
                # Export CSV (compatible SPSS)
                buffer_csv = io.StringIO()
                df_export.to_csv(buffer_csv, index=False, sep=';', encoding='utf-8-sig')
                
                st.download_button(
                    label="📊 Télécharger CSV (SPSS)",
                    data=buffer_csv.getvalue(),
                    file_name=f"radioia_analyses_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
            
            # Aperçu des données
            with st.expander("👁️ Aperçu des données exportées"):
                st.dataframe(df_export.head(10), use_container_width=True)
                st.caption("""
                **Codage pour SPSS :**
                - Champ/Symétrie/Inspiration : OUI = 1, NON = 0
                - Conformité : Conforme = 1, Non conforme = 0
                - Classification : NORMAL = 1, PATHOLOGIQUE = 0
                - Sexe : Masculin = 1, Féminin = 2
                """)
        
        else:
            st.info("📭 Aucune analyse enregistrée.")
            
    except Exception as e:
        st.warning(f"Historique indisponible : {e}")
