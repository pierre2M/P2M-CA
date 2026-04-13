# P2M-CA - Registre sémantique d'interactions multi-acteurs


**Auteur :** Pierre Musseau-Milesi  
**Version :** 2.1 — Avril 2026  
**Licence :** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

[![Licence: CC BY-NC-SA 4.0](https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc-sa/4.0/)


Le modèle repose sur **trois primitives formelles** :
- **L'acteur** — toute entité identifiable (personne, organisation, règle, bien commun, algorithme…)
- **L'interaction** — événement mettant en relation deux acteurs ou plus, identifié par un URI
- **L'écriture** — unité élémentaire du registre, associant un acteur, une interaction, un sens (DÉBIT/CRÉDIT) et un contenu libre en markdown

La **règle constitutive R1** (symétrie relationnelle) garantit que toute interaction produit des écritures miroirs entre acteurs, encodant la double face de l'asset-actif.


---

## Architecture du prototype (v2.1)

Le prototype local est construit sur :

- **Python / SQLite** — moteur de registre et schéma de données
- **ChromaDB** — RAG (Retrieval-Augmented Generation) par acteur
- **FastAPI** — interface web
- **Ollama / Mistral + API Claude** — agents conversationnels

Fonctionnalités implémentées : schéma URI (slug lisible + DID:key W3C), couche C-AGENT, workflow de validation asynchrone multi-acteur, co-validation, vérification automatique de la symétrie R1 (`check_symmetry.py`), chaînage des écritures via `ecriture_anterieure_uri`.

---

## Structure du dépôt

```
P2M-CA/
├── README.md
├── LICENSE-CC               # Licence CC BY-NC-SA 4.0 (documentation, modèle)
├── LICENSE-AGPL             # Licence AGPL-3.0 (code source .py et .js)
├── NOTICE.md                # Attribution et conditions de réutilisation
├── docs/
│   ├── P2M-CA_v2_1_document_complet.docx   # Document théorique complet
│   └── P2M-CA_v2_prototype_v21.docx        # Documentation du prototype
└── prototype/
    └── [fichiers du prototype]
```

---

## Licences

Ce dépôt utilise un double régime de licences :

### Documentation et modèle (`.docx`, `.md`, `.yaml`, `.json`)
> **Creative Commons Attribution – Pas d'utilisation commerciale – Partage dans les mêmes conditions 4.0 International (CC BY-NC-SA 4.0)**  
> Voir [`LICENSE-CC`](./LICENSE-CC) — https://creativecommons.org/licenses/by-nc-sa/4.0/

### Code source (`.py`, `.js`)
> **GNU Affero General Public License v3.0 (AGPL-3.0)**  
> Voir [`LICENSE-AGPL`](./LICENSE-AGPL) — https://www.gnu.org/licenses/agpl-3.0.html

Toute **utilisation commerciale** de l'un ou l'autre composant est soumise à autorisation préalable et écrite de l'auteur.

---

## Citation

Si vous utilisez ou adaptez ce travail, merci de citer :

```
Musseau-Milesi, Pierre (2026). P2M-CA — Registre sémantique d'interactions multi-acteurs, v2.1.
Dépôt GitHub : https://github.com/[votre-compte]/P2M-CA
Licence : CC BY-NC-SA 4.0 / AGPL-3.0
```

---

## Contact

Pour toute question, collaboration ou demande d'autorisation commerciale : pierremusseau@proton.me
