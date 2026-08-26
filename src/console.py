"""
Plateforme de détection de fraude — interface métier et d'inférence.

Ce que les ateliers font à la main dans un terminal, cette application le fait
en un clic et le montre : le pipeline s'exécute étape par étape et le graphe
s'allume au fur et à mesure, comme dans Airflow ou Jenkins.

Quatre onglets :

    Pipeline     charger → contrôler → transformer → entraîner → juger →
                 prédire → mesurer la dérive, avec le DAG en direct
    Inférence    scorer une transaction, ou un fichier entier
    Monitoring   état du service, métriques exposées, rapport de dérive
    Journal      logs/lab.log, filtrable

Lancement :
    python -m streamlit run src/console.py --server.port 8501
"""

from __future__ import annotations

import html
import json
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass, field

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as composants
import yaml
from prometheus_client.parser import text_string_to_metric_families

RACINE = pathlib.Path(__file__).resolve().parents[1]

# « streamlit run src/console.py » met src/ sur sys.path, pas la racine du
# dépôt : sans cette ligne, « from src.features import … » échoue.
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

EN_DOCKER = os.environ.get("CONSOLE_MODE", "local") == "docker"

if EN_DOCKER:
    SONDE_API = os.environ.get("API_URL", "http://api:8000")
    SONDE_PROM = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
    SONDE_GRAFANA = os.environ.get("GRAFANA_URL", "http://grafana:3000")
else:
    SONDE_API = os.environ.get("API_URL", "")  # vide = auto-détection 8001 puis 8000
    SONDE_PROM = os.environ.get("PROMETHEUS_URL", "http://localhost:9091")
    SONDE_GRAFANA = os.environ.get("GRAFANA_URL", "http://localhost:3002")

LIEN_API = "http://localhost:8001"
LIEN_PROM = "http://localhost:9091"
LIEN_GRAFANA = "http://localhost:3002"

# Tons moyens : lisibles sur fond clair comme sur fond sombre.
COULEURS = {
    "attente": "#8A9499",
    "en_cours": "#D08700",
    "reussi": "#3A9D4F",
    "echoue": "#D14437",
}
SYMBOLES = {"attente": "○", "en_cours": "◐", "reussi": "✓", "echoue": "✕"}


# =============================================================================
# Le graphe du pipeline
# =============================================================================

@dataclass
class Etape:
    cle: str
    titre: str
    sous_titre: str
    executer: object
    etat: str = "attente"
    duree: float = 0.0
    resume: str = ""
    detail: str = ""
    donnees: object = field(default=None)


def dessiner_dag(etapes: list[Etape]) -> str:
    """Rend le pipeline en SVG, coloré par l'état de chaque étape."""
    large, haut, ecart = 148, 62, 26
    marge, base = 16, 26
    total = marge * 2 + len(etapes) * large + (len(etapes) - 1) * ecart

    morceaux = [
        f'<svg viewBox="0 0 {total} {base + haut + 46}" width="100%" '
        f'style="max-width:100%;height:auto" role="img" '
        f'aria-label="Graphe du pipeline, une case par étape, colorée selon son état">',
        '<defs><marker id="fleche" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#8A9499"/></marker></defs>',
    ]

    for i, etape in enumerate(etapes):
        x = marge + i * (large + ecart)
        couleur = COULEURS[etape.etat]
        epaisseur = 2.4 if etape.etat == "en_cours" else 1.6
        remplissage = f"{couleur}1A" if etape.etat != "attente" else "none"

        morceaux.append(
            f'<rect x="{x}" y="{base}" width="{large}" height="{haut}" rx="6" '
            f'fill="{remplissage}" stroke="{couleur}" stroke-width="{epaisseur}"/>'
        )
        morceaux.append(
            f'<text x="{x + 12}" y="{base + 22}" font-size="15" fill="{couleur}" '
            f'font-weight="600" font-family="monospace">{SYMBOLES[etape.etat]}</text>'
        )
        morceaux.append(
            f'<text x="{x + 32}" y="{base + 23}" font-size="12.5" fill="{couleur}" '
            f'font-weight="600">{html.escape(etape.titre)}</text>'
        )
        morceaux.append(
            f'<text x="{x + 12}" y="{base + 42}" font-size="10.5" fill="{couleur}" '
            f'opacity="0.85">{html.escape(etape.sous_titre)}</text>'
        )
        if etape.duree:
            morceaux.append(
                f'<text x="{x + 12}" y="{base + 56}" font-size="10" fill="{couleur}" '
                f'opacity="0.7" font-family="monospace">{etape.duree:.1f} s</text>'
            )
        morceaux.append(
            f'<text x="{x + large - 10}" y="{base - 8}" font-size="10" '
            f'fill="#8A9499" text-anchor="end" font-family="monospace">{i + 1}</text>'
        )

        if i < len(etapes) - 1:
            d = x + large
            morceaux.append(
                f'<line x1="{d + 4}" y1="{base + haut / 2}" x2="{d + ecart - 4}" '
                f'y2="{base + haut / 2}" stroke="#8A9499" stroke-width="1.4" '
                f'marker-end="url(#fleche)"/>'
            )

    morceaux.append("</svg>")
    return "".join(morceaux)


