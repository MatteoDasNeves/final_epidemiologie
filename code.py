# =============================================================================
# TP FIA4 - Harmonisation et qualité des données de santé
# Script reproductible : exploration -> schéma cible -> harmonisation
#                        -> contrôles qualité -> analyse réhospitalisation 30j
# Données synthétiques : aucun résultat ne doit être lu comme un résultat clinique.
# =============================================================================

import json
import os

import matplotlib
matplotlib.use("Agg")  # pour sauvegarder les figures sans fenêtre
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

DOSSIER = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(DOSSIER, "resultats")
os.makedirs(SORTIE, exist_ok=True)


def titre(texte):
    print("\n" + "=" * 70)
    print(texte)
    print("=" * 70)


# =============================================================================
# 1. CHARGEMENT ET EXPLORATION DES 3 SOURCES
# =============================================================================
titre("1. Chargement et exploration")

# On lit tout en texte (dtype=str) pour ne rien perdre avant de convertir nous-mêmes
A = pd.read_csv(os.path.join(DOSSIER, "hopital_A.csv"), dtype=str)
B = pd.read_csv(os.path.join(DOSSIER, "hopital_B.csv"), dtype=str)
C = pd.read_csv(os.path.join(DOSSIER, "hopital_C.csv"), dtype=str)

for nom, df in [("A", A), ("B", B), ("C", C)]:
    print(f"\nHôpital {nom} : {df.shape[0]} lignes, {df.shape[1]} colonnes")
    print("Colonnes :", list(df.columns))
    print("Valeurs manquantes :", int(df.isna().sum().sum()))
    print("Lignes dupliquées :", int(df.duplicated().sum()))
    print("Identifiants dupliqués :", int(df.iloc[:, 0].duplicated().sum()))


# =============================================================================
# 2. SCHÉMA CIBLE COMMUN : on renomme les colonnes des 3 hôpitaux
# =============================================================================
titre("2. Renommage vers le schéma cible")

renommage_A = {
    "id": "id_patient", "date_adm": "date_entree", "date_dis": "date_sortie",
    "gender": "sexe", "weight": "poids_kg", "height_m": "taille_cm",
    "smoker": "tabac", "diabetes": "diabete", "hypertension": "hta",
    "icu": "reanimation", "los": "duree_sejour", "readmit30": "rehosp_30j",
    "death": "deces", "diag": "diag", "sbp": "pas",
    "creatinine": "creatinine", "crp": "crp",
}
renommage_B = {
    "patient": "id_patient", "admit": "date_entree", "discharge": "date_sortie",
    "gender": "sexe", "weight_lb": "poids_kg", "height_cm": "taille_cm",
    "smoking": "tabac", "diab": "diabete", "htn": "hta", "icu": "reanimation",
    "stay_days": "duree_sejour", "readmission": "rehosp_30j",
    "mortality": "deces", "diagnosis": "diag", "blood_pressure": "pas",
    "creat": "creatinine", "CRP": "crp",
}
renommage_C = {
    "taille": "taille_cm", "poids": "poids_kg", "duree": "duree_sejour",
    "creatininémie": "creatinine", "CRP": "crp",
}

A = A.rename(columns=renommage_A)
B = B.rename(columns=renommage_B)
C = C.rename(columns=renommage_C)

# On garde la trace de l'hôpital d'origine (important pour l'analyse et la traçabilité)
A["hopital"] = "A"
B["hopital"] = "B"
C["hopital"] = "C"


# =============================================================================
# 3. HARMONISATION HÔPITAL PAR HÔPITAL (ce qui dépend de la source)
# =============================================================================
titre("3. Harmonisation spécifique à chaque source")

# --- 3.1 Dates : 3 formats différents -> format ISO 8601 (AAAA-MM-JJ) ---------
formats_dates = {"A": "%Y-%m-%d", "B": "%d/%m/%Y", "C": "%Y/%m/%d"}
for df in [A, B, C]:
    fmt = formats_dates[df["hopital"].iloc[0]]
    for col in ["date_entree", "date_sortie"]:
        df[col] = pd.to_datetime(df[col], format=fmt, errors="coerce")


