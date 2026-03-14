from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('boutique', '0002_marketplace_multivendeur'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='type_vente',
            field=models.CharField(choices=[('detail', 'Détail'), ('grossiste', 'Grossiste')], default='detail', max_length=20),
        ),
    ]
