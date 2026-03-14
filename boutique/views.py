from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.db import transaction
from django.views.decorators.http import require_POST
from .models import Product, Order, OrderItem, Vendor, OfflineSale
import json
from django.utils import timezone
from datetime import timedelta


MARKETPLACE_CATEGORIES = [('tout', 'Toutes les catégories')] + Product.CATEGORY_CHOICES


def _get_marketplace_categories():
    return MARKETPLACE_CATEGORIES


def _get_active_vendors():
    return Vendor.objects.filter(actif=True).order_by('nom')


def _get_current_vendor(request):
    """Return the Vendor linked to the logged-in user, or None for superusers."""
    if request.user.is_superuser:
        return None
    return getattr(request.user, 'vendor_profile', None)


def _safe_positive_int(value, default=1):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return default
    return parsed_value if parsed_value > 0 else default


def _safe_non_negative_int(value, default=0):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return default
    return parsed_value if parsed_value >= 0 else default


def _build_order_vendor_context(order):
    vendors_map = {}
    for item in order.items.select_related('vendeur', 'product').all():
        vendor = item.vendeur
        vendor_key = vendor.pk if vendor else f'no-vendor-{item.pk}'
        if vendor_key not in vendors_map:
            vendors_map[vendor_key] = {
                'vendor': vendor,
                'items': [],
                'total': 0,
            }
        vendors_map[vendor_key]['items'].append(item)
        vendors_map[vendor_key]['total'] += item.sous_total

    vendor_orders = list(vendors_map.values())
    for group in vendor_orders:
        group['total_formate'] = f"{group['total']:,.0f} GNF".replace(',', ' ')
    return vendor_orders


def home(request):
    products = Product.objects.filter(actif=True).select_related('vendeur')
    categorie = request.GET.get('categorie', 'tout')
    search = request.GET.get('q', '')
    vendeur_slug = request.GET.get('vendeur', '')
    type_vente = request.GET.get('type_vente', 'tout')

    if search:
        products = products.filter(
            Q(nom__icontains=search) |
            Q(categorie__icontains=search) |
            Q(description__icontains=search) |
            Q(vendeur__nom__icontains=search) |
            Q(lieu_stock__icontains=search)
        )

    if categorie and categorie != 'tout':
        products = products.filter(categorie=categorie)

    if vendeur_slug:
        products = products.filter(vendeur__slug=vendeur_slug, vendeur__actif=True)

    if type_vente and type_vente != 'tout':
        products = products.filter(type_vente=type_vente)

    context = {
        'products': products,
        'categorie_active': categorie,
        'search_query': search,
        'vendeur_actif': vendeur_slug,
        'type_vente_actif': type_vente,
        'vendors': _get_active_vendors(),
        'total_products': Product.objects.filter(actif=True).count(),
        'categories': _get_marketplace_categories(),
        'type_vente_filters': [('tout', 'Tous les types')] + list(Product.TYPE_VENTE_CHOICES),
    }
    return render(request, 'boutique/home.html', context)


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('vendeur'), pk=pk, actif=True)

    if request.GET.get('fbclid'):
        return redirect('commande_directe', pk=product.pk)

    related = Product.objects.filter(categorie=product.categorie, actif=True).select_related('vendeur').exclude(pk=pk)[:4]
    context = {
        'product': product,
        'related_products': related,
    }
    return render(request, 'boutique/product_detail.html', context)


def about(request):
    return render(request, 'boutique/about.html')


def cart_view(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0
    vendors_in_cart = {}

    for product_id, qty in cart.items():
        try:
            product = Product.objects.select_related('vendeur').get(pk=int(product_id), actif=True)
            sous_total = product.prix * qty
            total += sous_total
            vendor = product.vendeur
            vendor_key = vendor.slug if vendor else f'no-vendor-{product.pk}'
            if vendor_key not in vendors_in_cart:
                vendors_in_cart[vendor_key] = {
                    'vendor': vendor,
                    'total': 0,
                    'items_count': 0,
                }
            vendors_in_cart[vendor_key]['total'] += sous_total
            vendors_in_cart[vendor_key]['items_count'] += qty
            cart_items.append({
                'product': product,
                'quantity': qty,
                'sous_total': sous_total,
                'sous_total_formate': f"{sous_total:,.0f} GNF".replace(",", " "),
            })
        except (Product.DoesNotExist, TypeError, ValueError):
            continue

    context = {
        'cart_items': cart_items,
        'total': total,
        'total_formate': f"{total:,.0f} GNF".replace(",", " "),
        'vendor_groups': vendors_in_cart.values(),
        'payment_methods': Order.PAYMENT_CHOICES,
    }
    return render(request, 'boutique/cart.html', context)


def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk, actif=True)
    cart = request.session.get('cart', {})
    product_id = str(pk)
    qty = _safe_positive_int(request.POST.get('quantity', 1)) if request.method == 'POST' else 1

    if product_id in cart:
        cart[product_id] += qty
    else:
        cart[product_id] = qty

    request.session['cart'] = cart
    messages.success(request, f'"{product.nom}" ajouté au panier !')

    next_url = request.POST.get('next', request.META.get('HTTP_REFERER', '/'))
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': sum(cart.values()),
            'message': f'"{product.nom}" ajouté au panier !'
        })
    return redirect(next_url)


