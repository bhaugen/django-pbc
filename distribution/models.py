from django.db import models
import datetime
from decimal import *
from django.db.models import Q
from django.contrib.localflavor.us.models import PhoneNumberField
from django.contrib.contenttypes.models import ContentType
from django.db.models.query import QuerySet
import itertools


def customer_fee():
    answer = 0
    try:
        answer = FoodNetwork.objects.get(pk=1).customer_fee
    except FoodNetwork.DoesNotExist:
        answer = 0
    return answer

def producer_fee():
    answer = 0
    try:
        answer = FoodNetwork.objects.get(pk=1).producer_fee
    except FoodNetwork.DoesNotExist:
        answer = 0
    return answer

def default_charge():
    charge = 0
    try:
        charge = FoodNetwork.objects.get(pk=1).charge
    except FoodNetwork.DoesNotExist:
        charge = 0
    return charge

def current_week():
    answer = datetime.date.today()
    try:
        answer = FoodNetwork.objects.get(pk=1).current_week
    except FoodNetwork.DoesNotExist:
        answer = datetime.date.today()
    return answer

def charge_name():
    try:
        answer = FoodNetwork.objects.get(pk=1).charge_name
    except:
        answer = 'Delivery Charge'
    return answer

def terms():
    return FoodNetwork.objects.get(pk=1).terms


class ProductAndProducers(object):
     def __init__(self, product, qty, price, producers):
         self.product = product
         self.qty = qty
         self.price = price
         self.producers = producers

         
class ProductAndLots(object):
     def __init__(self, product, qty, price, lots):
         self.product = product
         self.qty = qty
         self.price = price
         self.lots = lots


class ProductQuantity(object):
     def __init__(self, product, qty):
         self.product = product
         self.qty = qty


class PickupCustodian(object):
     def __init__(self, custodian, address, products):
         self.custodian = custodian
         self.address = address
         self.products = products
 
         
class PickupDistributor(object):
     def __init__(self, distributor, email, custodians):
         self.distributor = distributor
         self.email = email
         self.custodians = custodians
         
         
class OrderToBeDelivered(object):
     def __init__(self, customer, address, products):
         self.customer = customer
         self.address = address
         self.products = products
         
class DeliveryDistributor(object):
     def __init__(self, distributor, email, customers):
         self.distributor = distributor
         self.email = email
         self.customers = customers
         

