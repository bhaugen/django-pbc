from django.db.models import Q
from django.http import Http404
from django.views.generic import list_detail
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.template import RequestContext
import datetime
import time
from models import *
from forms import *
import csv
from django.http import HttpResponse
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.core.mail import send_mail
from django.forms.formsets import formset_factory

from decimal import *

try:
    from notification import models as notification
except ImportError:
    notification = None

# Several of the views here are based on
# http://collingrady.com/2008/02/18/editing-multiple-objects-in-django-with-newforms/
# Could now be switched to use formsets.

@login_required
def send_fresh_list(request):
    if request.method == "POST":
        if notification:
            try:
                food_network = FoodNetwork.objects.get(pk=1)
                food_network_name = food_network.long_name
            except FoodNetwork.DoesNotExist:
                request.user.message_set.create(message="Food Network does not exist")

            if food_network:
                week_of = current_week()
                fresh_list = food_network.fresh_list()
                users = list(Customer.objects.all())
                users.append(food_network)
                notification.send(users, "distribution_fresh_list", {"fresh_list": fresh_list, "week_of": week_of})
                request.user.message_set.create(message="Fresh List emails have been sent")
        return HttpResponseRedirect(request.POST["next"])
    
@login_required
def send_pickup_list(request):
    if request.method == "POST":
        if notification:
            try:
                food_network = FoodNetwork.objects.get(pk=1)
                food_network_name = food_network.long_name
            except FoodNetwork.DoesNotExist:
                request.user.message_set.create(message="Food Network does not exist")

            if food_network:
                pickup_date = current_week()
                pickup_list = food_network.pickup_list()
                for pickup in pickup_list:
                    dist = pickup_list[pickup]
                    item_list = dist.custodians.values()
                    item_list.sort(lambda x, y: cmp(x.custodian, y.custodian))   
                    users = [dist, food_network]
                    notification.send(users, "distribution_pickup_list", {
                            "pickup_list": item_list, 
                            "pickup_date": pickup_date,
                            "distributor": dist.distributor})
                request.user.message_set.create(message="Pickup List emails have been sent")
        return HttpResponseRedirect(request.POST["next"])
    
@login_required
def send_delivery_list(request):
    if request.method == "POST":
        if notification:
            try:
                food_network = FoodNetwork.objects.get(pk=1)
                food_network_name = food_network.long_name
            except FoodNetwork.DoesNotExist:
                request.user.message_set.create(message="Food Network does not exist")

            if food_network:
                order_date = current_week()
                delivery_list = food_network.delivery_list()
                for distributor in delivery_list:
                    dist = delivery_list[distributor]
                    order_list = dist.customers.values()
                    order_list.sort(lambda x, y: cmp(x.customer, y.customer))
                    users = [dist, food_network]
                    notification.send(users, "distribution_order_list", {
                            "order_list": order_list, 
                            "order_date": order_date,
                            "distributor": dist.distributor})
                request.user.message_set.create(message="Order List emails have been sent")
        return HttpResponseRedirect(request.POST["next"])

@login_required
def send_order_notices(request):
    if request.method == "POST":
        if notification:
            try:
                food_network = FoodNetwork.objects.get(pk=1)
                food_network_name = food_network.long_name
            except FoodNetwork.DoesNotExist:
                request.user.message_set.create(message="Food Network does not exist")

            if food_network:
                thisdate = current_week()
                weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
                weekend = weekstart + datetime.timedelta(days=5)
                order_list = Order.objects.filter(order_date__range=(weekstart, weekend))
                for order in order_list:
                    users = [order.customer, food_network]
                    notification.send(users, "distribution_order_notice", {
                            "order": order, 
                            "order_date": thisdate})
                request.user.message_set.create(message="Order Notice emails have been sent")
        return HttpResponseRedirect(request.POST["next"])

def json_customer_info(request, customer_id):
    # Note: serializer requires an iterable, not a single object. Thus filter rather than get.
    data = serializers.serialize("json", Customer.objects.filter(pk=customer_id))
    return HttpResponse(data, mimetype="text/json-comment-filtered")


def json_producer_info(request, producer_id):
    data = serializers.serialize("json", Party.objects.filter(pk=producer_id))
    return HttpResponse(data, mimetype="text/json-comment-filtered")

@login_required
def plan_selection(request):
    if request.method == "POST":
        psform = PlanSelectionForm(request.POST)  
        if psform.is_valid():
            psdata = psform.cleaned_data
            producer_id = psdata['producer']
            return HttpResponseRedirect('/%s/%s/'
               % ('planupdate', producer_id))
    else:
        psform = PlanSelectionForm()
    return render_to_response('distribution/plan_selection.html', {'header_form': psform})

@login_required
def plan_update(request, prod_id):
    try:
        producer = Party.objects.get(pk=prod_id)
    except Party.DoesNotExist:
        raise Http404
    if request.method == "POST":
        itemforms = create_plan_forms(producer, request.POST)     
        if all([itemform.is_valid() for itemform in itemforms]):
            producer_id = request.POST['producer-id']
            producer = Producer.objects.get(pk=producer_id)
            for itemform in itemforms:
                data = itemform.cleaned_data
                prodname = data['prodname']
                item_id = data['item_id']
                from_date = data['from_date']
                to_date = data['to_date']
                quantity = data['quantity']
                if item_id:
                    item = ProductPlan.objects.get(pk=item_id)
                    item.from_date = from_date
                    item.to_date = to_date
                    item.quantity = quantity
                    item.save()
                else:
                    if quantity > 0:
                        prodname = data['prodname']
                        product = Product.objects.get(short_name__exact=prodname)
                        item = itemform.save(commit=False)
                        item.producer = producer
                        item.product = product
                        item.save()
            return HttpResponseRedirect('/%s/%s/'
               % ('producerplan', producer_id))
        #else:
        #    for itemform in itemforms:
        #        if not itemform.is_valid():
        #            print '**invalid**', itemform
    else:
        itemforms = create_plan_forms(producer)
    return render_to_response('distribution/plan_update.html', {'producer': producer, 'item_forms': itemforms})

@login_required
def inventory_selection(request):
    # default date is Monday
    #availdate = datetime.date.today()
    #availdate = availdate - datetime.timedelta(days=datetime.date.weekday(availdate))
    if request.method == "POST":
        ihform = InventorySelectionForm(request.POST)  
        if ihform.is_valid():
            ihdata = ihform.cleaned_data
            producer_id = ihdata['producer']
            inv_date = ihdata['avail_date']
            if ihdata['meat']:
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/' 
                    % ('meatupdate', producer_id, inv_date.year, inv_date.month, inv_date.day))
            else:
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                   % ('inventoryupdate', producer_id, inv_date.year, inv_date.month, inv_date.day))
    else:
        #ihform = InventorySelectionForm(initial={'avail_date': availdate, })
    #return render_to_response('distribution/inventory_selection.html', {'avail_date': availdate, 'header_form': ihform})
        ihform = InventorySelectionForm()
    return render_to_response('distribution/inventory_selection.html', {'header_form': ihform})