# --- 3.2 Poids : vérification des unités -----------------------------------
# Dans notre brainstorming on avait remarqué des poids "trop longs"
# (ex : 145.7238155555). En regardant de plus près, ce ne sont pas juste des
# arrondis : ce sont des valeurs écrites dans la MAUVAISE unité.
#   - A (censé être en kg) : 20 valeurs à longues décimales ~ 96-206 -> en livres
#   - B (censé être en lb) : 20 valeurs à longues décimales ~ 40-97  -> déjà en kg
def decimales_longues(serie):
    """True si la valeur a plus de 2 chiffres après la virgule."""
    partie_dec = serie.str.split(".").str[1].fillna("")
    return partie_dec.str.len() > 2

LB_EN_KG = 0.453592

for df in [A, B, C]:
    df["poids_unite_corrigee"] = 0

# Hôpital A : kg, sauf valeurs à longues décimales = livres
masque = decimales_longues(A["poids_kg"])
A["poids_kg"] = pd.to_numeric(A["poids_kg"], errors="coerce")
A.loc[masque, "poids_kg"] = A.loc[masque, "poids_kg"] * LB_EN_KG
A.loc[masque, "poids_unite_corrigee"] = 1
print(f"A : {masque.sum()} poids en livres convertis en kg")

# Hôpital B : livres, sauf valeurs à longues décimales = déjà en kg
masque = decimales_longues(B["poids_kg"])
B["poids_kg"] = pd.to_numeric(B["poids_kg"], errors="coerce")
B.loc[~masque, "poids_kg"] = B.loc[~masque, "poids_kg"] * LB_EN_KG
B.loc[masque, "poids_unite_corrigee"] = 1
print(f"B : {(~masque).sum()} poids convertis lb -> kg, "
      f"{masque.sum()} déjà en kg laissés tels quels")

C["poids_kg"] = pd.to_numeric(C["poids_kg"], errors="coerce")


# --- 3.3 Taille : tout en cm ------------------------------------------------
A["taille_cm"] = pd.to_numeric(A["taille_cm"], errors="coerce") * 100   # m -> cm
B["taille_cm"] = pd.to_numeric(B["taille_cm"], errors="coerce")
C["taille_cm"] = pd.to_numeric(C["taille_cm"], errors="coerce")
masque = C["taille_cm"] < 3          # quelques tailles saisies en mètres
C.loc[masque, "taille_cm"] = C.loc[masque, "taille_cm"] * 100
print(f"C : {masque.sum()} tailles en mètres converties en cm")


# --- 3.4 Pression artérielle : valeurs "codes" qui ne sont pas des mesures --
# Chaque hôpital a SA valeur bidon répétée 10 fois : -1 (A), 999 (B), 35 (C).
# Ce sont des codes "non mesuré" -> on les remplace par NaN (≠ 0 !)
codes_pas = {"A": -1, "B": 999, "C": 35}
for df in [A, B, C]:
    code = codes_pas[df["hopital"].iloc[0]]
    df["pas"] = pd.to_numeric(df["pas"], errors="coerce")
    n = (df["pas"] == code).sum()
    df.loc[df["pas"] == code, "pas"] = np.nan
    print(f"{df['hopital'].iloc[0]} : {n} PAS = {code} remplacées par NaN")


# =============================================================================
# 4. ASSEMBLAGE + HARMONISATION COMMUNE
# =============================================================================
titre("4. Assemblage des 3 hôpitaux")

colonnes_finales = [
    "id_patient", "hopital", "date_entree", "date_sortie", "age", "sexe",
    "poids_kg", "taille_cm", "tabac", "diabete", "hta", "reanimation",
    "duree_sejour", "rehosp_30j", "deces", "diag", "pas", "creatinine", "crp",
    "poids_unite_corrigee",
]
df = pd.concat([A[colonnes_finales], B[colonnes_finales], C[colonnes_finales]],
               ignore_index=True)
print("Taille du jeu fusionné :", df.shape)

# Unicité des patients entre hôpitaux
print("Identifiants en double entre hôpitaux :", df["id_patient"].duplicated().sum())


# --- 4.1 Sexe : M/F (Male, Female, Homme, H...) ------------------------------
correspondance_sexe = {"M": "M", "MALE": "M", "H": "M", "HOMME": "M",
                       "F": "F", "FEMALE": "F", "FEMME": "F"}
df["sexe"] = df["sexe"].str.strip().str.upper().map(correspondance_sexe)
print("Sexe :", df["sexe"].value_counts(dropna=False).to_dict())