class FoodNetwork(models.Model):
    short_name = models.CharField(max_length=32, unique=True)
    long_name = models.CharField(max_length=64, blank=True)
    contact = models.CharField(max_length=64, blank=True)
    phone = PhoneNumberField(blank=True)
    address = models.CharField(max_length=96, blank=True, 
            help_text='Enter commas only where you want to split address lines for formatting.')
    email_address = models.EmailField(max_length=96, blank=True, null=True)
    billing_contact = models.CharField(max_length=64, blank=True)
    billing_phone = PhoneNumberField(blank=True, null=True)
    billing_address = models.CharField(max_length=96, blank=True, null=True, 
            help_text='Enter commas only where you want to split address lines for formatting.')
    billing_email_address = models.EmailField(max_length=96, blank=True, null=True)
    terms = models.IntegerField(blank=True, null=True,
        help_text='Net number of days for invoices')
    customer_fee = models.DecimalField(max_digits=3, decimal_places=2, 
        help_text='Fee is a decimal fraction, not a percentage - for example, .05 instead of 5%')
    producer_fee = models.DecimalField(max_digits=3, decimal_places=2, 
        help_text='Fee is a decimal fraction, not a percentage - for example, .05 instead of 5%')    
    charge = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True,
        help_text='Charge will be added to all orders unless overridden on the Customer')
    charge_name = models.CharField(max_length=32, blank=True, default='Delivery charge')
    current_week = models.DateField(default=datetime.date.today, 
        help_text='Current week for operations availability and orders')

    def __unicode__(self):
        return self.short_name
    def formatted_billing_address(self):
        return self.billing_address.split(',')
    
    @property
    def email(self):
        return self.email_address

    class Meta:
        ordering = ('short_name',)

    
    def fresh_list(self, thisdate = None):
        if not thisdate:
            thisdate = current_week()
        prods = Product.objects.all()
        item_list = []
        for prod in prods:
            #item_chain = prod.avail_items(thisdate)
            #items = []
            #for item in item_chain:
            #    items.append(item)
            items = prod.avail_items(thisdate)
            avail_qty = sum(item.avail_qty() for item in items)
            if avail_qty > 0:
                price = prod.price.quantize(Decimal('.01'), rounding=ROUND_UP)
                #producers = []
                #for item in items:
                #    producer = item.producer.long_name
                #    if not producer in producers:
                #        producers.append(producer)
                #item_list.append(ProductAndProducers(prod.long_name, avail_qty, price, producers))
                item_list.append(ProductAndLots(prod.long_name, avail_qty, price, items))
        return item_list
    
    def pickup_list(self, thisdate = None):
        if not thisdate:
            thisdate = current_week()
        prods = Product.objects.all()
        distributors = {}
        network = self
        for prod in prods:
            items = prod.ready_items(thisdate)            
            for item in items:
                distributor = item.distributor()
                if not distributor:
                    distributor = network
                if item.custodian:
                    custodian = item.custodian.long_name
                    address = item.custodian.address
                else:
                    custodian = item.producer.long_name
                    address = item.producer.address
                # eliminate items to be delivered by producer or custodian
                if not distributor.id == item.producer.id:
                    if not distributor in distributors:
                        if distributor.email_address:
                            email = distributor.email_address
                        else:
                            email = network.email_address
                        distributors[distributor] = PickupDistributor(distributor.long_name, email, {})
                    this_distributor = distributors[distributor]
                    if not custodian in this_distributor.custodians:
                        this_distributor.custodians[custodian] = PickupCustodian(custodian, address, [])
                    this_distributor.custodians[custodian].products.append(ProductQuantity(item.pickup_label(), item.planned))
        return distributors
        
    def delivery_list(self, thisdate = None):
        if not thisdate:
            thisdate = current_week()
        weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
        weekend = weekstart + datetime.timedelta(days=5)
        ois = OrderItem.objects.filter(order__order_date__range=(weekstart, weekend))
        
        #customers = {}
        #product_producers = {}
        
        distributors = {}
        network = self
        for oi in ois:
            customer = oi.order.customer.long_name
            product = oi.product.id
            txs = oi.inventorytransaction_set.all()
            # what if no txs, i.e. no lot assignments?
            lots = []
            for tx in txs:
                lots.append(tx.inventory_item)
            for lot in lots:
                distributor = lot.distributor()
                if not distributor:
                    distributor = network
                if not distributor in distributors:
                    if distributor.email_address:
                        email = distributor.email_address
                    else:
                        email = network.email_address
                    distributors[distributor] = DeliveryDistributor(distributor.long_name, email, {})
                this_distributor = distributors[distributor]
                
                if not customer in this_distributor.customers:
                    this_distributor.customers[customer] = OrderToBeDelivered(customer, oi.order.customer.address, {})
                otbd = this_distributor.customers[customer]
                if not product in otbd.products:
                    otbd.products[product] = ProductAndLots(oi.product.long_name, oi.quantity, oi.product.price,[])
                otbd.products[product].lots.append(lot)
        for dist in distributors:
            dd = distributors[dist]
            for cust in dd.customers:
                otbd = dd.customers[cust]
                otbd.products = otbd.products.values()
        return distributors
                
        #    customer = item.order.customer.long_name
        #    product = item.product.id
        #    if not product in product_producers:
        #            product_producers[product] = item.product.avail_producers(thisdate)
        #    producers = product_producers[product]             
        #    if not customer in customers:
        #        customers[customer] = OrderToBeDelivered(customer, item.order.customer.address, [])
        #    customers[customer].products.append(ProductAndProducers(item.product.long_name, item.quantity, item.product.price, producers))
        #item_list = customers.values()
        #item_list.sort(lambda x, y: cmp(x.customer, y.customer))   
        #return item_list
    
    def all_avail_items(self, thisdate=None):
        if not thisdate:
            thisdate = current_week()
        weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
        expired_date = weekstart + datetime.timedelta(days=5)
        items = InventoryItem.objects.filter(
            inventory_date__lte=expired_date,
            expiration_date__gte=expired_date)
        items = items.filter(Q(remaining__gt=0) | Q(onhand__gt=0))
        return items
    
    def all_active_items(self, thisdate = None):
        if not thisdate:
            thisdate = current_week()
        weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
        weekend = weekstart + datetime.timedelta(days=5)
        return InventoryItem.objects.filter(
            inventory_date__lte=weekend,
            expiration_date__gte=weekend)
          

