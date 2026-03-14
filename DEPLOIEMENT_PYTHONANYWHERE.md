# Déploiement sur PythonAnywhere — Africa Mindset (www.vendonsici.com)

## Configuration PythonAnywhere

| Paramètre | Valeur |
|---|---|
| **Domaine** | `www.vendonsici.com` |
| **CNAME** | `webapp-2986820.pythonanywhere.com` |
| **Username** | `vendonsici` |
| **Python** | 3.12 |
| **Source code** | `/home/vendonsici/vendonsici` |
| **Working directory** | `/home/vendonsici/` |
| **WSGI file** | `/var/www/www_vendonsici_com_wsgi.py` |

---

## Étape 1 : Uploader le code

### Option A : Via Git (recommandé)
```bash
cd ~
git clone <votre_repo_git> vendonsici
```

### Option B : Upload manuel
1. Aller dans l'onglet **Files**
2. Uploader tous les fichiers dans `/home/vendonsici/vendonsici/`

---

## Étape 2 : Configurer la base de données MySQL

1. Aller dans l'onglet **Databases**
2. Créer une base de données MySQL :
   - Nom de la base : `vendonsici$vendonsici`
3. Informations :
   - **Host** : `vendonsici.mysql.pythonanywhere-services.com`
   - **User** : `vendonsici`
   - **Database** : `vendonsici$vendonsici`

---

## Étape 3 : Créer un virtualenv

```bash
mkvirtualenv --python=/usr/bin/python3.12 vendonsici_env
pip install -r ~/vendonsici/requirements.txt
```

Puis dans l'onglet **Web**, renseigner le chemin du virtualenv :
```
/home/vendonsici/.virtualenvs/vendonsici_env
```

---

## Étape 4 : Configurer le fichier WSGI

Cliquer sur `/var/www/www_vendonsici_com_wsgi.py` et remplacer le contenu par :

```python
import os
import sys

path = '/home/vendonsici/vendonsici'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'guineemakiti.settings'
os.environ['PYTHONANYWHERE'] = '1'
os.environ['DB_NAME'] = 'vendonsici$vendonsici'
os.environ['DB_USER'] = 'vendonsici'
os.environ['DB_PASSWORD'] = 'VOTRE_MOT_DE_PASSE_MYSQL'
os.environ['DB_HOST'] = 'vendonsici.mysql.pythonanywhere-services.com'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

---

## Étape 5 : Static files (section Web)

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/vendonsici/vendonsici/static` |
| `/media/` | `/home/vendonsici/vendonsici/media` |

---

## Étape 6 : Migrations et données initiales

```bash
cd ~/vendonsici
python manage.py migrate
python manage.py seed_products
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

---

## Étape 7 : DNS

Chez votre registrar, configurer :
- **CNAME** : `www` → `webapp-2986820.pythonanywhere.com`

Puis dans PythonAnywhere :
1. Activer HTTPS (certificat gratuit Let's Encrypt)
2. Activer **Force HTTPS**
3. Cliquer **Reload**

---

## URLs du site

| Page | URL |
|------|-----|
| Accueil | `https://www.vendonsici.com/` |
| Produit | `https://www.vendonsici.com/produit/<id>/` |
| À Propos | `https://www.vendonsici.com/a-propos/` |
| Panier | `https://www.vendonsici.com/panier/` |
| Admin Login | `https://www.vendonsici.com/admin-panel/login/` |
| Admin Dashboard | `https://www.vendonsici.com/admin-panel/` |
| Django Admin | `https://www.vendonsici.com/django-admin/` |

---

## Notes importantes

- **Compte payant** requis pour le domaine personnalisé `www.vendonsici.com`
- **Sécurité** : changer `SECRET_KEY` en production et mettre `DEBUG = False`
- **Compte gratuit** : le site s'endort après 3 mois sans renouvellement