@login_required
def inventory_update(request, prod_id, year, month, day):
    availdate = datetime.date(int(year), int(month), int(day))
    try:
        producer = Party.objects.get(pk=prod_id)
    except Party.DoesNotExist:
        raise Http404
    if request.method == "POST":
        itemforms = create_inventory_item_forms(producer, availdate, request.POST)     
        if all([itemform.is_valid() for itemform in itemforms]):
            producer_id = request.POST['producer-id']
            producer = Producer.objects.get(pk=producer_id)
            inv_date = request.POST['avail-date']
            for itemform in itemforms:
                data = itemform.cleaned_data
                prodname = data['prodname']
                item_id = data['item_id']
                custodian = data['custodian']
                inventory_date = data['inventory_date']
                planned = data['planned']
                received = data['received']
                notes = data['notes']
                if item_id:
                    item = InventoryItem.objects.get(pk=item_id)
                    item.custodian = custodian
                    item.inventory_date = inventory_date
                    rem_change = planned - item.planned
                    item.planned = planned
                    item.remaining = item.remaining + rem_change
                    oh_change = received - item.received                 
                    item.received = received
                    item.onhand = item.onhand + oh_change
                    item.notes = notes
                    item.save()
                else:
                    if planned + received > 0:
                        prodname = data['prodname']
                        product = Product.objects.get(short_name__exact=prodname)
                        item = itemform.save(commit=False)
                        item.producer = producer
                        item.custodian = custodian
                        item.inventory_date = inventory_date
                        item.product = product
                        item.remaining = planned
                        item.onhand = received
                        item.notes = notes
                        item.save()
            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
               % ('produceravail', producer_id, year, month, day))
    else:
        itemforms = create_inventory_item_forms(producer, availdate)
    return render_to_response('distribution/inventory_update.html', {'avail_date': availdate, 'producer': producer, 'item_forms': itemforms})

@login_required
def order_selection(request):
    if request.method == "POST":
        ihform = OrderSelectionForm(request.POST)  
        if ihform.is_valid():
            ihdata = ihform.cleaned_data
            customer_id = ihdata['customer']
            ord_date = ihdata['order_date']
            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
               % ('orderbylot', customer_id, ord_date.year, ord_date.month, ord_date.day))
    else:
        #ihform = OrderSelectionForm(initial={'order_date': orderdate, })
    #return render_to_response('distribution/order_selection.html', {'order_date': orderdate, 'header_form': ihform})
        ihform = OrderSelectionForm()
    return render_to_response('distribution/order_selection.html', {'header_form': ihform})


@login_required
def order_update(request, cust_id, year, month, day):
    orderdate = datetime.date(int(year), int(month), int(day))
    availdate = orderdate

    try:
        fn = FoodNetwork.objects.get(pk=1)
    except FoodNetwork.DoesNotExist:
        return render_to_response('distribution/network_error.html')

    cust_id = int(cust_id)
    try:
        customer = Customer.objects.get(pk=cust_id)
    except Customer.DoesNotExist:
        raise Http404

    try:
        order = Order.objects.get(customer=customer, order_date=orderdate)
    except MultipleObjectsReturned:
        order = Order.objects.filter(customer=customer, order_date=orderdate)[0]
    except Order.DoesNotExist:
        order = False

    if request.method == "POST":
        if order:
            ordform = OrderForm(request.POST, instance=order)
        else:
            ordform = OrderForm(request.POST)
        itemforms = create_order_item_forms(order, availdate, orderdate, request.POST)     
        if ordform.is_valid() and all([itemform.is_valid() for itemform in itemforms]):
            if order:
                the_order = ordform.save()
            else:
                the_order = ordform.save(commit=False)
                the_order.customer = customer
                the_order.order_date = orderdate
                the_order.save()
            for itemform in itemforms:
                data = itemform.cleaned_data
                qty = data['quantity'] 
                if itemform.instance.id:
                    if qty > 0:
                        itemform.save()
                    else:
                        itemform.instance.delete()
                else:                    
                    if qty > 0:
                        # these product gyrations wd not be needed if I cd make the product field readonly
                        # or display the product field value (instead of the input widget) in the template
                        prodname = data['prodname']
                        product = Product.objects.get(short_name__exact=prodname)
                        oi = itemform.save(commit=False)
                        oi.order = the_order
                        oi.product = product
                        oi.save()
            return HttpResponseRedirect('/%s/%s/'
               % ('order', the_order.id))
    else:
        if order:
            ordform = OrderForm(instance=order)
        else:
            ordform = OrderForm(initial={'customer': customer, 'order_date': orderdate, })
        itemforms = create_order_item_forms(order, availdate, orderdate)
    return render_to_response('distribution/order_update.html', 
        {'customer': customer, 'order': order, 'order_date': orderdate, 'avail_date': availdate, 'order_form': ordform, 'item_forms': itemforms})

def create_order_by_lot_forms(order, order_date, data=None):    
    try:
        food_network = FoodNetwork.objects.get(pk=1)
    except FoodNetwork.DoesNotExist:
        raise Http404
    
    items = food_network.all_avail_items(order_date)

    initial_data = []
    
    product_dict = {}
    if order:
        for oi in order.orderitem_set.all():
            product_dict[oi.product] = True
            item = oi.lot()
            avail = oi.quantity
            if item.remaining:
                avail = item.remaining + oi.quantity
            if item.onhand:
                avail = item.onhand + oi.quantity
            dict ={
                'order_item_id': oi.id,
                'lot_id': item.id,
                'product_id': oi.product.id,
                'avail': avail, 
                'lot_label': item.lot_id(),
                'unit_price': item.product.price,
                'quantity': oi.quantity,
                'notes': oi.notes}
            initial_data.append(dict)

    for item in items:
        if not item.product in product_dict:
            # all_avail_items must have either remaining or onhand qty
            if item.remaining:
                avail = item.remaining
            else:
                avail = item.onhand 
            dict ={
                'order_item_id': None,
                'lot_id': item.id,
                'product_id': item.product.id,
                'avail': avail, 
                'lot_label': item.lot_id(),
                'unit_price': item.product.price,
                'quantity': Decimal(0),
                'notes': ""}
            initial_data.append(dict)
                       
    OrderByLotFormSet = formset_factory(OrderByLotForm, extra=0)
    formset = OrderByLotFormSet(initial=initial_data)
    return formset

@login_required
def order_by_lot(request, cust_id, year, month, day):
    orderdate = datetime.date(int(year), int(month), int(day))
    
    try:
        fn = FoodNetwork.objects.get(pk=1)
    except FoodNetwork.DoesNotExist:
        return render_to_response('distribution/network_error.html')

    cust_id = int(cust_id)
    try:
        customer = Customer.objects.get(pk=cust_id)
    except Customer.DoesNotExist:
        raise Http404

    try:
        order = Order.objects.get(customer=customer, order_date=orderdate)
    except MultipleObjectsReturned:
        order = Order.objects.filter(customer=customer, order_date=orderdate)[0]
    except Order.DoesNotExist:
        order = False

    if request.method == "POST":
        if order:
            ordform = OrderForm(request.POST, instance=order)
        else:
            ordform = OrderForm(request.POST)
        OrderByLotFormSet = formset_factory(OrderByLotForm, extra=0)
        formset = OrderByLotFormSet(request.POST)
        if ordform.is_valid() and formset.is_valid():
            if order:
                the_order = ordform.save()
            else:
                the_order = ordform.save(commit=False)
                the_order.customer = customer
                the_order.order_date = orderdate
                the_order.save()
            for form in formset.forms:
                data = form.cleaned_data
                qty = data["quantity"]
                oi_id = data["order_item_id"]
                product_id = data["product_id"]
                product = Product.objects.get(pk=product_id)                
                unit_price = data["unit_price"]
                notes = data["notes"]
                lot_id = data["lot_id"]
                lot = InventoryItem.objects.get(pk=lot_id)
                if oi_id:
                    oi = OrderItem.objects.get(pk=oi_id)
                    if oi.quantity != qty:
                        delivery = oi.inventorytransaction_set.all()[0]
                        if qty > 0:
                            oi.quantity = qty
                            oi.notes=notes
                            oi.save()
                            delivery.quantity=qty
                            delivery.save()
                        else:
                            delivery.delete()
                            oi.delete()                      
                    elif oi.notes != notes:
                        oi.notes=notes
                        oi.save()         
                else:
                    if qty:
                        oi = OrderItem(
                            order=the_order,
                            product=product,
                            quantity=qty,
                            unit_price=unit_price,
                            notes=notes)
                        oi.save()
                        delivery = InventoryTransaction(
                            transaction_type="Delivery",
                            inventory_item=lot,
                            order_item=oi,
                            quantity=qty,
                            transaction_date=orderdate)
                        delivery.save()
            #end of processing
            return HttpResponseRedirect('/%s/%s/'
               % ('order', the_order.id))
        #if invalid
        else:
            if order:
                ordform = OrderForm(instance=order)
            else:
                ordform = OrderForm(initial={'customer': customer, 'order_date': orderdate, })
            formset = create_order_by_lot_forms(order, orderdate)                     
    else:
        if order:
            ordform = OrderForm(instance=order)
        else:
            ordform = OrderForm(initial={'customer': customer, 'order_date': orderdate, })
        formset = create_order_by_lot_forms(order, orderdate) 
        
    return render_to_response('distribution/order_by_lot.html', 
        {'customer': customer, 
         'order': order, 
         'order_date': orderdate, 
         'order_form': ordform, 
         'formset': formset})    