# inheritance approach based on
# http://www.djangosnippets.org/snippets/1034/
class SubclassingQuerySet(QuerySet):
    def __getitem__(self, k):
        result = super(SubclassingQuerySet, self).__getitem__(k)
        if isinstance(result, models.Model) :
            return result.as_leaf_class()
        else :
            return result
    def __iter__(self):
        for item in super(SubclassingQuerySet, self).__iter__():
            yield item.as_leaf_class()

    
class PartyManager(models.Manager):
    
    def get_query_set(self):
        return SubclassingQuerySet(self.model)
    
    def planned_producers(self):
        producers = []
        all_prods = Party.subclass_objects.all()
        for prod in all_prods:
            if prod.product_plans.all().count():
                producers.append(prod)
        return producers

    
class Party(models.Model):
    short_name = models.CharField(max_length=32, unique=True)
    long_name = models.CharField(max_length=64, blank=True)
    member_id = models.CharField(max_length=12, blank=True)
    contact = models.CharField(max_length=64, blank=True)
    phone = PhoneNumberField(blank=True)
    cell = PhoneNumberField(blank=True)
    fax = PhoneNumberField(blank=True)
    address = models.CharField(max_length=96, blank=True)
    email_address = models.EmailField(max_length=96, blank=True, null=True)
    content_type = models.ForeignKey(ContentType,editable=False,null=True)
    delivers = models.BooleanField(default=False,
        help_text='Delivers products directly to customers?')
    
    objects = models.Manager()
    subclass_objects = PartyManager()

    def __unicode__(self):
        return self.short_name
    
    @property
    def email(self):
        return self.email_address

    class Meta:
        ordering = ('short_name',)
        
    def as_leaf_class(self):
        if self.content_type:
            content_type = self.content_type
            model = content_type.model_class()
            if (model == Party):
                return self
            return model.objects.get(id=self.id)
        else:
            return self
        
    def save(self, force_insert=False, force_update=False):
        if(not self.content_type):
            self.content_type = ContentType.objects.get_for_model(self.__class__)
        self.save_base(force_insert, force_update)
        
    def formatted_address(self):
        return self.address.split(',')


class ProducerManager(models.Manager):

    def planned_producers(self):
        producers = []
        all_prods = Producer.objects.all()
        for prod in all_prods:
            if prod.product_plans.all().count():
                producers.append(prod)
        return producers


class Producer(Party):
    pass


class Processor(Party):
    pass


class Distributor(Party):
    pass


class Customer(models.Model):
    short_name = models.CharField(max_length=32, unique=True)
    long_name = models.CharField(max_length=64, blank=True)
    member_id = models.CharField(max_length=12, blank=True)
    contact = models.CharField(max_length=64, blank=True)
    phone = PhoneNumberField(blank=True)
    cell = PhoneNumberField(blank=True)
    fax = PhoneNumberField(blank=True)
    address = models.CharField(max_length=96, blank=True, 
            help_text='Enter commas only where you want to split address lines for formatting.')
    email_address = models.EmailField(max_length=96, blank=True, null=True)
    charge = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True,
        help_text='Any value but 0 in this field will override the default charge from the Food Network')
    apply_charge = models.BooleanField(default=True,
        help_text='Add the extra charge to all orders for this customer, or not?')

    def __unicode__(self):
        return self.short_name
    def formatted_address(self):
        return self.address.split(',')
    def order_charge(self):
        answer = Decimal(0)
        if self.apply_charge:
            if self.charge:
                answer = self.charge
            else:
                answer = default_charge()
        return answer
    
    @property
    def email(self):
        return self.email_address

    class Meta:
        ordering = ('short_name',)