def update_cart(request, pk):
    cart = request.session.get('cart', {})
    product_id = str(pk)
    action = request.POST.get('action', '')

    if action == 'increase':
        cart[product_id] = cart.get(product_id, 0) + 1
    elif action == 'decrease':
        if cart.get(product_id, 0) > 1:
            cart[product_id] -= 1
        else:
            cart.pop(product_id, None)
    elif action == 'remove':
        cart.pop(product_id, None)

    request.session['cart'] = cart
    return redirect('cart')


def checkout(request):
    if request.method != 'POST':
        return redirect('cart')

    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, 'Votre panier est vide.')
        return redirect('cart')

    prenom_nom = request.POST.get('prenom_nom', '').strip()
    telephone = request.POST.get('telephone', '').strip()
    email = request.POST.get('email', '').strip()
    adresse = request.POST.get('adresse', '').strip()
    mode_paiement = request.POST.get('mode_paiement', '')
    notes = request.POST.get('notes', '').strip()

    if not all([prenom_nom, telephone, adresse, mode_paiement]):
        messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
        return redirect('cart')

    with transaction.atomic():
        order = Order.objects.create(
            prenom_nom=prenom_nom,
            telephone=telephone,
            email=email or None,
            adresse=adresse,
            mode_paiement=mode_paiement,
            notes=notes or None,
        )

        total = 0
        order_vendors = set()
        for product_id, qty in cart.items():
            try:
                product = Product.objects.select_related('vendeur').get(pk=int(product_id), actif=True)
                safe_qty = _safe_positive_int(qty)
                sous_total = product.prix * safe_qty
                total += sous_total
                if product.vendeur_id:
                    order_vendors.add(product.vendeur_id)
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    vendeur=product.vendeur,
                    nom_produit=product.nom,
                    categorie_produit=product.get_categorie_display(),
                    prix_unitaire=product.prix,
                    quantite=safe_qty,
                )
            except (Product.DoesNotExist, TypeError, ValueError):
                continue

        if total == 0:
            order.delete()
            messages.error(request, 'Aucun produit valide dans le panier.')
            return redirect('cart')

        order.total = total
        if len(order_vendors) == 1:
            order.vendeur_id = next(iter(order_vendors))
        order.save()

    request.session['cart'] = {}
    request.session['last_order_id'] = order.id

    return redirect(f"{reverse('order_confirmation', kwargs={'numero': order.numero})}?redirect_home=1")


def order_confirmation(request, numero):
    order = get_object_or_404(Order, numero=numero)
    context = {
        'order': order,
        'vendor_orders': _build_order_vendor_context(order),
        'redirect_home': request.GET.get('redirect_home') == '1',
    }
    return render(request, 'boutique/order_confirmation.html', context)


def cart_count(request):
    cart = request.session.get('cart', {})
    return JsonResponse({'count': sum(cart.values())})


# ============ COMMANDE EN LIGNE (lien partageable) ============

def commander_en_ligne(request):
    products = Product.objects.filter(actif=True).select_related('vendeur')
    categorie = request.GET.get('categorie', 'tout')
    vendeur_slug = request.GET.get('vendeur', '')

    if categorie and categorie != 'tout':
        products = products.filter(categorie=categorie)

    if vendeur_slug:
        products = products.filter(vendeur__slug=vendeur_slug, vendeur__actif=True)

    context = {
        'products': products,
        'categorie_active': categorie,
        'vendeur_actif': vendeur_slug,
        'vendors': _get_active_vendors(),
        'categories': _get_marketplace_categories(),
        'payment_methods': Order.PAYMENT_CHOICES,
    }
    return render(request, 'boutique/commander_en_ligne.html', context)