@login_required
def order_entry(request):
    try:
        fn = FoodNetwork.objects.get(pk=1)
    except FoodNetwork.DoesNotExist:
        return render_to_response('distribution/network_error.html')
    # based on http://collingrady.com/2008/02/18/editing-multiple-objects-in-django-with-newforms/
    # for now, avail date is Wednesday
    #thisdate = datetime.date.today() +  datetime.timedelta(days=3)
    availdate = datetime.date.today()
    availdate = availdate - datetime.timedelta(days=datetime.date.weekday(availdate)) + datetime.timedelta(days=2)
    orderdate = availdate + datetime.timedelta(days=1)
    if request.method == "POST":
        ordform = OrderForm(request.POST, instance=Order())
        itemforms = create_order_item_forms(availdate, orderdate, request.POST)     
        if ordform.is_valid() and all([itemform.is_valid() for itemform in itemforms]):
            new_order = ordform.save()
            for itemform in itemforms:
                data = itemform.cleaned_data
                qty = data['quantity'] 
                if qty > 0:
                    # these product gyrations wd not be needed if I cd make the product field readonly
                    # or display the product field value (instead of the input widget) in the template
                    prodname = data['prodname']
                    product = Product.objects.get(short_name__exact=prodname)
                    oi = itemform.save(commit=False)
                    oi.order = new_order
                    oi.product = product
                    oi.save()
            return HttpResponseRedirect('/%s/%s/'
               % ('order', new_order.id))
    else:
        ordform = OrderForm(initial={'order_date': orderdate, })
        itemforms = create_order_item_forms(availdate, orderdate)
    return render_to_response('distribution/order_entry.html', {'avail_date': availdate, 'order_form': ordform, 'item_forms': itemforms})

@login_required
def delivery_selection(request):
    if request.method == "POST":
        dsform = DeliverySelectionForm(request.POST)  
        if dsform.is_valid():
            dsdata = dsform.cleaned_data
            cust_id = dsdata['customer']
            ord_date = dsdata['order_date']
            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
               % ('deliveryupdate', cust_id, ord_date.year, ord_date.month, ord_date.day))
    else:
        #dsform = DeliverySelectionForm(initial={'order_date': order_date, })
    #return render_to_response('distribution/delivery_selection.html', {'order_date': order_date, 'header_form': dsform})
        dsform = DeliverySelectionForm()
    return render_to_response('distribution/delivery_selection.html', {'header_form': dsform})

@login_required
def delivery_update(request, cust_id, year, month, day):
    thisdate = datetime.date(int(year), int(month), int(day))
    cust_id = int(cust_id)
    if cust_id:
        try:
            customer = Customer.objects.get(pk=cust_id)
        except Customer.DoesNotExist:
            raise Http404
    else:
        customer = ''
        
    try:
        food_network = FoodNetwork.objects.get(pk=1)
    except FoodNetwork.DoesNotExist:
        raise Http404
    
    #todo: finish this thought
    lots = food_network.all_avail_items(thisdate)
    lot_list = []
    for lot in lots:
        lot_list.append([lot.id, float(lot.avail_qty())])

    if request.method == "POST":
        itemforms = create_delivery_forms(thisdate, customer, request.POST)
        for itemform in itemforms:
            if itemform.is_valid():
                item_data = itemform.cleaned_data
                oi_id = item_data['order_item_id']
                order_item = OrderItem.objects.get(pk=oi_id)
                for delform in itemform.delivery_forms:
                    if delform.is_valid():
                        del_data = delform.cleaned_data
                        inv_item = del_data['inventory_item']
                        qty = del_data['quantity']
                        if delform.instance.pk:
                            if qty > 0:
                                delform.save()
                            else:
                                delform.instance.delete()
                        else:
                            delivery = delform.save(commit=False) 
                            delivery.order_item = order_item
                            delivery.transaction_date = order_item.order.order_date
                            delivery.transaction_type='Delivery'
                            delivery.pay_producer = True
                            delivery.save()
        return HttpResponseRedirect('/%s/%s/%s/%s/' 
                                    % ('orderdeliveries', year, month, day))
    else:
        itemforms = create_delivery_forms(thisdate, customer)
    return render_to_response('distribution/delivery_update.html', {
        'order_date': thisdate, 
        'customer': customer, 
        'item_forms': itemforms,
        'lot_list': lot_list,
        })


def order_headings_by_product(thisdate, links=True):
    orders = Order.objects.filter(order_date=thisdate)
    heading_list = []
    for order in orders:
        lines = []
        if links:
            lines.append("<a href='/order/" + str(order.id) + "/'>" + order.customer.short_name + "</a>")
        else:
            lines.append(order.customer.short_name)
        lines.append(order.customer.contact)
        lines.append(order.customer.phone)
        heading = " ".join(str(i) for i in lines)
        heading_list.append(heading)
    return heading_list


def order_item_rows_by_product(thisdate):
    orders = Order.objects.filter(order_date=thisdate)
    cust_list = []
    for order in orders:
        cust_list.append(order.customer.short_name)
    cust_count = len(cust_list)
    prods = Product.objects.all()
    product_dict = {}
    for prod in prods:
        totavail = prod.total_avail(thisdate)
        totordered = prod.total_ordered(thisdate)
        if totordered > 0:
            producers = prod.avail_producers(thisdate)
            product_dict[prod.short_name] = [prod.parent_string(), prod.long_name, producers, totavail, totordered]
            for x in range(cust_count):
                product_dict[prod.short_name].append(' ')
    items = OrderItem.objects.filter(order__order_date=thisdate)
    for item in items:
        prod_cell = cust_list.index(item.order.customer.short_name) + 5
        product_dict[item.product.short_name][prod_cell] = item.quantity
    item_list = product_dict.values()
    item_list.sort()
    return item_list

def order_item_rows(thisdate):
    orders = Order.objects.filter(order_date=thisdate)
    cust_list = []
    for order in orders:
        cust_list.append(order.customer.id)
    cust_count = len(cust_list)
    prods = Product.objects.all()
    product_dict = {}
    for prod in prods:
        totavail = prod.total_avail(thisdate)
        totordered = prod.total_ordered(thisdate)
        if totordered > 0:
            producers = prod.avail_producers(thisdate)
            product_dict[prod.id] = [prod.parent_string(), prod.long_name, producers, totavail, totordered]
            for x in range(cust_count):
                product_dict[prod.id].append(' ')
    items = OrderItem.objects.filter(order__order_date=thisdate)
    for item in items:
        prod_cell = cust_list.index(item.order.customer.id) + 5
        product_dict[item.product.id][prod_cell] = item.quantity
    item_list = product_dict.values()
    item_list.sort()
    return item_list


def order_table_selection(request):
    if request.method == "POST":
        dsform = DateSelectionForm(request.POST)  
        if dsform.is_valid():
            dsdata = dsform.cleaned_data
            ord_date = dsdata['selected_date']
            return HttpResponseRedirect('/%s/%s/%s/%s/'
               % ('ordertable', ord_date.year, ord_date.month, ord_date.day))
    else:
        dsform = DateSelectionForm()
    return render_to_response('distribution/order_table_selection.html', {'dsform': dsform,})