# based on dfs from threaded_comments
def nested_objects(node, all_nodes):
     to_return = [node,]
     for subnode in all_nodes:
         if subnode.parent and subnode.parent.id == node.id:
             to_return.extend([nested_objects(subnode, all_nodes),])
     return to_return

def flattened_children(node, all_nodes, to_return):
     to_return.append(node)
     for subnode in all_nodes:
         if subnode.parent and subnode.parent.id == node.id:
             flattened_children(subnode, all_nodes, to_return)
     return to_return


class Product(models.Model):
    parent = models.ForeignKey('self', blank=True, null=True, related_name='children',
        limit_choices_to = {'is_parent': True})
    short_name = models.CharField(max_length=32, unique=True)
    long_name = models.CharField(max_length=64)
    sellable = models.BooleanField(default=True,
        help_text='Should this product appear in Inventory Update?')
    is_parent = models.BooleanField(default=False,
        help_text='Should this product appear in parent selections?')
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal(0))
    fee_override = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True, 
        help_text='Enter override as a decimal fraction, not a percentage - for example, .05 instead of 5%. Note: you cannot override to zero here, only on Order Items.')
    pay_producer = models.BooleanField(default=True,
        help_text='Does the Food Network pay the producer for deliveries of this product, or not?')
    expiration_days = models.IntegerField(default=6,
        help_text='Inventory Items (Lots) of this product will expire in this many days.')
    meat = models.BooleanField(default=False,
        help_text='Is this a meat product?')

    def __unicode__(self):
        return self.long_name
    
    def avail_items(self, thisdate):
        weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
        weekend = weekstart + datetime.timedelta(days=5)
        expired_date = weekstart + datetime.timedelta(days=5)
        items = InventoryItem.objects.filter(product=self, 
            inventory_date__lte=weekend,
            expiration_date__gte=expired_date)
        items = items.filter(Q(remaining__gt=0) | Q(onhand__gt=0))
        return items
    
    def current_items(self, thisdate):
        weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
        weekend = weekstart + datetime.timedelta(days=5)
        expired_date = weekstart + datetime.timedelta(days=5)
        items = InventoryItem.objects.filter(product=self, 
            inventory_date__lte=weekend,
            expiration_date__gte=expired_date)
        #items = items.filter(Q(remaining__gt=0) | Q(onhand__gt=0))
        return items
    
    def ready_items(self, thisdate):
        weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
        weekend = weekstart + datetime.timedelta(days=5)
        items = InventoryItem.objects.filter(product=self, 
            inventory_date__range=(weekstart, weekend),
            planned__gt=0, onhand__exact=0,  received__exact=0)
        return items
    
    def total_avail(self, thisdate):
        return sum(item.avail_qty() for item in self.avail_items(thisdate))
    
    def avail_producers(self, thisdate):
        producers = []
        myavails = self.avail_items(thisdate)
        for av in myavails:
            producers.append(av.producer.short_name)
        producers = list(set(producers))
        producer_string = ", ".join(producers)
        return producer_string
    
    def active_producers(self, thisdate):
        producers = []
        myavails = self.avail_items(thisdate)
        for av in myavails:
            producers.append(av.producer.short_name)
        deliveries = self.deliveries_this_week(thisdate)
        for delivery in deliveries:
            producers.append(delivery.inventory_item.producer.short_name)
        producers = list(set(producers))
        producer_string = ", ".join(producers)
        return producer_string
    
    def total_ordered(self, thisdate):
        weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
        weekend = weekstart + datetime.timedelta(days=5)
        myorders = OrderItem.objects.filter(product=self, order__order_date__range=(weekstart, weekend))
        return sum(order.quantity for order in myorders)
    
    def deliveries_this_week(self, thisdate):
        weekstart = thisdate - datetime.timedelta(days=datetime.date.weekday(thisdate))
        weekend = weekstart + datetime.timedelta(days=5)
        deliveries = InventoryTransaction.objects.filter(transaction_type="Delivery")
        return deliveries.filter(
            order_item__product=self, transaction_date__range=(weekstart, weekend))
    
    def total_delivered(self, thisdate):
        deliveries = self.deliveries_this_week(thisdate)
        return sum(delivery.quantity for delivery in deliveries)
    
    def decide_fee(self):
        prod_fee = self.fee_override
        if prod_fee:
            my_fee = prod_fee
        else:
            my_fee = customer_fee()
        return my_fee
    
    def parent_string(self):
        answer = ''
        prod = self
        parents = []
        while not prod.parent is None:
            parents.append(prod.parent.short_name)
            prod = prod.parent
        if len(parents) > 0:
            parents.reverse()
            answer = ', '.join(parents)
        return answer

    def sellable_children(self):
        kids = flattened_children(self, Product.objects.all(), [])
        sellables = []
        for kid in kids:
            if kid.sellable:
                sellables.append(kid)
        return sellables

    class Meta:
        ordering = ('short_name',)