# --- 4.2 Variables oui/non -> 1/0 (yes/no, Y/N, OUI/NON, 0.0/1.0) -------------
# On choisit 1/0 (entier) : lisible par la machine et pratique pour les moyennes
correspondance_binaire = {"YES": 1, "Y": 1, "OUI": 1, "1": 1, "1.0": 1,
                          "NO": 0, "N": 0, "NON": 0, "0": 0, "0.0": 0}
binaires = ["tabac", "diabete", "hta", "reanimation", "rehosp_30j", "deces"]
for col in binaires:
    df[col] = df[col].str.strip().str.upper().map(correspondance_binaire).astype("Int64")


# --- 4.3 Numériques ----------------------------------------------------------
for col in ["age", "duree_sejour", "creatinine", "crp"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["age"] = df["age"].round().astype("Int64")            # âge = entier
df["poids_kg"] = df["poids_kg"].round(1)                  # 1 décimale suffit
df["taille_cm"] = df["taille_cm"].round().astype("Int64")

# Créatinine : mg/dL -> µmol/L (unité utilisée en France), 1 mg/dL = 88.4 µmol/L
df["creatinine_umol_l"] = (df["creatinine"] * 88.4).round(0)
df = df.drop(columns="creatinine")


# --- 4.4 Durée de séjour -------------------------------------------------------
# Vérification de cohérence : duree_sejour ≈ date_sortie - date_entree
ecart_dates = (df["date_sortie"] - df["date_entree"]).dt.days
print("Sorties avant entrées :", int((ecart_dates < 0).sum()))
print("Écart duree_sejour - dates (jours) :",
      (df["duree_sejour"] - ecart_dates).describe().round(2).to_dict())
# -> la durée est toujours égale à l'écart des dates + une fraction de jour (0 à 0.9).
#    On GARDE la valeur décimale (plus précise que l'arrondi entier)
#    et on complète les durées manquantes à partir des dates quand c'est possible.
manque = df["duree_sejour"].isna() & ecart_dates.notna()
df.loc[manque, "duree_sejour"] = ecart_dates[manque]
df["duree_completee"] = manque.astype(int)
print(f"Durées de séjour complétées à partir des dates : {manque.sum()}")


# --- 4.5 Diagnostic : codes harmonisés en CIM-10 -------------------------------
# A : I10, E11.9, E11.9+I10 | B : HTA, DM2, DM2|HTA | C : HTA, E11, E11/HTA
def harmoniser_diag(valeur):
    if pd.isna(valeur):
        return np.nan
    codes = []
    for morceau in str(valeur).replace("|", "+").replace("/", "+").split("+"):
        morceau = morceau.strip().upper()
        if morceau in ["HTA", "I10"]:
            codes.append("I10")
        elif morceau in ["DM2", "E11", "E11.9"]:
            codes.append("E11")
    return "+".join(sorted(set(codes)))

df["diag"] = df["diag"].apply(harmoniser_diag)
print("Diagnostics harmonisés :", df["diag"].value_counts(dropna=False).to_dict())

# Table séparée des diagnostics (idée du brainstorming) : une ligne = un code.
# "E11+I10" n'est pas atomique, on l'éclate en 2 lignes.
table_diag = df[["id_patient", "diag"]].dropna().copy()
table_diag["code_diag"] = table_diag["diag"].str.split("+")
table_diag = table_diag.explode("code_diag")
table_diag["libelle"] = table_diag["code_diag"].map(
    {"E11": "Diabète de type 2", "I10": "Hypertension essentielle"})
table_diag = table_diag.drop(columns="diag")


# --- 4.6 IMC (variable dérivée) ----------------------------------------------
# Attention : l'IMC est redondant avec poids et taille (vu en cours).
# On le calcule pour l'analyse, mais on ne l'utilise pas EN MÊME TEMPS que poids/taille.
df["imc"] = (df["poids_kg"] / (df["taille_cm"] / 100) ** 2).round(1)


# =============================================================================
# 5. CONTRÔLES QUALITÉ (cohérence, valeurs suspectes)
# =============================================================================
titre("5. Contrôles qualité")

# 5.1 Diagnostic vs indicateurs diabete/hta : sont-ils cohérents ?
diag_dit_diabete = df["diag"].str.contains("E11", na=False)
diag_dit_hta = df["diag"].str.contains("I10", na=False)
print("\nTableau croisé diag x (diabete, hta) :")
print(pd.crosstab(df["diag"], [df["diabete"], df["hta"]]))
# Constat : un patient SANS diabète ni HTA reçoit le code I10 (HTA),
# et un patient avec HTA seule reçoit E11 (diabète). Le champ diag est donc
# incohérent avec les indicateurs. Pour l'analyse on se base sur diabete/hta
# (renseignés de façon homogène dans les 3 hôpitaux), et on signale diag.
df["diag_incoherent"] = (
    (diag_dit_diabete != (df["diabete"] == 1)) | (diag_dit_hta != (df["hta"] == 1))
) & df["diag"].notna() & df["diabete"].notna() & df["hta"].notna()
df["diag_incoherent"] = df["diag_incoherent"].astype(int)
print("Lignes où diag contredit diabete/hta :", df["diag_incoherent"].sum())

# 5.2 Valeurs "plafond / plancher" répétées (troncature probable à la saisie)
print("\nÂge = 95 :", (df["age"] == 95).sum(), "(pic anormal, âge probablement plafonné)")
print("Poids = 40 kg :", (df["poids_kg"] == 40).sum(), "(pic anormal, poids probablement plancher)")
df["age_plafonne"] = (df["age"] == 95).fillna(False).astype(int)
df["poids_plancher"] = (df["poids_kg"] == 40).fillna(False).astype(int)

# 5.3 Valeurs hors bornes physiologiques -> signalées (pas supprimées)
bornes = {"pas": (60, 260), "imc": (12, 70), "crp": (0, 500),
          "creatinine_umol_l": (20, 1500), "duree_sejour": (0, 365)}
for col, (mini, maxi) in bornes.items():
    hors = ((df[col] < mini) | (df[col] > maxi)).sum()
    print(f"{col} hors [{mini}, {maxi}] : {hors}")

# 5.4 Outliers statistiques avec la règle IQR (vue en cours) - on les SIGNALE
def outliers_iqr(serie):
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    return (serie < q1 - 1.5 * iqr) | (serie > q3 + 1.5 * iqr)

for col in ["poids_kg", "imc", "pas", "creatinine_umol_l", "crp", "duree_sejour"]:
    print(f"Outliers IQR {col} : {outliers_iqr(df[col]).sum()}")
# CRP et durée ont beaucoup d'outliers IQR : c'est normal, ces variables sont
# asymétriques (inflammation, longs séjours). On ne les supprime pas.

# 5.5 Incohérence décès / réhospitalisation
incoh = ((df["deces"] == 1) & (df["rehosp_30j"] == 1)).fillna(False).sum()
print(f"\nPatients décédés ET réhospitalisés : {incoh} (impossible -> signalés)")
df["deces_et_rehosp"] = ((df["deces"] == 1) & (df["rehosp_30j"] == 1)).fillna(False).astype(int)


# =============================================================================
# 6. PROFIL QUALITÉ (données manquantes)
# =============================================================================
titre("6. Profil qualité")

colonnes_metier = ["date_entree", "date_sortie", "age", "sexe", "poids_kg",
                   "taille_cm", "imc", "tabac", "diabete", "hta", "reanimation",
                   "duree_sejour", "rehosp_30j", "deces", "diag", "pas",
                   "creatinine_umol_l", "crp"]

profil = pd.DataFrame({
    "type": df[colonnes_metier].dtypes.astype(str),
    "nb_manquants": df[colonnes_metier].isna().sum(),
    "pct_manquants": (df[colonnes_metier].isna().mean() * 100).round(1),
    "nb_valeurs_distinctes": df[colonnes_metier].nunique(),
})
# % de manquants par hôpital (est-ce qu'un hôpital est moins bien renseigné ?)
for h in ["A", "B", "C"]:
    sous = df[df["hopital"] == h]
    profil[f"pct_manquants_{h}"] = (sous[colonnes_metier].isna().mean() * 100).round(1)
print(profil)

# Carte des manquants (comme dans le cours : heatmap de isna)
plt.figure(figsize=(10, 6))
sns.heatmap(df[colonnes_metier].isna(), cbar=False)
plt.title("Valeurs manquantes (blanc = manquant)")
plt.tight_layout()
plt.savefig(os.path.join(SORTIE, "fig_manquants.png"), dpi=120)
plt.close()

lignes_completes = df[colonnes_metier].dropna().shape[0]
print(f"\nLignes 100% complètes : {lignes_completes} / {len(df)} "
      f"({lignes_completes / len(df) * 100:.1f} %)")
# -> Supprimer toute ligne incomplète ferait perdre beaucoup de patients.
#    Choix : on garde toutes les lignes et on fait chaque analyse
#    sur les lignes où les variables utilisées sont renseignées.


# =============================================================================
# 7. ANALYSE ÉPIDÉMIOLOGIQUE : RÉHOSPITALISATION À 30 JOURS
# =============================================================================
titre("7. Analyse de la réhospitalisation à 30 jours")

# Population : patients vivants à la sortie et rehosp_30j connue
# (un patient décédé ne peut pas être réhospitalisé)
pop = df[(df["deces"] == 0) & df["rehosp_30j"].notna()].copy()
pop["rehosp_30j"] = pop["rehosp_30j"].astype(int)
taux_global = pop["rehosp_30j"].mean() * 100
print(f"Population analysée : {len(pop)} patients")
print(f"Taux global de réhospitalisation : {taux_global:.1f} %")
print("Équilibre des classes :", pop["rehosp_30j"].value_counts().to_dict(),
      "-> classes très déséquilibrées (à prendre en compte pour un futur modèle)")

# Groupes d'âge et d'IMC pour lire plus facilement
pop["classe_age"] = pd.cut(pop["age"].astype(float), bins=[17, 40, 60, 75, 120],
                           labels=["18-40", "41-60", "61-75", ">75"])
pop["classe_duree"] = pd.cut(pop["duree_sejour"], bins=[0, 3, 7, 14, 400],
                             labels=["<=3j", "4-7j", "8-14j", ">14j"])


# --- 7.1 Variables binaires : taux, odds ratio, test du Chi² -------------------
def analyse_binaire(data, var):
    sous = data[[var, "rehosp_30j"]].dropna()
    tab = pd.crosstab(sous[var], sous["rehosp_30j"])
    # odds ratio = (a*d)/(b*c) avec +0.5 pour éviter une division par 0
    a, b = tab.loc[1, 1] + 0.5, tab.loc[1, 0] + 0.5
    c, d = tab.loc[0, 1] + 0.5, tab.loc[0, 0] + 0.5
    odds_ratio = (a * d) / (b * c)
    chi2, p, _, _ = stats.chi2_contingency(tab)
    return {
        "variable": var,
        "n": len(sous),
        "taux_si_0 (%)": round(sous.loc[sous[var] == 0, "rehosp_30j"].mean() * 100, 1),
        "taux_si_1 (%)": round(sous.loc[sous[var] == 1, "rehosp_30j"].mean() * 100, 1),
        "odds_ratio": round(odds_ratio, 2),
        "p_value_chi2": round(p, 4),
    }

resultats_binaires = pd.DataFrame(
    [analyse_binaire(pop, v) for v in ["diabete", "hta", "tabac", "reanimation"]]
)
pop["sexe_h"] = (pop["sexe"] == "M").astype("Int64").where(pop["sexe"].notna())
resultats_binaires = pd.concat(
    [resultats_binaires, pd.DataFrame([analyse_binaire(pop, "sexe_h")])],
    ignore_index=True)
print("\nFacteurs binaires :")
print(resultats_binaires.to_string(index=False))


# --- 7.2 Variables continues : moyenne réhospitalisés vs non -------------------
# Test de Mann-Whitney (ne suppose pas une distribution normale)
lignes = []
for var in ["age", "duree_sejour", "imc", "pas", "creatinine_umol_l", "crp"]:
    sous = pop[[var, "rehosp_30j"]].dropna()
    g1 = sous.loc[sous["rehosp_30j"] == 1, var].astype(float)
    g0 = sous.loc[sous["rehosp_30j"] == 0, var].astype(float)
    _, p = stats.mannwhitneyu(g1, g0)
    lignes.append({"variable": var, "n": len(sous),
                   "moyenne_rehosp": round(g1.mean(), 1),
                   "moyenne_non_rehosp": round(g0.mean(), 1),
                   "p_value_mann_whitney": round(p, 4)})
resultats_continus = pd.DataFrame(lignes)
print("\nFacteurs continus :")
print(resultats_continus.to_string(index=False))


# --- 7.3 Durée de séjour et diabète (questions de l'énoncé) --------------------
taux_par_duree = (pop.groupby("classe_duree", observed=True)["rehosp_30j"]
                  .agg(n="count", taux="mean"))
taux_par_duree["taux"] = (taux_par_duree["taux"] * 100).round(1)
print("\nTaux par durée de séjour :\n", taux_par_duree)

taux_par_age = (pop.groupby("classe_age", observed=True)["rehosp_30j"]
                .agg(n="count", taux="mean"))
taux_par_age["taux"] = (taux_par_age["taux"] * 100).round(1)
print("\nTaux par classe d'âge :\n", taux_par_age)

taux_par_hopital = (pop.groupby("hopital")["rehosp_30j"]
                    .agg(n="count", taux="mean"))
taux_par_hopital["taux"] = (taux_par_hopital["taux"] * 100).round(1)
print("\nTaux par hôpital :\n", taux_par_hopital)


# --- 7.4 Impact des données manquantes -----------------------------------------
# On compare le taux "toutes lignes" avec le taux "lignes complètes uniquement"
complet = pop.dropna(subset=["age", "sexe", "tabac", "diabete", "hta",
                             "reanimation", "duree_sejour", "pas",
                             "creatinine_umol_l", "crp", "imc"])
taux_complet = complet["rehosp_30j"].mean() * 100
# Les patients sans rehosp_30j sont-ils différents ? (manquant au hasard ?)
manque_rehosp = df[df["rehosp_30j"].isna()]
print(f"\nCas complets : {len(complet)} / {len(pop)} patients "
      f"({len(complet) / len(pop) * 100:.1f} %)")
print(f"Taux toutes lignes : {taux_global:.1f} % | cas complets : {taux_complet:.1f} %")
print(f"Patients avec rehosp_30j manquante : {len(manque_rehosp)} "
      f"(âge moyen {manque_rehosp['age'].mean():.1f} vs {df['age'].mean():.1f})")


# --- 7.5 Figures ----------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
(taux_par_duree["taux"]).plot.bar(ax=axes[0], color="steelblue")
axes[0].set_title("Réhospitalisation selon la durée de séjour")
axes[0].set_ylabel("% réhospitalisés")
(taux_par_age["taux"]).plot.bar(ax=axes[1], color="darkorange")
axes[1].set_title("Réhospitalisation selon l'âge")
diab = resultats_binaires.set_index("variable")[["taux_si_0 (%)", "taux_si_1 (%)"]]
diab.plot.bar(ax=axes[2])
axes[2].set_title("Réhospitalisation selon les facteurs binaires")
for ax in axes:
    ax.tick_params(axis="x", rotation=0)
plt.tight_layout()
plt.savefig(os.path.join(SORTIE, "fig_rehospitalisation.png"), dpi=120)
plt.close()

# Matrice de corrélation (outil vu en cours pour la sélection de variables)
corr_cols = ["age", "poids_kg", "taille_cm", "imc", "tabac", "diabete", "hta",
             "reanimation", "duree_sejour", "pas", "creatinine_umol_l", "crp",
             "rehosp_30j"]
corr = df[corr_cols].astype(float).corr()
plt.figure(figsize=(10, 8))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0)
plt.title("Matrice de corrélation")
plt.tight_layout()
plt.savefig(os.path.join(SORTIE, "fig_correlation.png"), dpi=120)
plt.close()