ORDER_HEADINGS = ["Customer", "Order", "Lot", "Custodian", "Order Qty"]

def order_table(request, year, month, day):
    thisdate = datetime.date(int(year), int(month), int(day))
    date_string = thisdate.strftime('%Y_%m_%d')
    heading_list = ORDER_HEADINGS
    orders = Order.objects.filter(order_date=thisdate)
    for order in orders:
        order.rows = order.orderitem_set.all().count()
    item_list = OrderItem.objects.filter(order__order_date=thisdate)
    return render_to_response('distribution/order_table.html', 
        {'date': thisdate, 
         'datestring': date_string,
         'heading_list': heading_list, 
         'item_list': item_list,
         'orders': orders,})

def order_table_by_product(request, year, month, day):
    thisdate = datetime.date(int(year), int(month), int(day))
    heading_list = order_headings(thisdate)
    item_list = order_item_rows(thisdate)
    return render_to_response('distribution/order_table.html', {'date': thisdate, 'heading_list': heading_list, 'item_list': item_list})


def order_csv(request, order_date):
    thisdate = datetime.datetime(*time.strptime(order_date, '%Y_%m_%d')[0:5]).date()
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=ordersheet.csv'
    #thisdate = current_week()
    writer = csv.writer(response)
    writer.writerow(ORDER_HEADINGS)
    for item in OrderItem.objects.filter(order__order_date=thisdate):
        writer.writerow(
            [item.order.customer.long_name,
             "".join(["#", str(item.order.id), " ", item.order.order_date.strftime('%Y-%m-%d')]),
             item.lot(),
             item.lot().custodian,
             item.quantity]
             )
    return response


def order_csv_by_product(request):
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=ordersheet.csv'
    thisdate = current_week()
    product_heads = ['Item', 'Description', 'Producers', 'Avail', 'Ordered']
    order_heads = order_headings(thisdate, links=False)
    heading_list = product_heads + order_heads
    item_list = order_item_rows(thisdate)
    writer = csv.writer(response)
    writer.writerow(heading_list)
    for item in item_list:
        writer.writerow(item)
    return response


def order(request, order_id):
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        raise Http404
    return render_to_response('distribution/order.html', {'order': order})

def order_with_lots(request, order_id):
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        raise Http404
    return render_to_response('distribution/order_with_lots.html', {'order': order})

def producerplan(request, prod_id):
    try:
        producer = Party.objects.get(pk=prod_id)
    except Party.DoesNotExist:
        raise Http404
    plans = list(ProductPlan.objects.filter(producer=producer))
    for plan in plans:
        plan.parents = plan.product.parent_string()
    plans.sort(lambda x, y: cmp(x.parents, y.parents))
        
    return render_to_response('distribution/producer_plan.html', {'producer': producer, 'plans': plans })

def produceravail(request, prod_id, year, month, day):
    availdate = datetime.date(int(year), int(month), int(day))
    availdate = availdate - datetime.timedelta(days=datetime.date.weekday(availdate)) + datetime.timedelta(days=2)
    weekstart = availdate - datetime.timedelta(days=datetime.date.weekday(availdate))
    try:
        producer = Party.objects.get(pk=prod_id)
        inventory = InventoryItem.objects.filter(
            Q(producer=producer) &
            (Q(onhand__gt=0) | Q(inventory_date__range=(weekstart, availdate))))
    except Party.DoesNotExist:
        raise Http404
    return render_to_response('distribution/producer_avail.html', {'producer': producer, 'avail_date': weekstart, 'inventory': inventory })

def meatavail(request, prod_id, year, month, day):
    availdate = datetime.date(int(year), int(month), int(day))
    availdate = availdate - datetime.timedelta(days=datetime.date.weekday(availdate)) + datetime.timedelta(days=5)
    weekstart = availdate - datetime.timedelta(days=datetime.date.weekday(availdate))
    try:
        producer = Party.objects.get(pk=prod_id)
        inventory = InventoryItem.objects.filter(
            Q(producer=producer) &
            (Q(onhand__gt=0) | Q(inventory_date__range=(weekstart, availdate))))
    except Party.DoesNotExist:
        raise Http404
    return render_to_response('distribution/meat_avail.html', {'producer': producer, 'avail_date': weekstart, 'inventory': inventory })



def all_avail(request):

    return list_detail.object_list(
        request,
        queryset = AvailItem.objects.select_related().order_by(
            'distribution_availproducer.avail_date', 'distribution_product.short_name', 'distribution_producer.short_name'),
        template_name = "distribution/avail_list.html",
    )


def welcome(request):
    return render_to_response('welcome.html')

#changed help to flatpage
def help(request):
    return render_to_response('distribution/help.html')

class ProductActivity():
    def __init__(self, category, product, avail, ordered, delivered, lots):
        self.category = category
        self.product = product
        self.avail = avail
        self.ordered = ordered
        self.delivered = delivered
        self.lots = lots


def dashboard(request):
    try:
        food_network = FoodNetwork.objects.get(pk=1)
        food_network_name = food_network.long_name
    except FoodNetwork.DoesNotExist:
        food_network_name = "Food Group"
    
    thisdate = current_week()
    week_form = CurrentWeekForm(initial={"current_week": thisdate})

    item_list = food_network.all_active_items().order_by("custodian")
    return render_to_response('distribution/index.html', 
        {'item_list': item_list,
         'order_date': thisdate,
         'week_form': week_form,
         'food_network_name': food_network_name,     
         }, context_instance=RequestContext(request))


def reset_week(request):
    if request.method == "POST":
        try:
            food_network = FoodNetwork.objects.get(pk=1)
            food_network_name = food_network.long_name
            form = CurrentWeekForm(request.POST)
            if form.is_valid():
                current_week = form.cleaned_data['current_week']
                food_network.current_week = current_week
                food_network.save()
        except FoodNetwork.DoesNotExist:
            pass
    return HttpResponseRedirect("/dashboard/")   

def all_orders(request):
    return list_detail.object_list(
        request,
        queryset = OrderItem.objects.all(),
        template_name = "distribution/order_list.html",
    )


def all_deliveries(request):
    return list_detail.object_list(
        request,
        queryset = InventoryTransaction.objects.filter(transaction_type='Delivery'),
        template_name = "distribution/delivery_list.html",
    )


def orders_with_deliveries(request, year, month, day):
    thisdate = datetime.date(int(year), int(month), int(day))
    orderitem_list = OrderItem.objects.select_related().filter(order__order_date=thisdate).order_by('order', 'distribution_product.short_name')
    return render_to_response('distribution/order_delivery_list.html', {'order_date': thisdate, 'orderitem_list': orderitem_list})

def payment_selection(request):
    if request.method == "POST":
        ihform = PaymentSelectionForm(request.POST)  
        if ihform.is_valid():
            ihdata = ihform.cleaned_data
            producer_id = ihdata['producer']
            from_date = ihdata['from_date'].strftime('%Y_%m_%d')
            to_date = ihdata['to_date'].strftime('%Y_%m_%d')
            paid_orders = 1 if ihdata['paid_orders'] else 0
            paid_producer = ihdata['paid_producer']
            return HttpResponseRedirect('/%s/%s/%s/%s/%s/%s/'
               % ('producerpayments', producer_id, from_date, to_date, paid_orders, paid_producer))
    else:
        #ihform = PaymentSelectionForm(initial={'from_date': thisdate, 'to_date': thisdate })
    #return render_to_response('distribution/payment_selection.html', {'avail_date': thisdate, 'header_form': ihform})
        ihform = PaymentSelectionForm()
    return render_to_response('distribution/payment_selection.html', {'header_form': ihform})