class ProductPlan(models.Model):
    producer = models.ForeignKey(Party, related_name="product_plans") 
    product = models.ForeignKey(Product, limit_choices_to = {'sellable': True})
    from_date = models.DateField()
    to_date = models.DateField()
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    distributor = models.ForeignKey(Party, related_name="plan_distributors", blank=True, null=True)
    
    def __unicode__(self):
        return " ".join([
            self.producer.short_name,
            self.product.short_name,
            self.from_date.strftime('%Y-%m-%d'),
            self.from_date.strftime('%Y-%m-%d'),
            str(self.quantity)])
        
    class Meta:
        ordering = ('product', 'producer', 'from_date')
        

class InventoryItem(models.Model):
    producer = models.ForeignKey(Party, related_name="inventory_items") 
    custodian = models.ForeignKey(Party, blank=True, null=True, related_name="custody_items")
    product = models.ForeignKey(Product, limit_choices_to = {'sellable': True})
    inventory_date = models.DateField()
    expiration_date = models.DateField()
    planned = models.DecimalField("Ready", max_digits=8, decimal_places=2, default=Decimal('0'))
    remaining = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'),
        help_text='If you change Ready here, you most likely should also change Remaining. The Avail Update page changes Remaining automatically when you enter Ready, but this Admin form does not.')
    received = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    onhand = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'),
        help_text='If you change Received here, you most likely should also change Onhand. The Avail Update page changes Onhand automatically when you enter Received, but this Admin form does not.')
    notes = models.CharField(max_length=64, blank=True)
    
    class Meta:
        ordering = ('product', 'producer', 'inventory_date')

    def __unicode__(self):
        return " ".join([
            self.producer.short_name,
            self.product.short_name,
            self.inventory_date.strftime('%Y-%m-%d')])

    def lot_id(self):
        return " ".join([
            self.producer.member_id,
            self.producer.short_name,
            self.product.long_name,
            self.inventory_date.strftime('%Y-%m-%d')])        
    
    def avail_qty(self):
        if self.onhand:
            return self.onhand
        else:
            return self.remaining
        
    def ordered_qty(self):
        return self.delivered_qty()
        
    def delivered_qty(self):
        return sum(delivery.quantity for delivery in self.inventorytransaction_set.all())
        
    def delivery_label(self):
        return " ".join([
            self.producer.short_name,
            'qty', str(self.avail_qty()),
            'at', self.inventory_date.strftime('%m-%d')])
            
    def pickup_label(self):
        return self.lot_id()
        
    def distributor(self):
        plans = ProductPlan.objects.filter(
            product = self.product,
            producer = self.producer,
            from_date__lte=self.inventory_date,
            to_date__gte=self.inventory_date)
        if plans:
            return plans[0].distributor
        else:
            return None
        
    def customers(self):
        buyers = []
        deliveries = self.inventorytransaction_set.all()
        for delivery in deliveries:
            if delivery.order_item:
                buyers.append(delivery.order_item.order.customer.short_name)
        buyers = list(set(buyers))
        buyer_string = ", ".join(buyers)
        return buyer_string
            
    def update_from_transaction(self, qty): 
        """ update remaining or onhand

        Onhand trumps remaining.
        Qty could be positive or negative.
        """

        if self.onhand + self.received > Decimal('0'):
            # to deal with Django bug, fixed in 1.1
            onhand = Decimal(self.onhand)
            onhand += qty
            self.onhand = max([Decimal("0"), onhand])
            self.save()
        else:
            # to deal with Django bug, fixed in 1.1
            remaining = Decimal(self.remaining)
            print self, "remaining:", remaining, "qty:", qty
            remaining += qty
            self.remaining = max([Decimal("0"), remaining])
            self.save()
                
    def save(self, force_insert=False, force_update=False):
        if not self.pk:
            self.expiration_date = self.inventory_date + datetime.timedelta(days=self.product.expiration_days)
        super(InventoryItem, self).save(force_insert, force_update)
        

