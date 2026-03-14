from django.db import migrations, models
import django.db.models.deletion


def create_default_vendor(apps, schema_editor):
    Vendor = apps.get_model('boutique', 'Vendor')
    Product = apps.get_model('boutique', 'Product')

    default_vendor, _ = Vendor.objects.get_or_create(
        nom='Vendeur principal',
        defaults={
            'slug': 'vendeur-principal',
            'telephone': '',
            'email': None,
            'adresse': '',
            'ville': 'Conakry',
            'description': 'Vendeur principal de la marketplace.',
            'actif': True,
        },
    )

    Product.objects.filter(vendeur__isnull=True).update(vendeur=default_vendor)


def reverse_default_vendor(apps, schema_editor):
    Vendor = apps.get_model('boutique', 'Vendor')
    Vendor.objects.filter(slug='vendeur-principal').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('boutique', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Vendor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200)),
                ('slug', models.SlugField(blank=True, max_length=220, unique=True)),
                ('telephone', models.CharField(blank=True, max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('adresse', models.TextField(blank=True)),
                ('ville', models.CharField(default='Conakry', max_length=120)),
                ('description', models.TextField(blank=True)),
                ('actif', models.BooleanField(default=True)),
                ('date_ajout', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Vendeur',
                'verbose_name_plural': 'Vendeurs',
                'ordering': ['nom'],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='vendeur',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='boutique.vendor'),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='categorie_produit',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='vendeur',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='boutique.vendor'),
        ),
        migrations.AddField(
            model_name='product',
            name='lieu_stock',
            field=models.CharField(default='Conakry', max_length=120),
        ),
        migrations.AddField(
            model_name='product',
            name='vendeur',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='products', to='boutique.vendor'),
        ),
        migrations.AlterField(
            model_name='product',
            name='categorie',
            field=models.CharField(choices=[('agricole', 'Produits agricoles'), ('fruits', 'Fruits et légumes'), ('electronique', 'Électronique'), ('mode', 'Mode et habillement'), ('maison', 'Maison et décoration'), ('beaute', 'Beauté et bien-être'), ('artisanat', 'Artisanat local'), ('services', 'Services et autres')], max_length=20),
        ),
        migrations.RunPython(create_default_vendor, reverse_default_vendor),
        migrations.AlterField(
            model_name='product',
            name='vendeur',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='boutique.vendor'),
        ),
    ]