@login_required
def statement_selection(request):
    if request.method == "POST":
        hdrform = StatementSelectionForm(request.POST)  
        if hdrform.is_valid():
            hdrdata = hdrform.cleaned_data
            from_date = hdrdata['from_date'].strftime('%Y_%m_%d')
            to_date = hdrdata['to_date'].strftime('%Y_%m_%d')
            return HttpResponseRedirect('/%s/%s/%s/'
               % ('statements', from_date, to_date))
    else:
        hdrform = StatementSelectionForm()
    return render_to_response('distribution/statement_selection.html', {'header_form': hdrform})


def statements(request, from_date, to_date):
    try:
        from_date = datetime.datetime(*time.strptime(from_date, '%Y_%m_%d')[0:5]).date()
        to_date = datetime.datetime(*time.strptime(to_date, '%Y_%m_%d')[0:5]).date()
    except ValueError:
            raise Http404
        
    try:
        network = FoodNetwork.objects.get(pk=1)
    except FoodNetwork.DoesNotExist:
        raise Http404
    
    payments = Payment.objects.filter(payment_date__gte=from_date, payment_date__lte=to_date)
    return render_to_response('distribution/statements.html', 
              {'payments': payments, 'network': network, })   

def producer_payments(request, prod_id, from_date, to_date, paid_orders, paid_producer):
    try:
        from_date = datetime.datetime(*time.strptime(from_date, '%Y_%m_%d')[0:5]).date()
        to_date = datetime.datetime(*time.strptime(to_date, '%Y_%m_%d')[0:5]).date()
        paid_orders = int(paid_orders)
    except ValueError:
            raise Http404
    show_payments = True
    if paid_producer == 'unpaid':
        show_payments=False
    prod_id = int(prod_id)
    if prod_id:
        try:
            producer = Party.objects.get(pk=prod_id)
        except Party.DoesNotExist:
            raise Http404
        producer = one_producer_payments(producer, from_date, to_date, paid_orders, paid_producer)
        return render_to_response('distribution/one_producer_payments.html', 
              {'from_date': from_date, 'to_date': to_date, 'producer': producer, 'show_payments': show_payments })
    else:
        producer_list = all_producer_payments(from_date, to_date, paid_orders, paid_producer)
        return render_to_response('distribution/producer_payments.html', 
            {'from_date': from_date, 'to_date': to_date, 'producers': producer_list, 'show_payments': show_payments })

def one_producer_payments(producer, from_date, to_date, paid_orders, paid_producer):       
    if paid_orders:
        if paid_producer == 'paid':
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                order_item__order__paid__exact=True,
                inventory_item__producer=producer,
                transaction_type='Delivery').exclude(payment=None).order_by('order_item')
            procs = Processing.objects.filter(
                process_date__range=(from_date, to_date),
                processor=producer).exclude(payment=None)
            processings = []
            for proc in procs:
                tx = proc.inventory_transaction()
                if tx:
                    if tx.order_item:
                        if tx.order_item.order.paid:
                            processings.append(proc)
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date),
                paid=True, distributor=producer).exclude(transportation_payment=None)
        elif paid_producer == 'unpaid':
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                order_item__order__paid__exact=True,
                inventory_item__producer=producer,
                payment=None,
                transaction_type='Delivery').order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date),
                paid=True,
                transportation_payment=None,
                distributor=producer)
            procs = Processing.objects.filter(
                process_date__range=(from_date, to_date), 
                payment=None,
                processor=producer)
            processings = []
            for proc in procs:
                tx = proc.inventory_transaction()
                if tx:
                    if tx.order_item:
                        if tx.order_item.order.paid:
                            processings.append(proc)
        else:
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                order_item__order__paid__exact=True,
                inventory_item__producer=producer,
                transaction_type='Delivery').order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date), paid=True,
                distributor=producer)
            procs = Processing.objects.filter(
                process_date__range=(from_date, to_date), 
                processor=producer)
            processings = []
            for proc in procs:
                tx = proc.inventory_transaction()
                if tx:
                    if tx.order_item:
                        if tx.order_item.order.paid:
                            processings.append(proc)
    else:
        if paid_producer == 'paid':
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                inventory_item__producer=producer,
                transaction_type='Delivery').exclude(payment=None).order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date),
                distributor=producer).exclude(transportation_payment=None)
            processings = Processing.objects.filter(
                process_date__range=(from_date, to_date),
                processor=producer).exclude(payment=None)
        elif paid_producer == 'unpaid':
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                inventory_item__producer=producer,
                payment=None,
                transaction_type='Delivery').order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date), 
                transportation_payment=None,
                distributor=producer)
            processings = Processing.objects.filter(
                process_date__range=(from_date, to_date), 
                payment=None,
                processor=producer)
        else:
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                inventory_item__producer=producer,
                transaction_type='Delivery').order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date),
                distributor=producer)
            processings = Processing.objects.filter(
                process_date__range=(from_date, to_date),
                processor=producer)
                
    if paid_producer == 'paid':
        damaged = InventoryTransaction.objects.filter(
            transaction_date__range=(from_date, to_date), 
            inventory_item__producer=producer,
            transaction_type='Damage').exclude(payment=None).order_by('inventory_item')
    elif paid_producer == 'unpaid':
        damaged = InventoryTransaction.objects.filter(
            transaction_date__range=(from_date, to_date),
            inventory_item__producer=producer,
            payment=None, 
            transaction_type='Damage').order_by('inventory_item')
    else:   
        damaged = InventoryTransaction.objects.filter(
            transaction_date__range=(from_date, to_date), 
            transaction_type='Damage').order_by('inventory_item')
        
    rejected = InventoryTransaction.objects.filter(
        transaction_date__range=(from_date, to_date),
        transaction_type='Reject', 
        inventory_item__producer=producer).order_by('inventory_item')
    
    total_due = 0
    producer.deliveries = deliveries
    producer.damaged = damaged
    producer.rejected = rejected
    producer.processes = processings
    producer.transportations = transportations
    for delivery in deliveries:
        total_due += delivery.due_to_producer()
    for damage in damaged:
        total_due += damage.due_to_producer()
    for proc in processings:
        total_due += proc.cost
    for order in transportations:
        total_due += order.transportation_fee
    producer.total_due = total_due
    return producer