def commander_en_ligne_submit(request):
    if request.method != 'POST':
        return redirect('commander_en_ligne')

    prenom_nom = request.POST.get('prenom_nom', '').strip()
    telephone = request.POST.get('telephone', '').strip()
    email = request.POST.get('email', '').strip()
    adresse = request.POST.get('adresse', '').strip()
    mode_paiement = request.POST.get('mode_paiement', '')
    notes = request.POST.get('notes', '').strip()
    produits_json = request.POST.get('produits', '{}')

    if not all([prenom_nom, telephone, adresse, mode_paiement]):
        messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
        return redirect('commander_en_ligne')

    try:
        produits_selectionnes = json.loads(produits_json)
    except json.JSONDecodeError:
        produits_selectionnes = {}

    if not produits_selectionnes:
        messages.error(request, 'Veuillez sélectionner au moins un produit.')
        return redirect('commander_en_ligne')

    order = Order.objects.create(
        prenom_nom=prenom_nom,
        telephone=telephone,
        email=email or None,
        adresse=adresse,
        mode_paiement=mode_paiement,
        notes=notes or None,
    )

    total = 0
    order_vendors = set()
    for product_id, qty in produits_selectionnes.items():
        qty = _safe_positive_int(qty)
        if qty <= 0:
            continue
        try:
            product = Product.objects.select_related('vendeur').get(pk=int(product_id), actif=True)
            sous_total = product.prix * qty
            total += sous_total
            if product.vendeur_id:
                order_vendors.add(product.vendeur_id)
            OrderItem.objects.create(
                order=order,
                product=product,
                vendeur=product.vendeur,
                nom_produit=product.nom,
                categorie_produit=product.get_categorie_display(),
                prix_unitaire=product.prix,
                quantite=qty,
            )
        except (Product.DoesNotExist, TypeError, ValueError):
            continue

    if total == 0:
        order.delete()
        messages.error(request, 'Aucun produit valide sélectionné.')
        return redirect('commander_en_ligne')

    order.total = total
    if len(order_vendors) == 1:
        order.vendeur_id = next(iter(order_vendors))
    order.save()

    return redirect(f"{reverse('order_confirmation', kwargs={'numero': order.numero})}?redirect_home=1")


def commande_video(request):
    context = {
        'payment_methods': Order.PAYMENT_CHOICES,
    }
    return render(request, 'boutique/commande_video.html', context)


def commande_video_submit(request):
    if request.method != 'POST':
        return redirect('commande_video')

    prenom_nom = request.POST.get('prenom_nom', '').strip()
    telephone = request.POST.get('telephone', '').strip()
    email = request.POST.get('email', '').strip()
    adresse = request.POST.get('adresse', '').strip()
    mode_paiement = request.POST.get('mode_paiement', '')
    notes = request.POST.get('notes', '').strip()
    produit_video = request.POST.get('produit_video', '').strip()

    if not all([prenom_nom, telephone, adresse, mode_paiement, produit_video]):
        messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
        return redirect('commande_video')

    notes_completes = f"Produit vu dans la vidéo : {produit_video}"
    if notes:
        notes_completes = f"{notes_completes}\n\nNotes client : {notes}"

    order = Order.objects.create(
        prenom_nom=prenom_nom,
        telephone=telephone,
        email=email or None,
        adresse=adresse,
        mode_paiement=mode_paiement,
        notes=notes_completes,
        total=0,
    )

    return redirect(f"{reverse('order_confirmation', kwargs={'numero': order.numero})}?redirect_home=1")


# ============ COMMANDE DIRECTE PAR PRODUIT (lien partageable) ============

def commande_directe(request, pk):
    product = get_object_or_404(Product.objects.select_related('vendeur'), pk=pk, actif=True)
    context = {
        'product': product,
        'payment_methods': Order.PAYMENT_CHOICES,
    }
    return render(request, 'boutique/commande_directe.html', context)