# =============================================================================
# 8. EXPORTS
# =============================================================================
titre("8. Exports")

# Dates au format ISO dans le CSV
export = df.copy()
for col in ["date_entree", "date_sortie"]:
    export[col] = export[col].dt.strftime("%Y-%m-%d")

ordre = ["id_patient", "hopital", "date_entree", "date_sortie", "duree_sejour",
         "age", "sexe", "poids_kg", "taille_cm", "imc", "tabac", "diabete", "hta",
         "reanimation", "rehosp_30j", "deces", "diag", "pas",
         "creatinine_umol_l", "crp",
         # colonnes de traçabilité / qualité
         "poids_unite_corrigee", "duree_completee", "diag_incoherent",
         "age_plafonne", "poids_plancher", "deces_et_rehosp"]
export[ordre].to_csv(os.path.join(SORTIE, "patients_harmonises.csv"), index=False)
table_diag.to_csv(os.path.join(SORTIE, "diagnostics.csv"), index=False)
profil.to_csv(os.path.join(SORTIE, "profil_qualite.csv"))

# Schéma cible commun : nom, type, unité, et nom d'origine dans chaque hôpital
inverse = lambda d: {v: k for k, v in d.items()}
def noms_origine(fichier, renommage):
    colonnes = pd.read_csv(os.path.join(DOSSIER, fichier), nrows=0).columns
    return {**{c: c for c in colonnes}, **inverse(renommage)}
