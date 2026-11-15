# Ce que fait le script et le lien avec le cours

## 1. Ce qui vient de notre brainstorming (et du cours de l'an dernier)

| Problème repéré | Traitement dans `code.py` | Notion du cours |
|---|---|---|
| Noms de colonnes différents (A anglais, C français) | Dictionnaires de renommage → schéma cible commun | Hétérogénéité des noms de colonnes |
| Dates : `AAAA-MM-JJ`, `JJ/MM/AAAA`, `AAAA/MM/JJ` | `pd.to_datetime` avec le format de chaque hôpital → ISO 8601 | Uniformité / format |
| Sexe : `M`, `Male`, `Female`, `H`, `Homme` | Table de correspondance → `M` / `F` | Variables catégorielles |
| `yes/no`, `Y/N`, `OUI/NON`, `0.0/1.0` | Tout en `0` / `1` (lisible par la machine) | Variables catégorielles |
| Âge en float | Converti en entier | Format des colonnes |
| Poids en kg / lb, taille en m / cm | Tout en kg et en cm | Unité des colonnes |
| Poids « trop longs » (145.7238155…) | Voir point 2 : ce n'était pas qu'un arrondi | Précision |
| Diagnostic `E11.9+I10` : plusieurs valeurs dans une case | Codes CIM-10 harmonisés + table séparée `diagnostics.csv` (1 ligne = 1 code) | Unicité / atomicité |
| PAS : valeurs bizarres | Codes -1, 999, 35 → NaN | Données aberrantes |
| Créatinine en mg/dL | Convertie en µmol/L (×88,4), unité utilisée en France | Unité des colonnes |
| Données manquantes | Profil par colonne et par hôpital + heatmap `isna` | Complétude |

## 2. Ce qu'on a ajouté en creusant les données

1. **Poids dans la mauvaise unité.** Les 20 poids à longues décimales de l'hôpital A sont en livres (et non en kg). Les 20 de l'hôpital B sont déjà en kg (et non en livres). On les détecte et on les convertit correctement. Une colonne `poids_unite_corrigee` garde la trace.
2. **Durée de séjour.** Elle vaut toujours l'écart entre les dates + une fraction de jour (0 à 0,9). On garde la valeur décimale, plus précise qu'un arrondi. On complète les 368 durées manquantes à partir des dates (`duree_completee = 1`).
3. **Le champ diagnostic est incohérent.** Un patient sans diabète ni HTA reçoit `I10` (HTA). Un patient avec HTA seule reçoit `E11` (diabète). Le diagnostic contredit les colonnes `diabete` / `hta` sur environ 7 000 lignes. Il n'est donc pas fiable : on utilise `diabete` et `hta` pour l'analyse et on signale `diag_incoherent`.
4. **Valeurs plafond / plancher.** Il y a un pic à 95 ans (342 patients) et un pic à 40 kg (111 patients), ce qui suggère une troncature à la saisie. Ces valeurs sont signalées, pas supprimées.
5. **Décès et réhospitalisation à la fois.** 17 patients sont dans ce cas, ce qui est impossible. Ils sont signalés et exclus de l'analyse (on analyse les patients vivants à la sortie).
6. **IMC calculé** (variable dérivée). Il est redondant avec poids et taille (vu en cours), donc on ne l'utilise pas en même temps qu'eux.
7. **Outliers.** On applique la règle IQR (boxplot vu en cours) et des bornes physiologiques. On signale seulement : CRP et durée de séjour sont naturellement asymétriques.

## 3. Analyse (réponses aux questions de l'énoncé)

- **Taux global** : 8,5 % de réhospitalisations à 30 jours (9 009 patients vivants à la sortie). Les classes sont très déséquilibrées (763 contre 8 246), ce qui est à prendre en compte pour un futur modèle (undersampling, oversampling ou SMOTE, vus en cours).
- **Durée de séjour** : le taux augmente avec la durée (7,3 % pour ≤ 3 j, 12 % pour > 14 j). Test de Mann-Whitney : p < 0,001.
- **Diabète** : 9,9 % contre 8,2 %, odds ratio 1,24 (Chi², p = 0,02). L'écart est faible mais significatif.
- **HTA** : 10,4 % contre 7,3 %, odds ratio 1,48 (p < 0,001). C'est le facteur le plus net.
- **Tabac, sexe, âge, PAS, créatinine, CRP** : pas de différence nette.
- **Données manquantes** : seulement 53 % de lignes complètes. Si on supprimait toutes les lignes incomplètes, on perdrait près de la moitié des patients. Le taux reste à 8,5 % sur les cas complets, donc les manquants semblent répartis au hasard. Choix : on garde toutes les lignes et chaque analyse utilise les lignes où ses variables sont renseignées.
- **Variables fiables** : les indicateurs 0/1, l'âge (sauf le plafond à 95), la durée, la CRP et la créatinine. Les variables peu fiables sont `diag` (incohérent) et `poids` (unités mélangées, plancher à 40 kg).

Les données sont synthétiques : il s'agit d'associations, pas de causes, et rien ne doit être interprété comme un résultat clinique.

## 4. Fichiers produits (`resultats/`)

`patients_harmonises.csv`, `diagnostics.csv`, `schema_cible.csv`, `profil_qualite.csv`, `resultats_analyse.json`, `fig_manquants.png`, `fig_rehospitalisation.png`, `fig_correlation.png`.
