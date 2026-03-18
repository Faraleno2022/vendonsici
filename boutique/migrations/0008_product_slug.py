from django.db import migrations, models
from django.utils.text import slugify
import uuid


def generate_product_slugs(apps, schema_editor):
    Product = apps.get_model('boutique', 'Product')
    seen_slugs = set()
    for product in Product.objects.all().order_by('id'):
        base_slug = slugify(product.nom) or f'produit-{uuid.uuid4().hex[:6]}'
        slug = base_slug
        compteur = 1
        while slug in seen_slugs:
            compteur += 1
            slug = f'{base_slug}-{compteur}'
        seen_slugs.add(slug)
        product.slug = slug
        product.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('boutique', '0007_alter_product_actif_alter_product_categorie_and_more'),
    ]

    operations = [
        # Étape 1 : ajouter la colonne sans contrainte unique
        migrations.AddField(
            model_name='product',
            name='slug',
            field=models.SlugField(max_length=255, blank=True, null=True),
        ),
        # Étape 2 : peupler les slugs
        migrations.RunPython(generate_product_slugs, migrations.RunPython.noop),
        # Étape 3 : rendre le champ unique et non null
        migrations.AlterField(
            model_name='product',
            name='slug',
            field=models.SlugField(max_length=255, blank=True, unique=True),
        ),
    ]
