"""
Convertit toutes les images produits non-JPEG (AVIF, WebP, PNG, etc.) en JPEG
pour assurer la compatibilite Facebook / Twitter / Open Graph.

Usage:
    python manage.py convert_images_to_jpeg           # apercu (dry-run)
    python manage.py convert_images_to_jpeg --apply   # applique les changements
"""
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from boutique.models import Product

NON_JPEG_EXT = {'.avif', '.webp', '.png', '.gif', '.bmp', '.tiff', '.tif'}


class Command(BaseCommand):
    help = "Convertit les images produits non-JPEG en JPEG (compatible Facebook OG)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help="Applique vraiment les conversions (sans ce flag, dry-run uniquement).",
        )
        parser.add_argument(
            '--max-size',
            type=int,
            default=1200,
            help="Taille max (largeur ou hauteur) en pixels. Defaut: 1200.",
        )
        parser.add_argument(
            '--quality',
            type=int,
            default=85,
            help="Qualite JPEG 1-100. Defaut: 85.",
        )

    def handle(self, *args, **options):
        try:
            import pillow_avif  # noqa: F401
            self.stdout.write(self.style.SUCCESS("pillow-avif-plugin charge (AVIF supporte)"))
        except ImportError:
            self.stdout.write(self.style.WARNING(
                "pillow-avif-plugin non installe -- les fichiers AVIF seront ignores. "
                "Installez avec: pip install pillow-avif-plugin"
            ))

        from PIL import Image as PILImage

        apply = options['apply']
        max_size = options['max_size']
        quality = options['quality']

        products = Product.objects.exclude(image='').exclude(image__isnull=True)
        total = products.count()
        self.stdout.write(f"Produits avec image: {total}")

        converted = 0
        skipped = 0
        failed = 0

        for product in products:
            if not product.image:
                continue
            name = product.image.name
            ext = Path(name).suffix.lower()

            if ext == '.jpg' or ext == '.jpeg':
                skipped += 1
                continue

            if ext not in NON_JPEG_EXT:
                self.stdout.write(self.style.WARNING(f"  ? Format inconnu, ignore: {name}"))
                skipped += 1
                continue

            try:
                product.image.open('rb')
                img = PILImage.open(product.image)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                w, h = img.size
                if w > max_size or h > max_size:
                    img.thumbnail((max_size, max_size), PILImage.LANCZOS)
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                buffer.seek(0)
                product.image.close()

                stem = Path(name).stem
                new_name = f"produits/{stem}.jpg"

                action = "CONVERTI" if apply else "[DRY-RUN] a convertir"
                self.stdout.write(f"  {action}: {name} -> {new_name}")

                if apply:
                    old_path = product.image.path if product.image else None
                    product.image.save(new_name, ContentFile(buffer.getvalue()), save=False)
                    Product.objects.filter(pk=product.pk).update(image=product.image.name)
                    if old_path and Path(old_path).exists() and Path(old_path).suffix.lower() != '.jpg':
                        try:
                            Path(old_path).unlink()
                        except Exception:
                            pass

                converted += 1
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  ECHEC: {name} ({e})"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Resultat: {converted} convertis, {skipped} ignores (deja JPEG), {failed} echecs."
        ))
        if not apply and converted > 0:
            self.stdout.write(self.style.WARNING(
                "Ceci etait un DRY-RUN. Relancez avec --apply pour appliquer."
            ))