def commande_directe_submit(request, pk):
    if request.method != 'POST':
        return redirect('commande_directe', pk=pk)

    product = get_object_or_404(Product.objects.select_related('vendeur'), pk=pk, actif=True)

    prenom_nom = request.POST.get('prenom_nom', '').strip()
    telephone = request.POST.get('telephone', '').strip()
    email = request.POST.get('email', '').strip()
    adresse = request.POST.get('adresse', '').strip()
    mode_paiement = request.POST.get('mode_paiement', '')
    notes = request.POST.get('notes', '').strip()
    quantite = _safe_positive_int(request.POST.get('quantite', 1))

    if not all([prenom_nom, telephone, adresse, mode_paiement]):
        messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
        return redirect('commande_directe', pk=pk)

    sous_total = product.prix * quantite

    order = Order.objects.create(
        vendeur=product.vendeur,
        prenom_nom=prenom_nom,
        telephone=telephone,
        email=email or None,
        adresse=adresse,
        mode_paiement=mode_paiement,
        notes=notes or None,
        total=sous_total,
    )

    OrderItem.objects.create(
        order=order,
        product=product,
        vendeur=product.vendeur,
        nom_produit=product.nom,
        categorie_produit=product.get_categorie_display(),
        prix_unitaire=product.prix,
        quantite=quantite,
    )

    return redirect(f"{reverse('order_confirmation', kwargs={'numero': order.numero})}?redirect_home=1")


# ============ ADMIN VIEWS ============

def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Identifiants incorrects ou accès non autorisé.')

    return render(request, 'boutique/admin/login.html')


def vendor_register(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        nom_boutique = request.POST.get('nom_boutique', '').strip()
        telephone = request.POST.get('telephone', '').strip()
        email = request.POST.get('email', '').strip()
        adresse = request.POST.get('adresse', '').strip()
        ville = request.POST.get('ville', 'Conakry').strip() or 'Conakry'
        description = request.POST.get('description', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        errors = []
        if not all([nom_boutique, username, password, password_confirm]):
            errors.append('Veuillez remplir tous les champs obligatoires.')
        if password != password_confirm:
            errors.append('Les mots de passe ne correspondent pas.')
        if len(password) < 6:
            errors.append('Le mot de passe doit contenir au moins 6 caractères.')
        if User.objects.filter(username=username).exists():
            errors.append("Ce nom d'utilisateur est déjà pris.")
        if email and User.objects.filter(email=email).exists():
            errors.append('Cette adresse email est déjà utilisée.')

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'boutique/admin/register.html', {
                'form_data': request.POST,
            })

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email or '',
                is_staff=True,
            )
            Vendor.objects.create(
                user=user,
                nom=nom_boutique,
                telephone=telephone,
                email=email or None,
                adresse=adresse,
                ville=ville,
                description=description,
                actif=True,
            )

        login(request, user)
        messages.success(request, f'Bienvenue {nom_boutique} ! Votre compte vendeur a été créé avec succès.')
        return redirect('admin_dashboard')

    return render(request, 'boutique/admin/register.html')


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)

    if vendor:
        orders_qs = Order.objects.filter(
            Q(vendeur=vendor) | Q(items__vendeur=vendor)
        ).distinct()
        products_qs = Product.objects.filter(vendeur=vendor, actif=True)
    else:
        orders_qs = Order.objects.all()
        products_qs = Product.objects.filter(actif=True)

    total_orders = orders_qs.count()
    pending_orders = orders_qs.filter(statut='nouvelle').count()
    in_progress_orders = orders_qs.filter(statut='en_cours').count()
    completed_orders = orders_qs.filter(statut='terminee').count()
    total_revenue = orders_qs.filter(statut='terminee').aggregate(Sum('total'))['total__sum'] or 0
    total_products = products_qs.count()
    total_vendors = Vendor.objects.filter(actif=True).count()
    recent_orders = orders_qs.select_related('vendeur').all()[:10]

    context = {
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'in_progress_orders': in_progress_orders,
        'completed_orders': completed_orders,
        'total_revenue': total_revenue,
        'total_revenue_formate': f"{total_revenue:,.0f} GNF".replace(",", " "),
        'total_products': total_products,
        'total_vendors': total_vendors,
        'recent_orders': recent_orders,
    }
    return render(request, 'boutique/admin/dashboard.html', context)