def all_producer_payments(from_date, to_date, paid_orders, paid_producer):
    delivery_producers = {}
    processors = {}
    transporters = {}
    damage_producers = {}
    reject_producers = {}
    
    # Logic summary:
    # 1. Collect the transactions (deliveries, damages, rejects and processing)
    # 2. Organize and total the transactions by party
    
    # Collect the transactions
    if paid_orders:
        if paid_producer == 'paid':
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                order_item__order__paid__exact=True,
                transaction_type='Delivery').exclude(payment=None).order_by('order_item')
            procs = Processing.objects.filter(
                process_date__range=(from_date, to_date)).exclude(payment=None)
            processings = []
            for proc in procs:
                tx = proc.inventory_transaction()
                if tx:
                    if tx.order_item:
                        if tx.order_item.order.paid:
                            processings.append(proc)
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date),
                paid=True).exclude(transportation_payment=None).exclude(distributor=None)
        elif paid_producer == 'unpaid':
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                order_item__order__paid__exact=True,
                payment=None,
                transaction_type='Delivery').order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date),
                paid=True,
                transportation_payment=None).exclude(distributor=None)
            procs = Processing.objects.filter(
                process_date__range=(from_date, to_date), 
                payment=None)
            processings = []
            for proc in procs:
                tx = proc.inventory_transaction()
                if tx:
                    if tx.order_item:
                        if tx.order_item.order.paid:
                            processings.append(proc)
        else:
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                order_item__order__paid__exact=True,
                transaction_type='Delivery').order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date), paid=True).exclude(distributor=None)
            procs = Processing.objects.filter(
                process_date__range=(from_date, to_date))
            processings = []
            for proc in procs:
                tx = proc.inventory_transaction()
                if tx:
                    if tx.order_item:
                        if tx.order_item.order.paid:
                            processings.append(proc)
    else:
        if paid_producer == 'paid':
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                transaction_type='Delivery').exclude(payment=None).order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date)).exclude(transportation_payment=None).exclude(distributor=None)
            processings = Processing.objects.filter(
                process_date__range=(from_date, to_date)).exclude(payment=None)
        elif paid_producer == 'unpaid':
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                payment=None,
                transaction_type='Delivery').order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date), transportation_payment=None).exclude(distributor=None)
            processings = Processing.objects.filter(
                process_date__range=(from_date, to_date), payment=None)
        else:
            deliveries = InventoryTransaction.objects.filter(
                transaction_date__range=(from_date, to_date),
                transaction_type='Delivery').order_by('order_item')
            transportations = Order.objects.filter(
                order_date__range=(from_date, to_date)).exclude(distributor=None)
            processings = Processing.objects.filter(
                process_date__range=(from_date, to_date))
                
    if paid_producer == 'paid':
        damaged = InventoryTransaction.objects.filter(
            transaction_date__range=(from_date, to_date), 
            transaction_type='Damage').exclude(payment=None).order_by('inventory_item')
    elif paid_producer == 'unpaid':
        damaged = InventoryTransaction.objects.filter(
            transaction_date__range=(from_date, to_date),
            payment=None, 
            transaction_type='Damage').order_by('inventory_item')
    else:   
        damaged = InventoryTransaction.objects.filter(
            transaction_date__range=(from_date, to_date), 
            transaction_type='Damage').order_by('inventory_item')
    
    rejected = InventoryTransaction.objects.filter(
        transaction_date__range=(from_date, to_date), 
        transaction_type='Reject').order_by('inventory_item')
        
    # Organize and total the transactions by party
    
    # Organize
    for delivery in deliveries:
        prod = delivery.inventory_item.producer
        delivery_producers.setdefault(prod, []).append(delivery)
    for proc in processings:
        processor = proc.processor
        processors.setdefault(processor, []).append(proc)
    for order in transportations:
        dist = order.distributor
        transporters.setdefault(dist, []).append(order)
    for damage in damaged:
        prod = damage.inventory_item.producer
        damage_producers.setdefault(prod, []).append(damage)
    for reject in rejected:
        prod = reject.inventory_item.producer
        reject_producers.setdefault(prod, []).append(reject)
    producer_list = []
    
    # Total
    for prod in delivery_producers:
        prod_deliveries = delivery_producers[prod]
        delivery_total_due = 0
        grand_total_due = 0
        for delivery in prod_deliveries:
            due_to_producer = delivery.due_to_producer()
            delivery_total_due += due_to_producer
            grand_total_due += due_to_producer
        if grand_total_due > 0:
            producer = prod
            producer.delivery_total_due = delivery_total_due
            producer.grand_total_due = grand_total_due
            producer.deliveries = prod_deliveries
            producer_list.append(producer)
    for prod in processors:
        prod_processes = processors[prod]
        process_total_due = 0
        for process in prod_processes:
            due_to_producer = process.cost
            process_total_due += due_to_producer
        if process_total_due > 0:
            producer = prod
            producer.process_total_due = process_total_due
            try:
                grand_total_due = producer.grand_total_due
            except:
                grand_total_due = 0
            grand_total_due += process_total_due
            producer.grand_total_due = grand_total_due
            producer.processes = prod_processes
            producer_list.append(producer)
    for dist in transporters:
        dist_orders = transporters[dist]
        transportation_total_due = 0
        for order in dist_orders:
            due_to_producer = order.transportation_fee
            transportation_total_due += due_to_producer
        if transportation_total_due > 0:
            producer = dist
            producer.transportation_total_due = transportation_total_due
            try:
                grand_total_due = producer.grand_total_due
            except:
                grand_total_due = 0
            grand_total_due += transportation_total_due
            producer.grand_total_due = grand_total_due
            producer.transportations = dist_orders
            producer_list.append(producer)
    for prod in damage_producers:
        prod_damages = damage_producers[prod]
        damage_total_due = 0
        for damage in prod_damages: 
            due_to_producer = damage.due_to_producer()
            damage_total_due += due_to_producer
        if damage_total_due > 0:
            producer = Producer.objects.get(short_name=prod)
            if producer in producer_list:
                producer = producer_list[producer_list.index(producer)]
            else:
                producer_list.append(producer)
            producer.damage_total_due = damage_total_due
            grand_total_due = producer.grand_total_due if producer.grand_total_due else 0
            grand_total_due += damage_total_due
            producer.grand_total_due = grand_total_due
            producer.damaged = prod_damages
    for prod in reject_producers:
        producer = prod
        if producer in producer_list:
            producer = producer_list[producer_list.index(producer)]
        else:
            producer_list.append(producer)
        producer.rejected = reject_producers[prod]
        
    producer_list.sort(lambda x, y: cmp(x.short_name, y.short_name))
    return producer_list

def payment(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    return render_to_response('distribution/payment.html', {'payment': payment})

@login_required
def payment_update_selection(request):
    if request.method == "POST":
        psform = PaymentUpdateSelectionForm(request.POST)  
        if psform.is_valid():
            psdata = psform.cleaned_data
            producer = psdata['producer'] if psdata['producer'] else 0
            payment = psdata['payment'] if psdata['payment'] else 0
            return HttpResponseRedirect('/%s/%s/%s/'
               % ('paymentupdate', producer, payment))
    else:
        psform = PaymentUpdateSelectionForm()
    return render_to_response('distribution/payment_update_selection.html', {'selection_form': psform})

@login_required
def payment_update(request, producer_id, payment_id):

    producer_id = int(producer_id)
    if producer_id:
        producer = get_object_or_404(Party, pk=producer_id)
    else:
        producer = ''

    payment_id = int(payment_id)
    if payment_id:
        payment = get_object_or_404(Payment, pk=payment_id)
        producer = payment.paid_to
    else:
        payment = ''

    if request.method == "POST":
        if payment:
            paymentform = PaymentForm(request.POST, instance=payment)
        else:
            paymentform = PaymentForm(request.POST)
        itemforms = create_payment_transaction_forms(producer, payment, request.POST)     
        if paymentform.is_valid() and all([itemform.is_valid() for itemform in itemforms]):
            the_payment = paymentform.save()
            for itemform in itemforms:
                data = itemform.cleaned_data
                paid = data['paid']
                tx_id = data['transaction_id']
                tx_type = data['transaction_type']
                if tx_type == 'Order':
                    tx = Order.objects.get(pk=tx_id)
                    if paid:
                        tx.transportation_payment = the_payment
                        tx.save()
                    else:
                        if tx.transportation_payment:
                            if tx.transportation_payment.id == the_payment.id:
                                tx.transportation_payment = None
                                tx.save()
                else:
                    if tx_type == 'Processing':
                        tx = Processing.objects.get(pk=tx_id)
                    else:
                        tx = InventoryTransaction.objects.get(pk=tx_id)
                    if paid:
                        tx.payment = the_payment
                        tx.save()
                    else:
                        if tx.payment:
                            if tx.payment.id == the_payment.id:
                                tx.payment = None
                                tx.save()
            return HttpResponseRedirect('/%s/%s/'
               % ('payment', the_payment.id))
    else:
        if payment:
            paymentform = PaymentForm(instance=payment)
        else:
            paymentform = PaymentForm(initial={'payment_date': datetime.date.today(),})
        paymentform.fields['paid_to'].choices = [(producer.id, producer.short_name)]
        itemforms = create_payment_transaction_forms(producer, payment)
    return render_to_response('distribution/payment_update.html', 
        {'payment': payment, 'payment_form': paymentform, 'item_forms': itemforms})

def json_payments(request, producer_id):
    # todo: shd limit to a few most recent payments
    data = serializers.serialize("json", Payment.objects.filter(paid_to=int(producer_id)))
    return HttpResponse(data, mimetype="text/json-comment-filtered")

@login_required
def invoice_selection(request):
    if request.method == "POST":
        dsform = DeliverySelectionForm(request.POST)  
        if dsform.is_valid():
            dsdata = dsform.cleaned_data
            cust_id = dsdata['customer']
            ord_date = dsdata['order_date']
            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
               % ('invoices', cust_id, ord_date.year, ord_date.month, ord_date.day))
    else:
        dsform = DeliverySelectionForm()
    return render_to_response('distribution/invoice_selection.html', {'header_form': dsform})

