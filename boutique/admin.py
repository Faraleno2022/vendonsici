from django.contrib import admin
from .models import Product, Order, OrderItem, Vendor


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('vendeur', 'nom_produit', 'categorie_produit', 'prix_unitaire', 'quantite')


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ville', 'telephone', 'email', 'actif', 'date_ajout')
    list_filter = ('actif', 'ville')
    search_fields = ('nom', 'telephone', 'email', 'ville')
    prepopulated_fields = {}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('nom', 'vendeur', 'categorie', 'type_vente', 'prix', 'stock', 'badge', 'note', 'actif', 'date_ajout')
    list_filter = ('vendeur', 'categorie', 'type_vente', 'badge', 'actif', 'note')
    search_fields = ('nom', 'description', 'vendeur__nom', 'lieu_stock')
    list_editable = ('type_vente', 'prix', 'stock', 'actif', 'badge')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('numero', 'vendeur', 'prenom_nom', 'telephone', 'total', 'statut', 'date_commande')
    list_filter = ('vendeur', 'statut', 'mode_paiement', 'date_commande')
    search_fields = ('numero', 'prenom_nom', 'telephone', 'email', 'vendeur__nom')
    list_editable = ('statut',)
    inlines = [OrderItemInline]
    readonly_fields = ('numero', 'date_commande')