class Payment(models.Model):
    paid_to = models.ForeignKey(Party) 
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    reference = models.CharField(max_length=64, blank=True)

    def __unicode__(self):
        amount_string = '$' + str(self.amount)
        return ' '.join([
            self.payment_date.strftime('%Y-%m-%d'),
            self.paid_to.short_name,
            amount_string])

    class Meta:
        ordering = ('payment_date',)


class Order(models.Model):
    customer = models.ForeignKey(Customer) 
    order_date = models.DateField()
    distributor = models.ForeignKey(Party, blank=True, null=True, related_name="orders")
    transportation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    paid = models.BooleanField(default=False, verbose_name="Order paid")
    transportation_payment = models.ForeignKey(Payment, blank=True, null=True)

    def __unicode__(self):
        return ' '.join([self.order_date.strftime('%Y-%m-%d'), self.customer.short_name])
    
    def delete(self):
        deliveries = InventoryTransaction.objects.filter(order_item__order=self) 
        for delivery in deliveries:
            delivery.delete()
        super(Order, self).delete()
    
    def charge_name(self):
        return charge_name()
    
    def charge(self):
        return self.customer.order_charge()
    
    def total_price(self):
        items = self.orderitem_set.all()
        total = self.transportation_fee
        for item in items:
            total += item.extended_price()
            total += item.processing_cost()
        return total.quantize(Decimal('.01'), rounding=ROUND_UP)
    
    def coop_fee(self):
        total = self.total_price()
        fee = customer_fee()
        answer = total * fee
        return answer.quantize(Decimal('.01'), rounding=ROUND_UP)
    
    def grand_total(self):
        return self.total_price() + self.coop_fee()
    
    def payment_due_date(self):
        term_days = terms()
        return self.order_date + datetime.timedelta(days=term_days)
    
    def display_transportation_fee(self):
        return self.transportation_fee.quantize(Decimal('.01'), rounding=ROUND_UP)
    
    def coop_fee_label(self):
        fee = int(customer_fee() * 100)
        return "".join([str(fee), "% Co-op Fee"])    
        

    class Meta:
        ordering = ('order_date', 'customer')


class OrderItem(models.Model):
    order = models.ForeignKey(Order)
    product = models.ForeignKey(Product)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    fee = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0'),
        help_text='Fee is a decimal fraction, not a percentage - for example, .05 instead of 5%')
    notes = models.CharField(max_length=64, blank=True)

    def __unicode__(self):
        return ' '.join([
            str(self.order),
            self.product.short_name,
            str(self.quantity)])
    
    def delete(self):
        deliveries = self.inventorytransaction_set.all()
        for delivery in deliveries:
            delivery.delete()
        super(OrderItem, self).delete()
    
    def total_avail(self):
        return self.product.total_avail(self.order.order_date)
    
    def total_ordered(self):
        return self.product.total_ordered(self.order.order_date)
    
    def producers(self):
        txs = self.inventorytransaction_set.all()
        producers = []
        for tx in txs:
            producers.append(tx.inventory_item.producer.short_name)
        return ', '.join(list(set(producers)))
    
    def processes(self):
        processes = []
        try:
            deliveries = self.inventorytransaction_set.all()
            for delivery in deliveries:
                processes.append(delivery.inventory_item.processing)
        except:
            pass
        return processes
    
    def processing_cost(self):
        cost = Decimal(0)
        for delivery in self.inventorytransaction_set.all():
            cost += delivery.processing_cost()
        return cost.quantize(Decimal('.01'))
    
    def processors(self):
        procs = []
        for process in self.processes():
            procs.append(process.processor.short_name)
        procs = list(set(procs))
        return ", ".join(procs)
    
    def distributor(self):
        order_date = self.order.order_date
        plans = ProductPlan.objects.filter(
            product = self.product,
            producer = self.producer,
            from_date__lte=order_date,
            to_date__gte=order_date)
        if plans:
            return plans[0].distributor
        else:
            return None
    
    def extended_price(self):
        answer = self.quantity * self.unit_price
        #if self.processing():
        #    answer += self.processing().cost
        return answer.quantize(Decimal('.01'), rounding=ROUND_UP)
    
    def lot(self):
        # this is a hack
        # PBC's order_by_lot means one delivery InventoryTransaction
        # and thus one InventoryItem per OrderItem
        deliveries = self.inventorytransaction_set.all()
        if deliveries.count():
            delivery = deliveries[0]
            item = delivery.inventory_item
            return item
        else:
            return None
        
    def producer_fee(self):
        return producer_fee()
    
    def extended_producer_fee(self):
        answer = self.quantity * self.unit_price * producer_fee()
        return answer.quantize(Decimal('.01'), rounding=ROUND_UP)
    
    def customer_fee(self):
        return customer_fee()

    class Meta:
        ordering = ('order', 'product',)