iA = noms_origine("hopital_A.csv", renommage_A)
iB = noms_origine("hopital_B.csv", renommage_B)
iC = noms_origine("hopital_C.csv", renommage_C)
description = {
    "id_patient": ("texte", "-", "Identifiant unique du patient"),
    "hopital": ("texte", "A/B/C", "Établissement d'origine (ajouté)"),
    "date_entree": ("date", "AAAA-MM-JJ", "Date d'admission"),
    "date_sortie": ("date", "AAAA-MM-JJ", "Date de sortie"),
    "duree_sejour": ("décimal", "jours", "Durée de séjour"),
    "age": ("entier", "années", "Âge"),
    "sexe": ("texte", "M/F", "Sexe"),
    "poids_kg": ("décimal", "kg", "Poids"),
    "taille_cm": ("entier", "cm", "Taille"),
    "imc": ("décimal", "kg/m²", "IMC calculé = poids / taille² (dérivé)"),
    "tabac": ("entier", "0/1", "Fumeur"),
    "diabete": ("entier", "0/1", "Diabète"),
    "hta": ("entier", "0/1", "Hypertension artérielle"),
    "reanimation": ("entier", "0/1", "Passage en réanimation"),
    "rehosp_30j": ("entier", "0/1", "Réhospitalisation à 30 jours"),
    "deces": ("entier", "0/1", "Décès à l'hôpital"),
    "diag": ("texte", "CIM-10", "Diagnostic principal (E11, I10, E11+I10)"),
    "pas": ("décimal", "mmHg", "Pression artérielle systolique"),
    "creatinine_umol_l": ("décimal", "µmol/L", "Créatinine (convertie depuis mg/dL)"),
    "crp": ("décimal", "mg/L", "Protéine C-réactive"),
}
schema = pd.DataFrame([
    {"variable": v, "type": t, "unite_format": u, "description": d,
     "source_A": iA.get(v, "creatinine" if v == "creatinine_umol_l" else "-"),
     "source_B": iB.get(v, "creat" if v == "creatinine_umol_l" else "-"),
     "source_C": iC.get(v, "creatininémie" if v == "creatinine_umol_l" else "-")}
    for v, (t, u, d) in description.items()
])
schema.loc[schema["variable"] == "imc", ["source_A", "source_B", "source_C"]] = "calculé"
schema.loc[schema["variable"] == "hopital", ["source_A", "source_B", "source_C"]] = "ajouté"
schema.to_csv(os.path.join(SORTIE, "schema_cible.csv"), index=False)

