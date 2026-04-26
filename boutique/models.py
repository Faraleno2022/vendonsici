from django.db import models
from django.conf import settings
from django.utils.text import slugify
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import uuid
import sys


class Vendor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendor_profile',
        verbose_name='Compte utilisateur',
    )
    nom = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, null=True)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=120, default='Conakry')
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']
        verbose_name = 'Vendeur'
        verbose_name_plural = 'Vendeurs'

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nom) or f'vendeur-{uuid.uuid4().hex[:6]}'
            slug = base_slug
            compteur = 1
            while Vendor.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                compteur += 1
                slug = f'{base_slug}-{compteur}'
            self.slug = slug
        super().save(*args, **kwargs)


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('agricole', 'Produits agricoles'),
        ('fruits', 'Fruits et légumes'),
        ('electronique', 'Électronique'),
        ('mode', 'Mode et habillement'),
        ('maison', 'Maison et décoration'),
        ('beaute', 'Beauté et bien-être'),
        ('artisanat', 'Artisanat local'),
        ('restaurant', 'Restaurant'),
        ('services', 'Services et autres'),
    ]
    BADGE_CHOICES = [
        ('', 'Aucun'),
        ('Nouveau', 'Nouveau'),
        ('Bestseller', 'Bestseller'),
        ('Exclusif', 'Exclusif'),
        ('Premium', 'Premium'),
    ]
    TYPE_VENTE_CHOICES = [
        ('detail', 'Détail'),
        ('grossiste', 'Grossiste'),
    ]

    vendeur = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='products')
    nom = models.CharField(max_length=200)
    categorie = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    type_vente = models.CharField(max_length=20, choices=TYPE_VENTE_CHOICES, default='detail', db_index=True)
    prix = models.DecimalField(max_digits=12, decimal_places=0)
    prix_achat = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Prix d'achat")
    description = models.TextField()
    image = models.ImageField(upload_to='produits/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True, help_text="URL externe de l'image (si pas d'upload)")
    badge = models.CharField(max_length=20, choices=BADGE_CHOICES, blank=True, default='')
    note = models.IntegerField(default=5, choices=[(i, f'{i} étoile(s)') for i in range(1, 6)])
    stock = models.IntegerField(default=10)
    seuil_alerte_stock = models.IntegerField(default=3, verbose_name="Seuil d'alerte stock")
    lieu_stock = models.CharField(max_length=120, default='Conakry')
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-date_ajout']
        verbose_name = 'Produit'
        verbose_name_plural = 'Produits'
        indexes = [
            models.Index(fields=['actif', 'categorie']),
            models.Index(fields=['actif', '-date_ajout']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nom) or f'produit-{uuid.uuid4().hex[:6]}'
            slug = base_slug
            compteur = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                compteur += 1
                slug = f'{base_slug}-{compteur}'
            self.slug = slug
        if self.stock < 0:
            self.stock = 0
        if self.note < 1:
            self.note = 1
        if self.note > 5:
            self.note = 5
        if not self.lieu_stock:
            self.lieu_stock = 'Conakry'
        if self.image and hasattr(self.image, 'file'):
            self._compress_image()
        super().save(*args, **kwargs)

    def _compress_image(self, max_size=1200, quality=85):
        """Redimensionne et compresse l'image uploadée en JPEG (compatible Facebook/Twitter)."""
        try:
            import pillow_avif  # noqa: F401  (active le décodage AVIF dans Pillow)
        except ImportError:
            pass
        from PIL import Image as PILImage
        img = PILImage.open(self.image)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        w, h = img.size
        if w > max_size or h > max_size:
            img.thumbnail((max_size, max_size), PILImage.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        buffer.seek(0)
        original = self.image.name.rsplit('/', 1)[-1]
        stem = original.rsplit('.', 1)[0] if '.' in original else original
        name = f"{stem}.jpg"
        self.image = InMemoryUploadedFile(
            buffer, 'ImageField', name, 'image/jpeg',
            sys.getsizeof(buffer), None
        )

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('product_detail', kwargs={'slug': self.slug})

    def __str__(self):
        return f"{self.nom} — {self.vendeur.nom}"

    def get_image_url(self):
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        if self.image_url:
            return self.image_url
        return '/static/img/placeholder.jpg'

    def get_absolute_image_url(self):
        """URL absolue de l'image, pour les balises og:image / twitter:image."""
        from django.conf import settings
        base = f"https://{getattr(settings, 'CANONICAL_DOMAIN', 'www.vendonsici.com')}"
        if self.image and hasattr(self.image, 'url'):
            img_url = self.image.url
            if img_url.startswith('/'):
                return f"{base}{img_url}"
            return img_url
        if self.image_url:
            url = self.image_url.strip()
            # Convertir http en https pour Facebook
            if url.startswith('http://'):
                url = 'https://' + url[7:]
            # Ajouter le domaine si chemin relatif
            if url.startswith('/'):
                return f"{base}{url}"
            return url
        return f"{base}/static/images/logo.png"

    @property
    def prix_formate(self):
        return f"{self.prix:,.0f} GNF".replace(",", " ")

    @property
    def prix_achat_formate(self):
        return f"{self.prix_achat:,.0f} GNF".replace(",", " ")

    @property
    def benefice_unitaire(self):
        return self.prix - self.prix_achat

    @property
    def benefice_unitaire_formate(self):
        return f"{self.benefice_unitaire:,.0f} GNF".replace(",", " ")

    @property
    def stock_bas(self):
        return self.stock <= self.seuil_alerte_stock


class Order(models.Model):
    STATUS_CHOICES = [
        ('nouvelle', 'Nouvelle'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
    ]
    PAYMENT_CHOICES = [
        ('orange_money', 'Orange Money'),
        ('mtn_momo', 'MTN MoMo'),
        ('livraison', 'Paiement à la livraison'),
        ('virement', 'Virement bancaire'),
    ]

    numero = models.CharField(max_length=20, unique=True, editable=False)
    vendeur = models.ForeignKey('Vendor', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    prenom_nom = models.CharField(max_length=200, verbose_name="Prénom et Nom")
    telephone = models.CharField(max_length=20, verbose_name="Téléphone / WhatsApp")
    email = models.EmailField(blank=True, null=True)
    adresse = models.TextField(verbose_name="Adresse de livraison")
    mode_paiement = models.CharField(max_length=20, choices=PAYMENT_CHOICES, verbose_name="Mode de paiement")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes / Instructions")
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default='nouvelle')
    total = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    date_commande = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_commande']
        verbose_name = 'Commande'
        verbose_name_plural = 'Commandes'

    def __str__(self):
        if self.vendeur:
            return f"Commande {self.numero} - {self.prenom_nom} - {self.vendeur.nom}"
        return f"Commande {self.numero} - {self.prenom_nom}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = f"GM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def total_formate(self):
        return f"{self.total:,.0f} GNF".replace(",", " ")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    vendeur = models.ForeignKey('Vendor', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    nom_produit = models.CharField(max_length=200)
    categorie_produit = models.CharField(max_length=50, blank=True)
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=0)
    quantite = models.IntegerField(default=1)

    class Meta:
        verbose_name = "Article commandé"
        verbose_name_plural = "Articles commandés"

    def save(self, *args, **kwargs):
        if self.quantite < 1:
            self.quantite = 1
        super().save(*args, **kwargs)

    def __str__(self):
        if self.vendeur:
            return f"{self.quantite}x {self.nom_produit} ({self.vendeur.nom})"
        return f"{self.quantite}x {self.nom_produit}"

    @property
    def sous_total(self):
        return self.prix_unitaire * self.quantite

    @property
    def sous_total_formate(self):
        return f"{self.sous_total:,.0f} GNF".replace(",", " ")


class OfflineSale(models.Model):
    """Vente effectuée hors site (en boutique physique, WhatsApp, etc.)"""
    vendeur = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='offline_sales')
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='offline_sales')
    nom_produit = models.CharField(max_length=200)
    quantite = models.IntegerField(default=1)
    prix_vente = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Prix de vente unitaire")
    prix_achat = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Prix d'achat unitaire")
    client_nom = models.CharField(max_length=200, blank=True, verbose_name="Nom du client")
    client_telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone du client")
    notes = models.TextField(blank=True)
    date_vente = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_vente']
        verbose_name = 'Vente hors site'
        verbose_name_plural = 'Ventes hors site'

    def save(self, *args, **kwargs):
        if self.quantite < 1:
            self.quantite = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantite}x {self.nom_produit} — {self.vendeur.nom}"

    @property
    def total(self):
        return self.prix_vente * self.quantite

    @property
    def total_formate(self):
        return f"{self.total:,.0f} GNF".replace(",", " ")

    @property
    def benefice(self):
        return (self.prix_vente - self.prix_achat) * self.quantite

    @property
    def benefice_formate(self):
        return f"{self.benefice:,.0f} GNF".replace(",", " ")