class Processing(models.Model):
    inventory_item = models.OneToOneField(InventoryItem, related_name='processing')
    processor = models.ForeignKey(Party)
    process_date = models.DateField()
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    payment = models.ForeignKey(Payment, blank=True, null=True)
    
    class Meta:
        ordering = ('-process_date',)
        verbose_name_plural = "Processing"
        
    def formatted_cost(self):
        return self.cost.quantize(Decimal('.01'))
    
    def inventory_transaction(self):
        #todo: this is a hack based on PBC rule that each lot of meat is indivisible,
        # that is, will have only one transaction
        # and processings with no inventory_transaction have already been filtered out
        try:
            return self.inventory_item.inventorytransaction_set.all()[0]
        except:
            return None
    
    def save(self, force_insert=False, force_update=False):
        if not self.pk:
            self.process_date = self.inventory_item.inventory_date
        super(Processing, self).save(force_insert, force_update)

class ServiceType(models.Model):
    name = models.CharField(max_length=64)

    def __unicode__(self):
        return self.name


class ProcessType(models.Model):
    name = models.CharField(max_length=64)
    input_type = models.ForeignKey(Product, related_name='input_types')
    use_existing_input_lot = models.BooleanField(default=True)
    number_of_processing_steps = models.IntegerField(default=1)
    output_type = models.ForeignKey(Product, related_name='output_types')
    number_of_output_lots = models.IntegerField(default=1)
    notes = models.TextField(blank=True)

    def __unicode__(self):
        return self.name

class Process(models.Model):
    process_type = models.ForeignKey(ProcessType)
    process_date = models.DateField()
    notes = models.TextField(blank=True)

    def __unicode__(self):
        return " ".join([
            self.process_type.name,
            self.input_lot_id()
            #self.process_date.strftime('%Y-%m-%d')
            ])


    def inputs(self):
        return self.inventory_transactions.filter(transaction_type="Issue")

    def outputs(self):
        return self.inventory_transactions.filter(transaction_type="Production")

    def services(self):
        return self.service_transactions.all()

    def input_lot_id(self):
        inputs = self.inventory_transactions.filter(transaction_type="Issue")
        try:
            return inputs[0].inventory_item.lot_id()
        except:
            return ""

    def output_lot_ids(self):
        answer = ""
        outputs = self.inventory_transactions.filter(transaction_type="Production")
        lot_ids = []
        for output in outputs:
            lot_ids.append(output.inventory_item.lot_id())
        answer = ", ".join(lot_ids)
        return answer

    def next_processes(self):
        processes = []
        for output in self.outputs():
            lot = output.inventory_item
            for issue in lot.inventorytransaction_set.filter(transaction_type="Issue"):
                if issue.process:
                    processes.append(issue.process)
        return processes

    def previous_processes(self):
        processes = []
        for inp in self.inputs():
            lot = inp.inventory_item
            for tx in lot.inventorytransaction_set.filter(transaction_type="Production"):
                if tx.process:
                    processes.append(tx.process)
        return processes 

    def previous_process(self):       
        # for PBC now, processes will have one or None previous_processes
        processes = self.previous_processes()
        if processes:
            return processes[0]
        else:
            return None

    def is_deletable(self):
        if self.next_processes():
            return False
        else:
            return True 