@login_required
def admin_orders(request):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    statut_filter = request.GET.get('statut', '')
    vendeur_filter = request.GET.get('vendeur', '')

    if vendor:
        orders = Order.objects.filter(
            Q(vendeur=vendor) | Q(items__vendeur=vendor)
        ).select_related('vendeur').prefetch_related('items', 'items__vendeur').distinct()
    else:
        orders = Order.objects.select_related('vendeur').prefetch_related('items', 'items__vendeur').distinct()

    if statut_filter:
        orders = orders.filter(statut=statut_filter)
    else:
        orders = orders.exclude(statut='terminee')

    if vendeur_filter and not vendor:
        orders = orders.filter(Q(vendeur__slug=vendeur_filter) | Q(items__vendeur__slug=vendeur_filter)).distinct()

    context = {
        'orders': orders,
        'statut_filter': statut_filter,
        'vendeur_filter': vendeur_filter,
        'vendors': _get_active_vendors(),
        'statuts': Order.STATUS_CHOICES,
        'is_vendor': vendor is not None,
    }
    return render(request, 'boutique/admin/orders.html', context)


@login_required
def admin_order_detail(request, pk):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    order = get_object_or_404(Order.objects.select_related('vendeur').prefetch_related('items', 'items__vendeur', 'items__product'), pk=pk)

    if vendor and order.vendeur != vendor and not order.items.filter(vendeur=vendor).exists():
        messages.error(request, 'Vous n\'avez pas accès à cette commande.')
        return redirect('admin_orders')

    context = {'order': order}
    return render(request, 'boutique/admin/order_detail.html', context)


@login_required
@require_POST
def admin_update_status(request, pk):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    order = get_object_or_404(Order, pk=pk)

    if vendor and order.vendeur != vendor and not order.items.filter(vendeur=vendor).exists():
        messages.error(request, 'Vous n\'avez pas accès à cette commande.')
        return redirect('admin_orders')

    new_status = request.POST.get('statut', '')
    if new_status in dict(Order.STATUS_CHOICES):
        order.statut = new_status
        order.save()
        messages.success(request, f'Statut de la commande {order.numero} mis à jour.')
    return redirect('admin_order_detail', pk=pk)


@login_required
@require_POST
def admin_mark_order_completed(request, pk):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    order = get_object_or_404(Order, pk=pk)

    if vendor and order.vendeur != vendor and not order.items.filter(vendeur=vendor).exists():
        messages.error(request, 'Vous n\'avez pas accès à cette commande.')
        return redirect('admin_orders')

    order.statut = 'terminee'
    order.save(update_fields=['statut'])
    messages.success(request, f'Commande {order.numero} marquée comme traitée.')
    return redirect('admin_orders')


# ============ PRODUCT MANAGEMENT ============

@login_required
def admin_products(request):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    search = request.GET.get('q', '')
    categorie = request.GET.get('categorie', '')
    vendeur_filter = request.GET.get('vendeur', '')

    if vendor:
        products = Product.objects.filter(vendeur=vendor).select_related('vendeur')
    else:
        products = Product.objects.select_related('vendeur').all()

    if search:
        products = products.filter(
            Q(nom__icontains=search) | Q(description__icontains=search) | Q(vendeur__nom__icontains=search)
        )
    if categorie:
        products = products.filter(categorie=categorie)
    if vendeur_filter and not vendor:
        products = products.filter(vendeur__slug=vendeur_filter)

    context = {
        'products': products,
        'search_query': search,
        'categorie_filter': categorie,
        'vendeur_filter': vendeur_filter,
        'vendors': _get_active_vendors(),
        'categories': Product.CATEGORY_CHOICES,
        'total': products.count(),
        'is_vendor': vendor is not None,
    }
    return render(request, 'boutique/admin/products.html', context)