# Résultats d'analyse en JSON (pour le rapport)
resultats = {
    "n_total": int(len(df)),
    "n_analyse": int(len(pop)),
    "taux_rehosp_global_pct": round(taux_global, 1),
    "taux_rehosp_cas_complets_pct": round(taux_complet, 1),
    "n_cas_complets": int(len(complet)),
    "facteurs_binaires": resultats_binaires.to_dict(orient="records"),
    "facteurs_continus": resultats_continus.to_dict(orient="records"),
    "taux_par_duree": taux_par_duree.reset_index().astype(str).to_dict(orient="records"),
    "taux_par_age": taux_par_age.reset_index().astype(str).to_dict(orient="records"),
    "taux_par_hopital": taux_par_hopital.reset_index().to_dict(orient="records"),
    "qualite": {
        "poids_unite_corrigee": int(df["poids_unite_corrigee"].sum()),
        "durees_completees": int(df["duree_completee"].sum()),
        "diag_incoherents": int(df["diag_incoherent"].sum()),
        "age_plafonne_95": int(df["age_plafonne"].sum()),
        "poids_plancher_40": int(df["poids_plancher"].sum()),
        "deces_et_rehosp": int(df["deces_et_rehosp"].sum()),
    },
}
with open(os.path.join(SORTIE, "resultats_analyse.json"), "w", encoding="utf-8") as f:
    json.dump(resultats, f, ensure_ascii=False, indent=2)

print("Fichiers créés dans", SORTIE)
for fichier in sorted(os.listdir(SORTIE)):
    print(" -", fichier)