TX_CHOICES = (
    ('Receipt', 'Receipt'),         # inventory was received from outside the system
    ('Delivery', 'Delivery'),       # inventory was delivered to a customer
    ('Transfer', 'Transfer'),       # combination delivery and receipt inside the system
    ('Issue', 'Issue'),             # a process consumed inventory
    ('Production', 'Production'),   # a process created inventory
    ('Damage', 'Damage'),           # inventory was damaged and must be paid for
    ('Reject', 'Reject'),           # inventory was rejected by a customer and does not need to be paid for
)

class InventoryTransaction(models.Model):
    inventory_item = models.ForeignKey(InventoryItem)
    process = models.ForeignKey(Process, blank=True, null=True, related_name='inventory_transactions')
    transaction_type = models.CharField(max_length=10, choices=TX_CHOICES, default='Delivery')
    transaction_date = models.DateField()
    order_item = models.ForeignKey(OrderItem, blank=True, null=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    pay_producer = models.BooleanField(default=True)
    notes = models.CharField(max_length=64, blank=True)
    payment = models.ForeignKey(Payment, blank=True, null=True)

    def __unicode__(self):
        if self.order_item:
            label = ' '.join(['Order Item:', str(self.order_item)])
        else:
            label = ' '.join(['Type:', self.transaction_type])
        return " ".join([
            label, 
            'Inventory Item:', str(self.inventory_item), 
            'Qty:', str(self.quantity)])
        
    def save(self, force_insert=False, force_update=False):
        initial_qty = Decimal("0")
        if self.pk:
            prev_state = InventoryTransaction.objects.get(pk=self.pk)
            initial_qty = prev_state.quantity
        super(InventoryTransaction, self).save(force_insert, force_update)
        qty_delta = self.quantity - initial_qty
        if self.transaction_type=="Receipt" or self.transaction_type=="Production":
            self.inventory_item.update_from_transaction(qty_delta)
        else:
            self.inventory_item.update_from_transaction(-qty_delta)
        
    def delete(self):
        if self.transaction_type=="Receipt" or self.transaction_type=="Production":
            self.inventory_item.update_from_transaction(-self.quantity)
        else:
            self.inventory_item.update_from_transaction(self.quantity)
        super(InventoryTransaction, self).delete()
        
    def order_customer(self):
        return self.order_item.order.customer
    
    def product(self):
        return self.inventory_item.product
    
    def producer(self):
        return self.inventory_item.producer
    
    def inventory_date(self):
        return self.inventory_item.inventory_date
    
    def due_to_producer(self):
        if self.transaction_type is 'Reject':
            return Decimal(0)
        if not self.inventory_item.product.pay_producer:
            return Decimal(0)
        if not self.pay_producer:
            return Decimal(0)
        
        fee = producer_fee()
        unit_price = self.inventory_item.product.price
        return (unit_price * self.quantity * (1 - fee)).quantize(Decimal('.01'), rounding=ROUND_UP)
    
    def processing_cost(self):
        cost = Decimal(0)
        item = self.inventory_item
        try:
            processing = item.processing
        except Processing.DoesNotExist:
            processing = None
        if processing:
            cost = processing.cost
            item_qty = item.received if item.received else item.planned
            if self.quantity < item_qty:
                cost = (cost * self.quantity / item_qty).quantize(Decimal('.01'), rounding=ROUND_UP)
        return cost

    class Meta:
        ordering = ('-transaction_date',)


class ServiceTransaction(models.Model):
    service_type = models.ForeignKey(ServiceType)
    process = models.ForeignKey(Process, related_name='service_transactions')
    processor = models.ForeignKey(Party)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    transaction_date = models.DateField()
    notes = models.CharField(max_length=64, blank=True)
    payment = models.ForeignKey(Payment, blank=True, null=True)

    def __unicode__(self):
        return " ".join([
            self.service_type.name,
            self.processor.long_name,
            ])