@login_required
def invoices(request, cust_id, year, month, day):
    try:
        fn = FoodNetwork.objects.get(pk=1)
    except FoodNetwork.DoesNotExist:
        return render_to_response('distribution/network_error.html')
    thisdate = datetime.date(int(year), int(month), int(day))
    cust_id = int(cust_id)
    if cust_id:
        try:
            customer = Customer.objects.get(pk=cust_id)
        except Customer.DoesNotExist:
            raise Http404
    else:
        customer = ''
    if customer:
        orders = Order.objects.filter(customer=customer, order_date=thisdate)
    else:
        orders = Order.objects.filter(order_date=thisdate)
    return render_to_response('distribution/invoices.html', {'orders': orders, 'network': fn,})

def advance_dates():
    orders = list(Order.objects.all())
    for order in orders:
        order.order_date = order.order_date + datetime.timedelta(days=7)
        order.save()
    items = list(InventoryItem.objects.all())
    for item in items:
        item.inventory_date = item.inventory_date + datetime.timedelta(days=7)
        item.save()
    txs = list(InventoryTransaction.objects.all())
    for tx in txs:
        tx.transaction_date = tx.transaction_date + datetime.timedelta(days=7)
        tx.save()
    payments = Payment.objects.all()
    for payment in payments:
        payment.payment_date = payment.payment_date + datetime.timedelta(days=7)
        payment.save()

@login_required
def next_week(request):
    if request.method == "POST":
        advance_dates()
        return HttpResponseRedirect('/dashboard')
    else:
        return render_to_response('distribution/next_week.html')
    
def send_email(request):
    if request.method == "POST":
        email_form = EmailForm(request.POST)
        if email_form.is_valid():
            data = email_form.cleaned_data
            from_email = data["email_address"]
            subject = data["subject"]
            message = data["message"]
            send_mail(subject, message, from_email, ["bob.haugen@gmail.com",])      
            return HttpResponseRedirect(reverse("email_sent"))
    else:
        email_form = EmailForm()
    
    return render_to_response("distribution/send_email.html", {
        "email_form": email_form,
    })
    
def send_ga_email(request):
    if request.method == "POST":
        email_form = EmailForm(request.POST)
        if email_form.is_valid():
            data = email_form.cleaned_data
            from_email = data["email_address"]
            subject = data["subject"]
            message = data["message"]
            send_mail(subject, message, from_email, ["bob.haugen@gmail.com",])      
            return HttpResponseRedirect(reverse("ga_email_sent"))
    else:
        email_form = EmailForm()
    
    return render_to_response("distribution/send_email.html", {
        "email_form": email_form,
    })

def create_meat_item_forms(producer, avail_date, data=None):
    #todo: is this the proper date range for PBC?
    monday = avail_date - datetime.timedelta(days=datetime.date.weekday(avail_date))
    saturday = monday + datetime.timedelta(days=5)
    items = InventoryItem.objects.filter(
        producer=producer, 
        product__meat=True,
        inventory_date__range=(monday, saturday))
    
    initial_data = []
        
    item_dict = {}
    for item in items:
        item_dict[item.product.id] = item
        processor_id = ""
        cost = 0
        try:
            processor_id = item.processing.processor.id
            cost = item.processing.cost
        except Processing.DoesNotExist:
            pass
        custodian_id = ""
        if item.custodian:
            custodian_id = item.custodian.id
        dict ={
            'item_id': item.id,
            'product': item.product.id, 
            'description': item.product.long_name,
            'custodian': custodian_id,
            'inventory_date': item.inventory_date,
            'planned': item.planned,
            'received': item.received,
            'notes': item.notes,
            'processor': processor_id,
            'cost': cost }
        initial_data.append(dict)
        
    plans = ProductPlan.objects.filter(
        producer=producer, 
        product__meat=True,
        from_date__lte=avail_date, 
        to_date__gte=saturday)
    product_list = []
    for plan in plans:
        product_list.append(plan.product)
        
    form_list = []

    for plan in plans:
        try:
            item = item_dict[plan.product.id]
        except KeyError:
            item = False
        if not item:
            dict = {
                'product': plan.product.id, 
                'description': plan.product.long_name,
                'inventory_date': avail_date,
                'planned': 0,
                'received': 0,
                'cost': 0,
                'notes': ''}
            initial_data.append(dict)
        
    for i in range(1, 6):
        dict={'inventory_date': avail_date,
            'planned': 0,
            'received': 0,
            'cost': 0}
        initial_data.append(dict)
        
    MeatItemFormSet = formset_factory(MeatItemForm, extra=0)
    formset = MeatItemFormSet(initial=initial_data)
    product_choices = [(prod.id, prod.long_name) for prod in product_list]
    for form in formset.forms:
        form.fields['product'].choices = product_choices
    return formset

@login_required
def meat_update(request, prod_id, year, month, day):
    avail_date = datetime.date(int(year), int(month), int(day))
    try:
        producer = Party.objects.get(pk=prod_id)
    except Party.DoesNotExist:
        raise Http404
    
    if request.method == "POST":
        MeatItemFormSet = formset_factory(MeatItemForm, extra=0)
        formset = MeatItemFormSet(request.POST)
        if formset.is_valid():
            producer_id = request.POST['producer-id']
            producer = Producer.objects.get(pk=producer_id)
            inv_date = request.POST['avail-date']
            for form in formset.forms:
                data = form.cleaned_data
                product = data['product']
                item_id = data['item_id']
                custodian = data['custodian']
                inventory_date = data['inventory_date']
                planned = data['planned']
                received = data['received']
                notes = data['notes']
                processor_id = data['processor']
                cost = data['cost']
                if item_id:
                    item = InventoryItem.objects.get(pk=item_id)
                    item.custodian = custodian
                    item.inventory_date = inventory_date
                    rem_change = planned - item.planned
                    item.planned = planned
                    item.remaining = item.remaining + rem_change
                    oh_change = received - item.received                 
                    item.received = received
                    item.onhand = item.onhand + oh_change
                    item.notes = notes
                    item.save()
                    item_processing = None
                    try:
                        item_processing = item.processing
                    except Processing.DoesNotExist:
                        pass
                    if processor_id:
                        processor = Processor.objects.get(id=processor_id)
                        if item_processing:
                            item_processing.processor = processor
                            item_processing.cost = cost
                            item_processing.save()
                        else:
                            processing = Processing(
                                inventory_item = item,
                                processor=processor,
                                cost=cost).save()
                else:
                    if planned + received > 0:
                        #prodname = data['prodname']
                        #product = Product.objects.get(short_name__exact=prodname)
                        item = form.save(commit=False)
                        item.producer = producer
                        item.custodian = custodian
                        item.inventory_date = inventory_date
                        item.product = product
                        item.remaining = planned
                        item.onhand = received
                        item.notes = notes
                        item.save()
                        if processor_id:
                            processor = Processor.objects.get(id=processor_id)
                            processing = Processing(
                                inventory_item = item,
                                processor=processor,
                                cost=cost).save()
            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
               % ('meatavail', producer_id, year, month, day))
                
    else:
        formset = create_meat_item_forms(producer, avail_date, data=None)
        
    return render_to_response('distribution/meat_update.html', {
        'avail_date': avail_date, 
        'producer': producer,
        'formset': formset})