@login_required
def admin_product_add(request):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)

    if request.method == 'POST':
        if vendor:
            vendeur_id = str(vendor.pk)
        else:
            vendeur_id = request.POST.get('vendeur', '')
        nom = request.POST.get('nom', '').strip()
        categorie = request.POST.get('categorie', '')
        type_vente = request.POST.get('type_vente', 'detail')
        prix = _safe_non_negative_int(request.POST.get('prix', '0'))
        description = request.POST.get('description', '').strip()
        image_url = request.POST.get('image_url', '').strip()
        badge = request.POST.get('badge', '')
        note = _safe_positive_int(request.POST.get('note', '5'), default=5)
        stock = _safe_non_negative_int(request.POST.get('stock', '0'))
        prix_achat = _safe_non_negative_int(request.POST.get('prix_achat', '0'))
        seuil_alerte_stock = _safe_non_negative_int(request.POST.get('seuil_alerte_stock', '3'))
        lieu_stock = request.POST.get('lieu_stock', 'Conakry').strip() or 'Conakry'
        actif = request.POST.get('actif') == 'on'

        if not all([vendeur_id, nom, categorie, prix, description]):
            messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
            return render(request, 'boutique/admin/product_form.html', {
                'mode': 'add',
                'vendors': _get_active_vendors(),
                'categories': Product.CATEGORY_CHOICES,
                'type_vente_choices': Product.TYPE_VENTE_CHOICES,
                'badges': Product.BADGE_CHOICES,
                'form_data': request.POST,
                'is_vendor': vendor is not None,
            })

        vendeur = get_object_or_404(Vendor, pk=int(vendeur_id), actif=True)

        if vendor and vendeur.pk != vendor.pk:
            messages.error(request, 'Vous ne pouvez ajouter des produits que pour votre boutique.')
            return redirect('admin_products')

        product = Product(
            vendeur=vendeur,
            nom=nom,
            categorie=categorie,
            type_vente=type_vente,
            prix=prix,
            prix_achat=prix_achat,
            description=description,
            image_url=image_url or None,
            badge=badge,
            note=min(note, 5),
            stock=stock,
            seuil_alerte_stock=seuil_alerte_stock,
            lieu_stock=lieu_stock,
            actif=actif,
        )

        if 'image' in request.FILES:
            product.image = request.FILES['image']

        product.save()
        messages.success(request, f'Produit "{product.nom}" ajouté avec succès !')
        return redirect('admin_products')

    context = {
        'mode': 'add',
        'vendors': _get_active_vendors(),
        'categories': Product.CATEGORY_CHOICES,
        'type_vente_choices': Product.TYPE_VENTE_CHOICES,
        'badges': Product.BADGE_CHOICES,
        'is_vendor': vendor is not None,
    }
    return render(request, 'boutique/admin/product_form.html', context)


@login_required
def admin_product_edit(request, pk):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    product = get_object_or_404(Product, pk=pk)

    if vendor and product.vendeur != vendor:
        messages.error(request, 'Vous n\'avez pas accès à ce produit.')
        return redirect('admin_products')

    if request.method == 'POST':
        vendeur_id = request.POST.get('vendeur', '')
        if vendeur_id:
            product.vendeur = get_object_or_404(Vendor, pk=int(vendeur_id), actif=True)
        product.nom = request.POST.get('nom', '').strip()
        product.categorie = request.POST.get('categorie', '')
        product.type_vente = request.POST.get('type_vente', 'detail')
        product.prix = _safe_non_negative_int(request.POST.get('prix', '0'))
        product.prix_achat = _safe_non_negative_int(request.POST.get('prix_achat', '0'))
        product.description = request.POST.get('description', '').strip()
        product.badge = request.POST.get('badge', '')
        product.note = min(_safe_positive_int(request.POST.get('note', '5'), default=5), 5)
        product.stock = _safe_non_negative_int(request.POST.get('stock', '0'))
        product.seuil_alerte_stock = _safe_non_negative_int(request.POST.get('seuil_alerte_stock', '3'))
        product.lieu_stock = request.POST.get('lieu_stock', 'Conakry').strip() or 'Conakry'
        product.actif = request.POST.get('actif') == 'on'

        image_url = request.POST.get('image_url', '').strip()
        if image_url:
            product.image_url = image_url

        if 'image' in request.FILES:
            product.image = request.FILES['image']

        if not all([product.nom, product.categorie, product.prix, product.description]):
            messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
        else:
            product.save()
            messages.success(request, f'Produit "{product.nom}" mis à jour avec succès !')
            return redirect('admin_products')

    context = {
        'mode': 'edit',
        'product': product,
        'vendors': _get_active_vendors(),
        'categories': Product.CATEGORY_CHOICES,
        'type_vente_choices': Product.TYPE_VENTE_CHOICES,
        'badges': Product.BADGE_CHOICES,
    }
    return render(request, 'boutique/admin/product_form.html', context)


@login_required
@require_POST
def admin_product_delete(request, pk):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    product = get_object_or_404(Product, pk=pk)

    if vendor and product.vendeur != vendor:
        messages.error(request, 'Vous n\'avez pas accès à ce produit.')
        return redirect('admin_products')

    nom = product.nom

    try:
        with transaction.atomic():
            if product.image:
                product.image.delete(save=False)
            product.delete()
        messages.success(request, f'Produit "{nom}" supprimé définitivement.')
    except Exception:
        messages.error(request, f'Impossible de supprimer le produit "{nom}" pour le moment.')

    return redirect('admin_products')


# ============ COMPTABILITÉ / GESTION DES VENTES ============