def legende() -> str:
    cases = " ".join(
        f'<span style="color:{COULEURS[e]};font-weight:600">{SYMBOLES[e]} {n}</span>'
        for e, n in (
            ("attente", "en attente"),
            ("en_cours", "en cours"),
            ("reussi", "réussie"),
            ("echoue", "échouée"),
        )
    )
    return f'<div style="font-size:13px;display:flex;gap:22px">{cases}</div>'


# =============================================================================
# Sondes et lectures
# =============================================================================

def joignable(url: str, timeout: float = 2.0) -> bool:
    try:
        return requests.get(url, timeout=timeout).status_code < 500
    except Exception:
        return False


def obtenir_json(url: str, timeout: float = 3.0):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def trouver_api() -> str | None:
    candidats = [SONDE_API] if SONDE_API else [LIEN_API, "http://localhost:8000"]
    for url in candidats:
        if joignable(f"{url}/health"):
            return url
    return None


def params() -> dict:
    try:
        with open(RACINE / "params.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def metriques_modele() -> dict | None:
    chemin = RACINE / "reports" / "metriques.json"
    if not chemin.exists():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def charger_modele(_signature: float):
    """Charge le pipeline sérialisé. La signature invalide le cache après un réentraînement."""
    import joblib

    return joblib.load(RACINE / "models" / "modele.pkl")


def modele_courant():
    chemin = RACINE / "models" / "modele.pkl"
    if not chemin.exists():
        return None
    return charger_modele(chemin.stat().st_mtime)


def familles_metriques(api: str) -> list:
    try:
        r = requests.get(f"{api}/metrics", timeout=3)
        r.raise_for_status()
        return list(text_string_to_metric_families(r.text))
    except Exception:
        return []


PREFIXES_SYSTEME = ("python_", "process_")


def chercher_famille(familles: list, *fragments: str, type_attendu: str | None = None):
    candidates = [
        f
        for f in familles
        if not f.name.startswith(PREFIXES_SYSTEME)
        and not f.name.endswith("_created")
        and (type_attendu is None or f.type == type_attendu)
    ]
    for f in candidates:
        if any(fragment in f.name.lower() for fragment in fragments):
            return f
    return candidates[0] if candidates else None


def total_compteur(famille) -> float:
    if not famille:
        return 0.0
    return sum(s.value for s in famille.samples if s.name.endswith("_total"))


def cible_prometheus_up() -> tuple[bool, str]:
    data = obtenir_json(f"{SONDE_PROM}/api/v1/targets")
    if not data:
        return False, "Prometheus ne répond pas"
    for c in data.get("data", {}).get("activeTargets", []):
        if c.get("labels", {}).get("job") == "api-fraude":
            sante = c.get("health")
            return sante == "up", f"cible api-fraude : {sante}"
    return False, "aucune cible api-fraude déclarée"


# =============================================================================
# Les étapes du pipeline
# =============================================================================

def lancer(commande: list[str]) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            commande, cwd=RACINE, capture_output=True, text=True, timeout=600
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def etape_chargement(etape: Etape) -> None:
    p = params()
    chemin = RACINE / p["donnees"]["reference"]
    if not chemin.exists():
        etape.etat, etape.resume = "echoue", f"{chemin.name} introuvable"
        etape.detail = "Lancez d'abord : python -m data.generate_data"
        return
    df = pd.read_csv(chemin)
    etape.donnees = df
    etape.etat = "reussi"
    etape.resume = f"{len(df):,} lignes × {df.shape[1]} colonnes".replace(",", " ")
    etape.detail = f"Source : {p['donnees']['reference']}"


def etape_contrat(etape: Etape) -> None:
    ok, sortie = lancer([sys.executable, "-m", "pytest",
                         "tests/test_data_contract.py", "-q", "--no-header"])
    ignores = "skip" in sortie.lower()
    etape.detail = sortie
    if not ok:
        etape.etat, etape.resume = "echoue", "au moins un contrôle échoue"
    elif ignores:
        etape.etat, etape.resume = "echoue", "des contrôles sont encore vides"
    else:
        etape.etat, etape.resume = "reussi", "tous les contrôles passent"


def etape_pretraitement(etape: Etape, precedente: Etape) -> None:
    from src.features import COLONNES_ATTENDUES, construire_features

    df = precedente.donnees
    if df is None:
        etape.etat, etape.resume = "echoue", "aucune donnée en entrée"
        return
    X = construire_features(df)
    ajoutees = [c for c in X.columns if c not in COLONNES_ATTENDUES]
    etape.donnees = X
    etape.etat = "reussi"
    etape.resume = f"{len(ajoutees)} variables dérivées"
    etape.detail = "Ajoutées : " + ", ".join(ajoutees)


def etape_entrainement(etape: Etape) -> None:
    ok, sortie = lancer([sys.executable, "-m", "src.train"])
    etape.detail = sortie
    m = metriques_modele()
    if ok and m:
        etape.etat = "reussi"
        etape.resume = f"F1 = {m['f1']} · AUC = {m['roc_auc']}"
        etape.donnees = m
    else:
        etape.etat, etape.resume = "echoue", "l'entraînement a échoué"


def etape_qualite(etape: Etape) -> None:
    ok, sortie = lancer([sys.executable, "-m", "src.evaluate"])
    etape.detail = sortie
    p = params()
    m = metriques_modele() or {}
    seuil = p.get("evaluation", {}).get("seuil_f1")
    if ok:
        etape.etat = "reussi"
        etape.resume = f"F1 {m.get('f1')} ≥ seuil {seuil}"
    else:
        etape.etat = "echoue"
        etape.resume = f"F1 {m.get('f1')} < seuil {seuil} — promotion refusée"


def etape_prediction(etape: Etape, precedente: Etape) -> None:
    modele = modele_courant()
    if modele is None:
        etape.etat, etape.resume = "echoue", "models/modele.pkl absent"
        return
    p = params()
    seuil = p["evaluation"]["seuil_decision"]
    df = pd.read_csv(RACINE / p["donnees"]["derive"])
    X_source = df.sample(n=min(800, len(df)), random_state=7)

    from src.features import construire_features

    proba = modele.predict_proba(construire_features(X_source))[:, 1]
    resultat = X_source.copy()
    resultat["score"] = proba
    resultat["signalee"] = (proba >= seuil).astype(int)

    (RACINE / "reports").mkdir(exist_ok=True)
    colonnes = ["montant", "heure", "frequence_7j", "anciennete_jours",
                "type_contrepartie", "score", "signalee"]
    resultat[colonnes].to_csv(RACINE / "reports" / "predictions.csv", index=False)

    etape.donnees = resultat
    etape.etat = "reussi"
    etape.resume = f"{len(resultat)} scorées · {resultat.signalee.mean():.2%} signalées"
    etape.detail = f"Écrit dans reports/predictions.csv · seuil de décision {seuil}"


def etape_derive(etape: Etape) -> None:
    from src.drift_report import analyser, rendre_html

    p = params()
    ref = pd.read_csv(RACINE / p["donnees"]["reference"])
    cou = pd.read_csv(RACINE / p["donnees"]["derive"])
    resultats = analyser(ref, cou, p)

    (RACINE / "reports").mkdir(exist_ok=True)
    (RACINE / "reports" / "derive.html").write_text(
        rendre_html(resultats, ref, cou, p["donnees"]["reference"], p["donnees"]["derive"]),
        encoding="utf-8",
    )

    derivees = [r for r in resultats if r["psi"] >= p["derive"]["psi_alerte"]]
    nouvelles = [r["nouveau"] for r in resultats if r["nouveau"]]
    etape.donnees = resultats
    # Une dérive détectée n'est pas une panne du pipeline : l'étape réussit.
    etape.etat = "reussi"
    etape.resume = f"{len(derivees)} variables dérivées"
    if nouvelles:
        etape.resume += f" · catégorie inconnue : {', '.join(nouvelles)}"
    etape.detail = "reports/derive.html a été régénéré."


def construire_etapes() -> list[Etape]:
    return [
        Etape("chargement", "Chargement", "reference_2025.csv", etape_chargement),
        Etape("contrat", "Contrat", "6 contrôles sur la donnée", etape_contrat),
        Etape("pretraitement", "Prétraitement", "variables dérivées", etape_pretraitement),
        Etape("entrainement", "Entraînement", "forêt aléatoire", etape_entrainement),
        Etape("qualite", "Porte de qualité", "promouvoir ou refuser", etape_qualite),
        Etape("prediction", "Prédiction", "scoring par lot", etape_prediction),
        Etape("derive", "Dérive", "PSI · KS · khi²", etape_derive),
    ]


# =============================================================================
# Onglet 1 — Pipeline
# =============================================================================

def onglet_pipeline() -> None:
    st.subheader("Pipeline de bout en bout")
    st.caption(
        "Ce que les ateliers font commande par commande dans un terminal, "
        "exécuté ici en une fois. Le graphe s'allume au fur et à mesure."
    )

    colonnes = st.columns([1, 1, 3])
    lancer_tout = colonnes[0].button("▶  Lancer le pipeline", type="primary")
    reinitialiser = colonnes[1].button("Réinitialiser")

    if reinitialiser:
        st.session_state.pop("etapes", None)
        st.session_state.pop("pipeline_fini", None)

    if "etapes" not in st.session_state:
        st.session_state["etapes"] = construire_etapes()

    etapes: list[Etape] = st.session_state["etapes"]
    zone_graphe = st.empty()
    zone_etat = st.empty()
    zone_graphe.markdown(dessiner_dag(etapes), unsafe_allow_html=True)
    st.markdown(legende(), unsafe_allow_html=True)

    if lancer_tout:
        etapes = construire_etapes()
        st.session_state["etapes"] = etapes
        arrete = False

        for i, etape in enumerate(etapes):
            etape.etat = "en_cours"
            zone_graphe.markdown(dessiner_dag(etapes), unsafe_allow_html=True)
            zone_etat.info(f"Étape {i + 1}/{len(etapes)} — {etape.titre}…")

            debut = time.perf_counter()
            try:
                if etape.cle == "pretraitement":
                    etape.executer(etape, etapes[0])
                elif etape.cle == "prediction":
                    etape.executer(etape, etapes[2])
                else:
                    etape.executer(etape)
            except Exception as exc:  # noqa: BLE001
                etape.etat, etape.resume = "echoue", str(exc)[:160]
                etape.detail = str(exc)
            etape.duree = time.perf_counter() - debut

            zone_graphe.markdown(dessiner_dag(etapes), unsafe_allow_html=True)
            if etape.etat == "echoue":
                arrete = True
                break

        st.session_state["pipeline_fini"] = not arrete
        if arrete:
            zone_etat.error(
                "Le pipeline s'est arrêté. C'est le comportement attendu : "
                "une étape qui échoue ne laisse pas passer la suivante."
            )
        else:
            zone_etat.success(
                f"Pipeline terminé — {len(etapes)} étapes, "
                f"{sum(e.duree for e in etapes):.1f} s au total."
            )

    if not any(e.etat != "attente" for e in etapes):
        st.info("Cliquez sur **Lancer le pipeline** pour l'exécuter de bout en bout.")
        return

    st.divider()
    st.markdown("### Le détail, étape par étape")

    for i, etape in enumerate(etapes, 1):
        if etape.etat == "attente":
            continue
        icone = {"reussi": "✅", "echoue": "❌", "en_cours": "⏳"}[etape.etat]
        with st.expander(
            f"{icone}  {i}. {etape.titre} — {etape.resume}", expanded=(etape.etat == "echoue")
        ):
            if etape.detail:
                st.caption(etape.detail if len(etape.detail) < 200 else "")
                if len(etape.detail) >= 200:
                    st.code(etape.detail[-2500:])

            if etape.cle == "chargement" and etape.donnees is not None:
                st.dataframe(etape.donnees.head(8), use_container_width=True)
            elif etape.cle == "pretraitement" and etape.donnees is not None:
                st.dataframe(etape.donnees.head(8), use_container_width=True)
            elif etape.cle == "entrainement" and etape.donnees:
                m = etape.donnees
                c = st.columns(4)
                c[0].metric("F1", m["f1"])
                c[1].metric("Précision", m["precision"])
                c[2].metric("Rappel", m["rappel"])
                c[3].metric("ROC AUC", m["roc_auc"])
            elif etape.cle == "prediction" and etape.donnees is not None:
                d = etape.donnees
                c = st.columns(3)
                c[0].metric("Transactions scorées", len(d))
                c[1].metric("Signalées", f"{d.signalee.mean():.2%}")
                c[2].metric("Score moyen", f"{d.score.mean():.4f}")
                st.dataframe(
                    d.groupby("type_contrepartie").signalee.mean().mul(100).round(1)
                    .rename("% signalé").reset_index(),
                    use_container_width=True, hide_index=True,
                )
            elif etape.cle == "derive" and etape.donnees:
                st.dataframe(
                    pd.DataFrame([
                        {"variable": r["variable"], "PSI": round(r["psi"], 3),
                         "verdict": r["verdict"], "évolution": r["detail"],
                         "nouvelle catégorie": r["nouveau"] or "—"}
                        for r in etape.donnees
                    ]),
                    use_container_width=True, hide_index=True,
                )


# =============================================================================
# Onglet 2 — Inférence
# =============================================================================

def onglet_inference(api: str | None) -> None:
    st.subheader("Inférence")

    if api:
        st.caption(f"Les prédictions passent par le service : {api}")
    else:
        st.caption(
            "Aucun service ne répond : les prédictions utilisent directement "
            "models/modele.pkl. Lancez `docker compose up -d` pour passer par l'API."
        )

    unitaire, lot = st.tabs(["Une transaction", "Un fichier"])

    with unitaire:
        with st.form("form_predire"):
            c = st.columns(5)
            montant = c[0].number_input("Montant (FCFA)", value=45000.0, min_value=0.0, step=1000.0)
            heure = c[1].number_input("Heure", value=21, min_value=0, max_value=23)
            frequence = c[2].number_input("Transactions / 7 j", value=4, min_value=0)
            anciennete = c[3].number_input("Ancienneté (jours)", value=35, min_value=0)
            contrepartie = c[4].selectbox(
                "Contrepartie", ["particulier", "agent", "facture", "marchand"]
            )
            envoye = st.form_submit_button("Évaluer la transaction", type="primary")

        if envoye:
            charge = {
                "montant": float(montant), "heure": int(heure),
                "frequence_7j": int(frequence), "anciennete_jours": int(anciennete),
                "type_contrepartie": contrepartie,
            }
            reponse = None
            if api:
                try:
                    r = requests.post(f"{api}/predict", json=charge, timeout=5)
                    r.raise_for_status()
                    reponse = r.json()
                except Exception as exc:  # noqa: BLE001
                    st.warning(f"Le service n'a pas répondu ({exc}) — calcul local.")
            if reponse is None:
                modele = modele_courant()
                if modele is None:
                    st.error("models/modele.pkl est absent. Lancez le pipeline.")
                    return
                from src.features import construire_features

                p = params()
                score = float(modele.predict_proba(construire_features(pd.DataFrame([charge])))[0][1])
                reponse = {
                    "score": round(score, 4),
                    "signalee": bool(score >= p["evaluation"]["seuil_decision"]),
                    "seuil_decision": p["evaluation"]["seuil_decision"],
                    "version_modele": p["version_modele"],
                }

            c = st.columns(3)
            c[0].metric("Score de fraude", f"{reponse['score']:.4f}")
            c[1].metric("Seuil de décision", reponse["seuil_decision"])
            c[2].metric("Modèle", reponse["version_modele"])
            if reponse["signalee"]:
                st.error("🚩 **Transaction signalée** — à transmettre à un analyste.")
            else:
                st.success("✅ **Transaction normale** — laissée passer.")

            if contrepartie == "marchand":
                st.warning(
                    "`marchand` n'existe pas dans les données d'entraînement. Le modèle "
                    "ne refuse pas cette transaction : il l'encode en vecteur nul et se "
                    "prononce quand même. C'est le sujet de l'atelier 3."
                )

    with lot:
        p = params()
        choix = st.selectbox(
            "Jeu à scorer",
            [p["donnees"]["reference"], p["donnees"]["derive"]],
            format_func=lambda c: f"{c}  ({'trafic 2025' if '2025' in c else 'trafic 2026'})",
        )
        combien = st.slider("Nombre de transactions", 100, 2000, 800, step=100)

        if st.button("Scorer le fichier", type="primary"):
            modele = modele_courant()
            if modele is None:
                st.error("models/modele.pkl est absent. Lancez le pipeline.")
                return
            from src.features import construire_features

            df = pd.read_csv(RACINE / choix)
            ech = df.sample(n=min(combien, len(df)), random_state=7)
            proba = modele.predict_proba(construire_features(ech))[:, 1]
            seuil = p["evaluation"]["seuil_decision"]
            ech = ech.assign(score=proba, signalee=(proba >= seuil).astype(int))

            c = st.columns(3)
            c[0].metric("Scorées", len(ech))
            c[1].metric("Signalées", f"{ech.signalee.mean():.2%}")
            c[2].metric("Score moyen", f"{ech.score.mean():.4f}")

            st.markdown("**Taux de signalement par contrepartie**")
            st.bar_chart(
                ech.groupby("type_contrepartie").signalee.mean().mul(100).round(1),
                y_label="% signalé", color="#D14437",
            )
            st.markdown("**Les vingt scores les plus élevés**")
            st.dataframe(
                ech.nlargest(20, "score")[
                    ["montant", "heure", "frequence_7j", "anciennete_jours",
                     "type_contrepartie", "score", "signalee"]
                ],
                use_container_width=True, hide_index=True,
            )


# =============================================================================
# Onglet 3 — Monitoring
# =============================================================================

def onglet_monitoring(api: str | None) -> None:
    st.subheader("Monitoring")

    st.markdown("### État des services")
    lignes = []
    if api:
        sante = obtenir_json(f"{api}/health") or {}
        lignes.append(("Service de prédiction", True, f"{api} — {sante.get('version_modele', '?')}"))
    else:
        lignes.append(("Service de prédiction", False, "aucun service ne répond"))

    prom_ok, detail_prom = cible_prometheus_up()
    lignes.append(("Prometheus", prom_ok, f"{LIEN_PROM} — {detail_prom}"))
    lignes.append(("Grafana", joignable(f"{SONDE_GRAFANA}/api/health"), LIEN_GRAFANA))

    for titre, ok, detail in lignes:
        st.markdown(f"{'✅' if ok else '❌'} **{titre}** — {detail}")

    if not api:
        st.info("Démarrez la pile : `docker compose up -d --build`")
    else:
        st.markdown("### Métriques exposées par le service")
        familles = familles_metriques(api)
        f_pred = chercher_famille(familles, "prediction", type_attendu="counter")
        f_lat = chercher_famille(familles, "latence", "inference", "duree",
                                 type_attendu="histogram")
        f_score = chercher_famille(familles, "score", type_attendu="gauge")

        if not f_pred:
            st.warning(
                "Le service n'expose aucune métrique métier. C'est l'état de départ "
                "de l'atelier 2 : il répond, mais il n'est pas observable."
            )
        else:
            c = st.columns(3)
            c[0].metric("Prédictions servies", int(total_compteur(f_pred)))
            c[1].metric("Histogramme de latence", f_lat.name if f_lat else "—")
            c[2].metric("Jauge de score", f_score.name if f_score else "—")
            labels = sorted({k for s in f_pred.samples for k in s.labels})
            st.caption("Labels portés par le compteur : " + ", ".join(labels))

        st.markdown(f"[Ouvrir le tableau de bord Grafana]({LIEN_GRAFANA})")

    st.divider()
    st.markdown("### Dérive des données")

    rapport = RACINE / "reports" / "derive.html"
    if not rapport.exists():
        st.info("Aucun rapport. Lancez le pipeline, étape 7.")
        return

    predictions = RACINE / "reports" / "predictions.csv"
    if predictions.exists():
        d = pd.read_csv(predictions)
        if "type_contrepartie" in d and (d.type_contrepartie == "marchand").any():
            segment = d.groupby(d.type_contrepartie == "marchand").signalee.mean()
            c = st.columns(2)
            c[0].metric("Trafic historique", f"{segment.get(False, 0):.2%}")
            c[1].metric("Segment marchand", f"{segment.get(True, 0):.2%}", delta="dérive localisée")
            st.caption(
                "La dérive ne touche pas tout le trafic. Le modèle n'est pas cassé : "
                "il est aveugle à une population qui n'existait pas."
            )

    with st.expander("Rapport de dérive complet"):
        composants.html(rapport.read_text(encoding="utf-8"), height=900, scrolling=True)


# =============================================================================
# Onglet 4 — Journal
# =============================================================================

SOURCES = {
    "train": "entraînement",
    "evaluate": "porte de qualité",
    "replay": "rejeu de trafic",
    "derive": "rapport de dérive",
    "serve": "service de prédiction",
}


def onglet_journal() -> None:
    st.subheader("Journal — logs/lab.log")
    st.caption(
        "Tout ce que produisent l'entraînement, la porte de qualité, le rejeu, "
        "le rapport de dérive et le service."
    )

    chemin = RACINE / "logs" / "lab.log"
    if not chemin.exists():
        st.info("Aucun journal pour l'instant. Il apparaîtra au premier entraînement.")
        return

    lignes = chemin.read_text(encoding="utf-8", errors="replace").splitlines()

    colonnes = st.columns([2, 1, 1])
    sources = colonnes[0].multiselect(
        "Sources", list(SOURCES), default=list(SOURCES),
        format_func=lambda s: f"{s} — {SOURCES[s]}",
    )
    niveau_min = colonnes[1].selectbox("Niveau", ["INFO", "WARNING", "ERROR"])
    combien = colonnes[2].number_input("Lignes", 20, 2000, 200, step=20)

    ordre = ["INFO", "WARNING", "ERROR"]
    acceptes = set(ordre[ordre.index(niveau_min):])

    retenues = []
    for ligne in lignes:
        morceaux = [m.strip() for m in ligne.split("|", 3)]
        if len(morceaux) < 4:
            continue
        _, source, niveau, _ = morceaux
        if source in sources and niveau in acceptes:
            retenues.append(ligne)

    st.caption(f"{len(retenues)} ligne(s) sur {len(lignes)} — les plus récentes en bas.")
    st.code("\n".join(retenues[-int(combien):]) or "(rien ne correspond)", language="log")

    anomalies = [x for x in retenues if "| ERROR" in x or "| WARNING" in x]
    if anomalies:
        st.warning(f"{len(anomalies)} ligne(s) en avertissement ou en erreur.")

    st.download_button(
        "Télécharger le journal", chemin.read_bytes(),
        file_name="lab.log", mime="text/plain",
    )


# =============================================================================
# Assemblage
# =============================================================================

def principal() -> None:
    st.set_page_config(
        page_title="Détection de fraude — plateforme",
        page_icon="🛡️",
        layout="wide",
    )

    st.title("Détection de fraude mobile money")
    st.caption(
        "Plateforme d'inférence et de supervision · Togo AI Summer School 2026 · "
        + ("mode Docker" if EN_DOCKER else "mode local")
    )

    api = trouver_api()

    with st.sidebar:
        st.markdown("### État")
        st.markdown(f"{'🟢' if api else '🔴'} Service — `{api or 'hors ligne'}`")
        prom_ok, _ = cible_prometheus_up()
        st.markdown(f"{'🟢' if prom_ok else '🔴'} Prometheus")
        st.markdown(f"{'🟢' if joignable(f'{SONDE_GRAFANA}/api/health') else '🔴'} Grafana")

        m = metriques_modele()
        if m:
            st.divider()
            st.markdown("### Modèle en place")
            st.markdown(f"`{m['version_modele']}`")
            st.metric("F1", m["f1"])
            st.caption(f"Seuil de décision : {m['seuil_decision']}")

        st.divider()
        if st.button("Rafraîchir", use_container_width=True):
            st.rerun()
        st.markdown(
            f"[API]({LIEN_API}/docs) · [Prometheus]({LIEN_PROM}) · [Grafana]({LIEN_GRAFANA})"
        )

    pipeline, inference, monitoring, journal = st.tabs(
        ["Pipeline", "Inférence", "Monitoring", "Journal"]
    )
    with pipeline:
        onglet_pipeline()
    with inference:
        onglet_inference(api)
    with monitoring:
        onglet_monitoring(api)
    with journal:
        onglet_journal()


principal()