@login_required
def process_selection(request):
    process_date = current_week()
    #initial_data = {"process_date": process_date}
    processes = Process.objects.filter(process_date=process_date)
    #psform = ProcessSelectionForm(data=request.POST or None, initial=initial_data)
    psform = ProcessSelectionForm(data=request.POST or None)
    if request.method == "POST":
        if psform.is_valid():
            data = psform.cleaned_data
            process_type_id = data['process_type']
            return HttpResponseRedirect('/%s/%s/'
               % ('newprocess', process_type_id))
    return render_to_response('distribution/process_selection.html', {
        'process_date': process_date,
        'header_form': psform,
        'processes': processes,})

@login_required
def new_process(request, process_type_id):
    weekstart = current_week()
    weekend = weekstart + datetime.timedelta(days=5)
    expired_date = weekstart + datetime.timedelta(days=5)
    pt = get_object_or_404(ProcessType, id=process_type_id)

    input_types = pt.input_type.sellable_children()
    input_select_form = None
    input_create_form = None
    input_lot_qties = []
    if pt.use_existing_input_lot:
        input_lots = InventoryItem.objects.filter(
            product__in=input_types, 
            inventory_date__lte=weekend,
            expiration_date__gte=expired_date,
            remaining__gt=Decimal("0"))
        initial_data = {"quantity": Decimal("0")}

        for lot in input_lots:
            input_lot_qties.append([lot.id, float(lot.avail_qty())])
        if input_lots:
            initial_data = {"quantity": input_lots[0].remaining,}
        input_select_form = InputLotSelectionForm(input_lots, data=request.POST or None, prefix="inputselection", initial=initial_data)
    else:
        input_create_form = InputLotCreationForm(input_types, data=request.POST or None, prefix="inputcreation")

    service_label = "Processing Service"
    service_formset = None
    #service_form = None
    steps = pt.number_of_processing_steps
    if steps > 1:
        service_label = "Processing Services"
        #ServiceFormSet = formset_factory(ProcessServiceForm, extra=steps)
        #service_formset = ServiceFormSet(data=request.POST or None, prefix="service")
    #else:
        #service_form = ProcessServiceForm(data=request.POST or None, prefix="service")

    ServiceFormSet = formset_factory(ProcessServiceForm, extra=steps)
    service_formset = ServiceFormSet(data=request.POST or None, prefix="service")

    output_types = pt.output_type.sellable_children()

    output_label = "Output Lot"
    #output_create_form = None
    output_formset = None
    outputs = pt.number_of_output_lots
    if outputs > 1:
        output_label = "Output Lots"
        #OutputFormSet = formset_factory(OutputLotCreationFormsetForm, extra=outputs)
        #output_formset = OutputFormSet(data=request.POST or None, prefix="output")
        #for form in output_formset.forms:
        #    form.fields['product'].choices = [(prod.id, prod.long_name) for prod in output_types]
    #else:
    #    output_create_form = OutputLotCreationForm(output_types, data=request.POST or None, prefix="output")

    OutputFormSet = formset_factory(OutputLotCreationFormsetForm, extra=outputs)
    output_formset = OutputFormSet(data=request.POST or None, prefix="output")
    for form in output_formset.forms:
        form.fields['product'].choices = [(prod.id, prod.long_name) for prod in output_types]

    process = None

    if request.method == "POST":
        if input_create_form:
            if input_create_form.is_valid():
                data = input_create_form.cleaned_data
                lot = input_create_form.save(commit=False)
                qty = data["planned"]
                process = Process(
                    process_type = pt,
                    process_date = weekstart)
                process.save()
                lot.inventory_date = weekstart
                lot.remaining = qty
                lot.save()
                issue = InventoryTransaction(
                    transaction_type = "Issue",
                    process = process,
                    inventory_item = lot,
                    transaction_date = weekstart,
                    quantity = qty)
                issue.save()

        elif input_select_form:
            if input_select_form.is_valid():
                data = input_select_form.cleaned_data
                lot_id = data['lot']
                lot = InventoryItem.objects.get(id=lot_id)
                qty = data["quantity"]
                process = Process(
                    process_type = pt,
                    process_date = weekstart)
                process.save()
                issue = InventoryTransaction(
                    transaction_type = "Issue",
                    process = process,
                    inventory_item = lot,
                    transaction_date = weekstart,
                    quantity = qty)
                issue.save()

        if process:
            if service_form:
                if service_form.is_valid():
                    tx = service_form.save(commit=False)
                    tx.process = process
                    tx.transaction_date = weekstart
                    tx.save()
            if service_formset:
                if service_formset.is_valid(): # todo: shd be selective, or not?
                    for service_form in service_formset.forms:
                        tx = service_form.save(commit=False)
                        tx.process = process
                        tx.transaction_date = weekstart
                        tx.save()
            if output_create_form:
                if output_create_form.is_valid():
                    data = output_create_form.cleaned_data
                    lot = output_create_form.save(commit=False)
                    qty = data["planned"]
                    lot.inventory_date = weekstart
                    lot.save()
                    tx = InventoryTransaction(
                        transaction_type = "Production",
                        process = process,
                        inventory_item = lot,
                        transaction_date = weekstart,
                        quantity = qty)
                    tx.save()
            if output_formset:
                for form in output_formset.forms:
                    if form.is_valid():
                        data = form.cleaned_data
                        lot = form.save(commit=False)
                        qty = data["planned"]
                        lot.inventory_date = weekstart
                        lot.save()
                        tx = InventoryTransaction(
                            transaction_type = "Production",
                            process = process,
                            inventory_item = lot,
                            transaction_date = weekstart,
                            quantity = qty)
                        tx.save()
                    #else:
                    #    print "output form is invalid:", form


            return HttpResponseRedirect('/%s/%s/'
               % ('process', process.id))

    return render_to_response('distribution/new_process.html', {
        'input_lot_qties': input_lot_qties,
        'input_select_form': input_select_form,
        'input_create_form': input_create_form,
        #'service_form': service_form,
        'service_formset': service_formset,
        'service_label': service_label,
        #'output_create_form': output_create_form,
        'output_formset': output_formset,
        'output_label': output_label,
        })  

@login_required
def edit_process(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    inputs = process.inputs()

    # todo: wip: how to edit a process?



def process(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    return render_to_response('distribution/process.html', {"process": process,})

def delete_process_confirmation(request, process_id):
    if request.method == "POST":
        process = get_object_or_404(Process, id=process_id)
        outputs = []
        outputs_with_lot = []
        for output in process.outputs():
            lot = output.inventory_item
            qty = output.quantity
            if lot.planned == qty:
                outputs_with_lot.append(output)
            else:
                outputs.append(output)
        inputs = []
        inputs_with_lot = []
        for inp in process.inputs():
            lot = inp.inventory_item
            qty = inp.quantity
            if lot.planned == qty:
                inputs_with_lot.append(inp)
            else:
                inputs.append(inp)
        return render_to_response('distribution/process_delete_confirmation.html', {
            "process": process,
            "outputs": outputs,
            "inputs": inputs,
            "outputs_with_lot": outputs_with_lot,
            "inputs_with_lot": inputs_with_lot,
            })

def delete_process(request, process_id):
    if request.method == "POST":
        process = get_object_or_404(Process, id=process_id)
        for output in process.outputs():
            lot = output.inventory_item
            qty = output.quantity
            output.delete()
            if lot.planned == qty:
                lot.delete()
        for inp in process.inputs():
            lot = inp.inventory_item
            qty = inp.quantity
            inp.delete()
            if lot.planned == qty:
                lot.delete()
        for service in process.services():
            service.delete() 
        process.delete()
     
        return HttpResponseRedirect(reverse("process_selection"))