@login_required
def admin_comptabilite(request):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    now = timezone.now()

    # Période de filtre
    periode = request.GET.get('periode', 'mois')
    if periode == 'semaine':
        date_debut = now - timedelta(days=7)
    elif periode == 'mois':
        date_debut = now - timedelta(days=30)
    elif periode == 'trimestre':
        date_debut = now - timedelta(days=90)
    elif periode == 'annee':
        date_debut = now - timedelta(days=365)
    else:
        date_debut = now - timedelta(days=30)

    # --- Produits et stock ---
    if vendor:
        products = Product.objects.filter(vendeur=vendor)
    else:
        products = Product.objects.all()

    total_produits = products.filter(actif=True).count()
    produits_stock_bas = products.filter(actif=True, stock__lte=F('seuil_alerte_stock'))
    nb_alertes_stock = produits_stock_bas.count()

    # --- Ventes sur le site (OrderItems terminées) ---
    if vendor:
        order_items_qs = OrderItem.objects.filter(
            vendeur=vendor,
            order__statut='terminee',
            order__date_commande__gte=date_debut,
        )
    else:
        order_items_qs = OrderItem.objects.filter(
            order__statut='terminee',
            order__date_commande__gte=date_debut,
        )

    ventes_site_qte = order_items_qs.aggregate(total=Sum('quantite'))['total'] or 0
    ventes_site_recette = order_items_qs.aggregate(
        total=Sum(F('prix_unitaire') * F('quantite'))
    )['total'] or 0

    # Coût d'achat des ventes site (via product.prix_achat)
    cout_achat_site = 0
    for item in order_items_qs.select_related('product'):
        if item.product and item.product.prix_achat:
            cout_achat_site += item.product.prix_achat * item.quantite

    benefice_site = ventes_site_recette - cout_achat_site

    # --- Ventes hors site ---
    if vendor:
        offline_qs = OfflineSale.objects.filter(vendeur=vendor, date_vente__gte=date_debut)
    else:
        offline_qs = OfflineSale.objects.filter(date_vente__gte=date_debut)

    ventes_hors_site_qte = offline_qs.aggregate(total=Sum('quantite'))['total'] or 0
    ventes_hors_site_recette = offline_qs.aggregate(
        total=Sum(F('prix_vente') * F('quantite'))
    )['total'] or 0
    cout_achat_hors_site = offline_qs.aggregate(
        total=Sum(F('prix_achat') * F('quantite'))
    )['total'] or 0
    benefice_hors_site = ventes_hors_site_recette - cout_achat_hors_site

    # --- Totaux ---
    total_qte_vendus = ventes_site_qte + ventes_hors_site_qte
    total_recette = ventes_site_recette + ventes_hors_site_recette
    total_cout_achat = cout_achat_site + cout_achat_hors_site
    total_benefice = benefice_site + benefice_hors_site

    # --- Top produits vendus (site) ---
    top_produits = order_items_qs.values('nom_produit').annotate(
        qte_vendue=Sum('quantite'),
        ca=Sum(F('prix_unitaire') * F('quantite')),
    ).order_by('-qte_vendue')[:10]

    # --- Dernières ventes hors site ---
    dernieres_offline = offline_qs[:10]

    def fmt(val):
        return f"{val:,.0f} GNF".replace(",", " ")

    context = {
        'periode': periode,
        'total_produits': total_produits,
        'nb_alertes_stock': nb_alertes_stock,
        'produits_stock_bas': produits_stock_bas,
        # Site
        'ventes_site_qte': ventes_site_qte,
        'ventes_site_recette': fmt(ventes_site_recette),
        'cout_achat_site': fmt(cout_achat_site),
        'benefice_site': fmt(benefice_site),
        'benefice_site_val': benefice_site,
        # Hors site
        'ventes_hors_site_qte': ventes_hors_site_qte,
        'ventes_hors_site_recette': fmt(ventes_hors_site_recette),
        'cout_achat_hors_site': fmt(cout_achat_hors_site),
        'benefice_hors_site': fmt(benefice_hors_site),
        'benefice_hors_site_val': benefice_hors_site,
        # Totaux
        'total_qte_vendus': total_qte_vendus,
        'total_recette': fmt(total_recette),
        'total_cout_achat': fmt(total_cout_achat),
        'total_benefice': fmt(total_benefice),
        'total_benefice_val': total_benefice,
        # Détails
        'top_produits': top_produits,
        'dernieres_offline': dernieres_offline,
    }
    return render(request, 'boutique/admin/comptabilite.html', context)


