import os
import shutil

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from boutique.models import Product, Vendor


class Command(BaseCommand):
    help = 'Ajoute des produits de démonstration au catalogue avec images locales'

    def handle(self, *args, **options):
        products_data = [
            {
                'nom': 'Robe Élégante Soirée',
                'categorie': 'mode',
                'prix': 850000,
                'description': "Robe longue en tissu satiné, parfaite pour les soirées et événements. Coupe ajustée avec détails brodés à la main. Disponible en plusieurs tailles.",
                'image_file': 'robe_elegante.jpg',
                'badge': 'Nouveau',
                'note': 5,
                'stock': 15,
            },
            {
                'nom': 'Costume Homme Premium',
                'categorie': 'mode',
                'prix': 1200000,
                'description': "Costume trois pièces en laine fine. Coupe moderne et élégante, idéal pour les occasions professionnelles et cérémonies. Finitions soignées.",
                'image_file': 'costume_homme.jpg',
                'badge': 'Premium',
                'note': 5,
                'stock': 8,
            },
            {
                'nom': 'Sac à Main Cuir',
                'categorie': 'beaute',
                'prix': 450000,
                'description': "Sac à main en cuir véritable avec finitions dorées. Design intemporel et pratique avec multiples compartiments. Bandoulière ajustable incluse.",
                'image_file': 'sac_main_cuir.jpg',
                'badge': 'Bestseller',
                'note': 5,
                'stock': 20,
            },
            {
                'nom': 'Montre Classique Or',
                'categorie': 'beaute',
                'prix': 680000,
                'description': "Montre classique avec bracelet en cuir et cadran doré. Mouvement à quartz de haute précision. Résistante à l'eau jusqu'à 30 mètres.",
                'image_file': 'montre_classique.jpg',
                'badge': 'Exclusif',
                'note': 4,
                'stock': 12,
            },
            {
                'nom': 'Ensemble Wax Africain',
                'categorie': 'mode',
                'prix': 350000,
                'description': "Ensemble deux pièces en tissu wax authentique. Motifs traditionnels revisités avec une touche moderne. Tissu 100% coton de qualité supérieure.",
                'image_file': 'ensemble_wax.jpg',
                'badge': 'Nouveau',
                'note': 5,
                'stock': 25,
            },
            {
                'nom': 'Collier Perles Dorées',
                'categorie': 'beaute',
                'prix': 180000,
                'description': "Collier de perles dorées artisanal. Design élégant et raffiné, parfait pour sublimer toute tenue. Fermoir en plaqué or.",
                'image_file': 'collier_perles.jpg',
                'badge': '',
                'note': 4,
                'stock': 30,
            },
            {
                'nom': 'Coussin Décoratif Luxe',
                'categorie': 'maison',
                'prix': 120000,
                'description': "Coussin décoratif en velours avec broderies dorées. Dimensions 45x45cm. Housse lavable avec fermeture invisible. Garnissage hypoallergénique.",
                'image_file': 'coussin_luxe.jpg',
                'badge': '',
                'note': 4,
                'stock': 40,
            },
            {
                'nom': 'Vase Artisanal Doré',
                'categorie': 'maison',
                'prix': 250000,
                'description': "Vase artisanal en céramique avec finition dorée. Pièce unique fabriquée à la main. Hauteur 35cm. Parfait comme centre de table ou décoration.",
                'image_file': 'vase_artisanal.jpg',
                'badge': 'Exclusif',
                'note': 5,
                'stock': 10,
            },
            {
                'nom': 'Chemise Lin Homme',
                'categorie': 'mode',
                'prix': 280000,
                'description': "Chemise en lin naturel, coupe décontractée et élégante. Tissu respirant idéal pour le climat tropical. Col mao avec boutons en nacre.",
                'image_file': 'chemise_lin.jpg',
                'badge': '',
                'note': 4,
                'stock': 18,
            },
            {
                'nom': 'Bougie Parfumée Premium',
                'categorie': 'maison',
                'prix': 95000,
                'description': "Bougie parfumée artisanale à la cire de soja. Parfum boisé et vanillé. Durée de combustion environ 50 heures. Contenant réutilisable en verre soufflé.",
                'image_file': 'bougie_parfumee.jpg',
                'badge': 'Bestseller',
                'note': 5,
                'stock': 35,
            },
            {
                'nom': 'Lunettes de Soleil Fashion',
                'categorie': 'beaute',
                'prix': 220000,
                'description': "Lunettes de soleil unisexes avec monture dorée et verres polarisés. Protection UV400. Design tendance et intemporel. Étui rigide inclus.",
                'image_file': 'lunettes_soleil.jpg',
                'badge': '',
                'note': 4,
                'stock': 22,
            },
            {
                'nom': 'Plateau Service Doré',
                'categorie': 'maison',
                'prix': 175000,
                'description': "Plateau de service en métal avec finition dorée martelée. Dimensions 40x25cm. Parfait pour servir le thé ou comme pièce décorative.",
                'image_file': 'plateau_dore.jpg',
                'badge': 'Premium',
                'note': 5,
                'stock': 15,
            },
        ]

        images_dir = os.path.join(settings.MEDIA_ROOT, 'produits')
        vendor, _ = Vendor.objects.get_or_create(
            slug='vendeur-principal',
            defaults={
                'nom': 'Vendeur principal',
                'telephone': '',
                'email': None,
                'adresse': '',
                'ville': 'Conakry',
                'description': 'Vendeur principal de la boutique.',
                'actif': True,
            },
        )
        created_count = 0
        updated_count = 0

        for data in products_data:
            image_filename = data.pop('image_file')
            image_path = os.path.join(images_dir, image_filename)
            data['vendeur'] = vendor

            product, created = Product.objects.get_or_create(
                nom=data['nom'],
                defaults=data
            )

            # Assign local image if file exists and product has no local image
            if os.path.exists(image_path) and not product.image:
                dest = f'produits/{image_filename}'
                product.image = dest
                product.image_url = ''
                product.save(update_fields=['image', 'image_url'])
                if not created:
                    updated_count += 1
                self.stdout.write(self.style.SUCCESS(f'  📷 Image locale assignée : {image_filename}'))

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Produit créé : {product.nom}'))
            else:
                self.stdout.write(self.style.WARNING(f'  → Produit existant : {product.nom}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n{created_count} produit(s) créé(s), {updated_count} mis à jour avec images locales.'
        ))
