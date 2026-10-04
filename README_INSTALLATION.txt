SCANNER DRIVE 86 — VERSION WEB MOBILE
======================================

Ce dossier contient une version PWA : elle s'ouvre dans Chrome Android et peut être
ajoutée à l'écran d'accueil comme une application.

IMPORTANT
---------
Le téléphone n'effectue pas le scan. Le serveur héberge l'application et lance
Chromium pour lire les catalogues publics. Le téléphone sert d'interface.

DEPLOIEMENT RAPIDE AVEC RENDER
------------------------------
1. Créer un compte Render.
2. Mettre ce dossier dans un dépôt GitHub.
3. Dans Render : New > Web Service > choisir le dépôt.
4. Render détectera le Dockerfile.
5. Une fois le service lancé, ouvrir l'URL depuis Android.
6. Dans Chrome Android : menu ⋮ > Ajouter à l'écran d'accueil.

INTERMARCHE
-----------
L'URL publique du Drive Intermarché Demi-Lune n'est pas renseignée dans cette V1.
Il faudra la mettre dans config.json après vérification du bon parcours Drive.

TELEGRAM
--------
Renseigner telegram_bot_token et telegram_chat_id dans config.json si tu veux les
alertes Telegram. Ne mets jamais un token dans un dépôt public GitHub.

LIMITATION DU PLAN GRATUIT
--------------------------
Un hébergement gratuit peut mettre le serveur en veille et avoir des limites.
Pour une surveillance fiable 24/7, un petit serveur payant sera préférable.

SECURITE
--------
Le programme ne demande pas d'identifiant Auchan/Intermarché/Leclerc et ne passe
aucune commande. Il analyse les informations accessibles publiquement.
