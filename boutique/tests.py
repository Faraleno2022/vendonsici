from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Product, Vendor


@override_settings(CANONICAL_DOMAIN='www.vendonsici.com')
class ProductOpenGraphTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(nom='Vendeur Test')
        self.product = Product.objects.create(
            vendeur=self.vendor,
            nom='Produit Test',
            categorie='mode',
            type_vente='detail',
            prix=100000,
            description='Un produit parfait pour tester le partage Facebook.',
            stock=5,
        )
    def test_product_og_image_uses_facebook_image_endpoint(self):
        expected_url = f"https://www.vendonsici.com{reverse('product_og_image', kwargs={'slug': self.product.slug})}"

        self.assertEqual(self.product.get_absolute_image_url(), expected_url)

        response = self.client.get(
            reverse('product_detail', kwargs={'slug': self.product.slug}),
            HTTP_HOST='www.vendonsici.com',
        )

        self.assertContains(response, f'<meta property="og:image" content="{expected_url}">')
        self.assertContains(response, '<meta property="og:image:type" content="image/jpeg">')
        self.assertContains(response, '<meta property="og:image:width" content="1200">')
        self.assertContains(response, '<meta property="og:image:height" content="1200">')

    def test_product_og_image_endpoint_returns_jpeg(self):
        response = self.client.get(
            reverse('product_og_image', kwargs={'slug': self.product.slug}),
            HTTP_HOST='www.vendonsici.com',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertGreater(len(response.content), 0)
