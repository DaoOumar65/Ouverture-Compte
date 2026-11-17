Lors de mes tests j'ai constaté beaucoup d'erreurs dont tu vas prendre ce fichier en compte afin d'ameliorer le système.

D'abord pour creer un gestionnaire on a besoin que son nom, prenom, mot de passe de 8 caractères. PAr la suite on va gerer de sorte a ce que le gestionnaire utilise son identifiant de Active Directory qui va recuperer ses informations depuis le Server AD et l'admin va juste l'approuver en tant que admissible a la session. 

J'ai cree un nouvel utilisateur et essayer de creer un nouveau dossier et meme previsualiser, après tenter d'enregistrer mais une fois dans le dossier je ne retrouvz plus ni dans la BD et meme aucun journal comme si je n'ai rien fais, ça m'est arrivé au moins 3 fois et il faut verifier cela analyser correctement puis corriger pour eviter cette fatalité.

Problème 1 : un seul formulaire de saisie pour les deux types
Aujourd'hui, la page de saisie est la même pour un particulier et un commercial. Le
commercial demande beaucoup plus d'informations, ce qui rend l'écran chargé et source
de confusion.

À faire :
- Créer deux formulaires de saisie distincts (DossierParticulierForm et
  DossierCommercialForm), avec chacun ses sections, ses champs et ses listes de choix.
- Le type est choisi à la création du dossier. L'écran de saisie s'ouvre ensuite
  uniquement avec les champs du type choisi. Le type n'est plus modifiable après la
  création.
- Les deux écrans ne doivent pas se ressembler : titres, regroupements et libellés
  propres à chaque type, pour qu'on ne puisse pas les confondre.
- Garder le modèle de données existant (pas de refonte), seulement séparer formulaires,
  vues et templates. Si une migration est nécessaire, la fournir.

Problème 2 : écarts entre le document papier et la saisie numérique
Sur le document officiel, certaines rubriques ont plusieurs cases (exemple : 4 cases à
cocher) alors que l'écran n'en propose que 2. Des informations manquent ou sont mal
organisées.

À faire :
- Comparer, formulaire par formulaire (F1 à F5 pour le particulier, puis les formulaires
  commerciaux), chaque champ et chaque case du papier avec la saisie.
- Me fournir d'abord un tableau des écarts : « rubrique du papier / champ numérique
  existant / manquant / action proposée ».
- Corriger ensuite : ajouter les champs et cases manquants, avec les mêmes choix que le
  papier, dans le même ordre que sur le formulaire, et regroupés de façon lisible.
- Utiliser le bon composant selon la nature de la réponse : cases à cocher multiples,
  boutons radio, listes déroulantes. Pour Oui/Non : boutons radio sans valeur par défaut.

Problème 3 : lisibilité de F1 (Renseignements complémentaires)
Les informations remplies sont collées aux libellés et aux bordures, presque illisibles.

À faire :
- Augmenter les espaces entre libellé et valeur, la hauteur des lignes, et le retrait
  intérieur des cellules. Police de la valeur : 10 pt minimum, sans coller aux bordures.
- Faire en sorte que les valeurs longues passent à la ligne sans déborder de la cellule.
- Vérifier le résultat à l'aperçu et à l'impression A4, sur une page par formulaire.
- Appliquer la même vérification à F3 et F4.

Contraintes à respecter
- Les déclarations FATCA, PPE, levée du secret bancaire et les consentements CREDITINFO
  doivent etre correctement mise.
- Un gestionnaire ne voit que les dossiers qu'il a créés.
- Ne pas modifier les règles de validation déjà en place, sauf pour les nouveaux champs.
- Les zones réservées à la banque (CIP, AMPLITUDE, niveau de risque, signatures) restent vides. Sauf des parties ou le gestionnaire sait que c'est a lui de remplir en meme temps

Pour une meilleure gestion, on va mettre le dossier a 2 status soit il est Brouillon soit il est creer. Quand on remplit le formulaire au lieu de previsualiser on aura simplement le bouton Generer qui va tirer le pdf conformement rempli et un bouton Valider pour enregistrer sur la plateforme en tant que créé ou un bouton Corriger au cas ou on se rend compte qu'après avoir tirer il y'a des corrections. Chaque dossier peut etre Consulter/Modifier après avoir été creer egalement mais on peut supprimer un dossier lorsque c'est au brouillon et cela supprime juste dans l'interface sino ça reste traçable dans la BD avec un status desactivé a l'etat Brouillon. 

A tout moment on doit pouvoir generer un pdf concernant un client et pouvoir imprimer et il doit etre modifiable, il se pourrait qu'après avoir generer et valider le client trouve que son nom est mal saisie donc on doit pouvoir modifier et regenerer a nouveau. De ce fait, quand on veut modifier je constate que certains champs deja remplis disparaissent comme les dates et autres ce qui redemande une saisie supplementaire encombrant. Et si on modifie les infos le dossier ne doit pas etre dupliquer mais juste le meme mise a jour.

La reference des dossiers sera : BCB-numero agence-numero CNIB ou Passeport-0000nombre de dossier par exemple si c'est le 10e dossier sur la plateforme ou autre nombre par ordre.

La recherche peut etre fait en fonction du nom ou prenom ou numero cnib.

Dans le remplissage des pdf il y'a confusion de champs, couramment les champs Adresse s'attende au mail et quand dit details precis ce sont les explications plus detaillées de la localisation.

Il faut bien regarder les pdf que j'ai livré, il y'a certains champs maquant dans les formulaires a remplir pourtant doit etre rempli ou cocher: dans la partie KYC il y'a des cases a cocher par l'agent qui assure le remplissage lui meme comme la cage qui demande fiche de creation/ fiche de mise a jour qui doit etre preciser et le reste des champs qui suivent, a constater il y'a plusieurs d'autres parties dont le client doit repondre afin qu'on coche la cage ou remplir mais dans le formulaire il n'est pas la ce qui veut dire informations manquantes. De ce fait, analyse bien la façon dont les pages sont construites pour reconstruire similaire et meme t'assurer que le reste d'une page ne se retrouve pas sur une autre car ça deforme le remplissage et l'agent aura du mal a se retrouver.

Dans coordonnées du client et infos de l'employeur, Pays de Résidence Fiscale et situation professionnelle sont mal ecris dans le pdf generer il manque certains mots alors que tout doit etre conforme pour eviter une confusion ou complication juridique après lors du='une poursuite donc veille a verifier phrase avec les parenthèses si tout est bien fait dans tous le document.

Au niveau de plan de reperage, tu as ajouter au formulaire des champs au dessus qui n'est pas dans l'original que tu dois enlever ça doit etre comme sur l'original.
Au niveau d'identification du client, le champ proximité n'exite pas dans le formulaire generé et les infos s'assurer que les infos remplie parte dans les champs dediée et qu'on ne retrouve pas le numero de secteur dans adresse. Verifie la conformité avec l'original.

Dans la partie KYC au niveau du 2/3 sur l'original il y'a des infos manquantes sur le generer donc non conforme, compare et assure toi que tout est Ok 