@login_required
def admin_offline_sales(request):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)

    if vendor:
        sales = OfflineSale.objects.filter(vendeur=vendor).select_related('product', 'vendeur')
    else:
        sales = OfflineSale.objects.select_related('product', 'vendeur').all()

    context = {
        'sales': sales,
        'is_vendor': vendor is not None,
    }
    return render(request, 'boutique/admin/offline_sales.html', context)


@login_required
def admin_offline_sale_add(request):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)

    if request.method == 'POST':
        product_id = request.POST.get('product', '')
        nom_produit = request.POST.get('nom_produit', '').strip()
        quantite = _safe_positive_int(request.POST.get('quantite', '1'))
        prix_vente = _safe_non_negative_int(request.POST.get('prix_vente', '0'))
        prix_achat = _safe_non_negative_int(request.POST.get('prix_achat', '0'))
        client_nom = request.POST.get('client_nom', '').strip()
        client_telephone = request.POST.get('client_telephone', '').strip()
        notes = request.POST.get('notes', '').strip()

        product = None
        if product_id:
            try:
                product = Product.objects.get(pk=int(product_id))
                if vendor and product.vendeur != vendor:
                    product = None
                else:
                    if not nom_produit:
                        nom_produit = product.nom
                    if not prix_vente:
                        prix_vente = int(product.prix)
                    if not prix_achat:
                        prix_achat = int(product.prix_achat)
            except (Product.DoesNotExist, ValueError):
                product = None

        if not nom_produit:
            messages.error(request, 'Veuillez indiquer le nom du produit.')
            return render(request, 'boutique/admin/offline_sale_form.html', {
                'mode': 'add',
                'products': Product.objects.filter(vendeur=vendor) if vendor else Product.objects.all(),
                'form_data': request.POST,
                'is_vendor': vendor is not None,
            })

        sale_vendor = vendor
        if not sale_vendor and product:
            sale_vendor = product.vendeur
        if not sale_vendor:
            messages.error(request, 'Impossible de déterminer le vendeur.')
            return redirect('admin_offline_sales')

        sale = OfflineSale.objects.create(
            vendeur=sale_vendor,
            product=product,
            nom_produit=nom_produit,
            quantite=quantite,
            prix_vente=prix_vente,
            prix_achat=prix_achat,
            client_nom=client_nom,
            client_telephone=client_telephone,
            notes=notes,
        )

        # Décrémenter le stock si lié à un produit
        if product:
            product.stock = max(0, product.stock - quantite)
            product.save(update_fields=['stock'])

        messages.success(request, f'Vente hors site "{sale.nom_produit}" enregistrée !')
        return redirect('admin_offline_sales')

    if vendor:
        products = Product.objects.filter(vendeur=vendor, actif=True)
    else:
        products = Product.objects.filter(actif=True).select_related('vendeur')

    context = {
        'mode': 'add',
        'products': products,
        'is_vendor': vendor is not None,
    }
    return render(request, 'boutique/admin/offline_sale_form.html', context)


@login_required
@require_POST
def admin_offline_sale_delete(request, pk):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)
    sale = get_object_or_404(OfflineSale, pk=pk)

    if vendor and sale.vendeur != vendor:
        messages.error(request, 'Vous n\'avez pas accès à cette vente.')
        return redirect('admin_offline_sales')

    sale.delete()
    messages.success(request, 'Vente hors site supprimée.')
    return redirect('admin_offline_sales')


@login_required
def admin_stock_alerts(request):
    if not request.user.is_staff:
        return redirect('home')

    vendor = _get_current_vendor(request)

    if vendor:
        products = Product.objects.filter(vendeur=vendor, actif=True)
    else:
        products = Product.objects.filter(actif=True).select_related('vendeur')

    produits_alerte = products.filter(stock__lte=F('seuil_alerte_stock')).order_by('stock')
    produits_ok = products.filter(stock__gt=F('seuil_alerte_stock')).order_by('stock')

    context = {
        'produits_alerte': produits_alerte,
        'produits_ok': produits_ok,
        'total_alertes': produits_alerte.count(),
        'is_vendor': vendor is not None,
    }
    return render(request, 'boutique/admin/stock_alerts.html', context)


@login_required
def admin_logout(request):
    logout(request)
    messages.success(request, 'Déconnexion réussie.')
    return redirect('home')
