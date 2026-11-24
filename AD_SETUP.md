# Authentification Active Directory

L'application valide les mots de passe uniquement auprès d'Active Directory quand `AUTH_MODE=AD` (mode par défaut). Il n'y a alors aucun repli vers les mots de passe Django locaux. `AUTH_MODE=LOCAL` est réservé aux environnements de développement explicitement isolés.

## Configuration

1. Installer les dépendances avec `python -m pip install -r requirements.txt`.
2. Copier `.env.example` en `.env` à la racine du projet, ou injecter les mêmes variables dans le service qui lance Django.
3. Faire compléter `AD_BIND_DN` et `AD_BIND_PASSWORD` par l'équipe Active Directory dans le gestionnaire de secrets du serveur. Ce compte doit avoir uniquement les droits de lecture nécessaires. Ne pas committer `.env`.
4. Faire confirmer `AD_BASE_DN`, les suffixes UPN, le contrôleur, le port et le certificat par l'équipe AD.

Le mode `ldaps` utilise le port 636 par défaut. StartTLS utilise normalement le port 389. `AD_TLS=aucun` est également accepté sur un réseau explicitement approuvé, généralement avec le port 389; LDAP simple ne chiffre pas les identifiants et le contrôleur peut refuser les binds non protégés selon sa politique. La vérification des certificats reste activée pour `ldaps` et `starttls`. Le nom d'hôte doit correspondre au certificat du contrôleur; si le certificat ne contient pas l'adresse IP comme SAN, configurer son nom DNS complet dans `AD_HOST`.

## Approbation d'accès

Au premier identifiant AD valide, Django crée un compte local sans mot de passe utilisable et une demande en attente. Aucun cookie de session n'est créé avant l'approbation. Les administrateurs déjà autorisés sont conservés par la migration. Ils voient le compteur des demandes dans le menu « Demandes d'accès ».

L'approbation rattache le compte à une agence active, accorde le rôle `GESTIONNAIRE` et autorise la session. Un refus n'accorde aucun accès. Les rôles `ADMIN` restent attribués séparément par un administrateur habilité.

Les collaborateurs doivent exister dans AD et utiliser leur `sAMAccountName`, leur UPN autorisé ou la forme `BCB\\identifiant`. Le compte de service et le mot de passe ne sont jamais enregistrés dans le dépôt.

## Mise en service

Après configuration des secrets, exécuter `python manage.py migrate`, puis redémarrer le service. Les administrateurs déjà habilités sont approuvés par la migration et doivent correspondre à un compte AD actif.

Sur une nouvelle installation sans administrateur historique, un opérateur serveur de confiance doit exécuter `python manage.py bootstrap_ad_admin`. La commande demande les identifiants sans les inscrire dans l'historique du shell, les valide auprès d'AD puis crée le premier administrateur habilité. Elle ne doit être utilisée que pour cette initialisation.
