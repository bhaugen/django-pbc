from django.contrib import admin
from distribution.models import *
from distribution.forms import CustomerForm, DistributorForm, ProcessorForm, ProducerForm

class FoodNetworkAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'long_name', 'contact', 'customer_fee', 'producer_fee', 'charge', 'charge_name')

admin.site.register(FoodNetwork, FoodNetworkAdmin)


class ProducerAdmin(admin.ModelAdmin):
    form = ProducerForm
    list_display = ('short_name', 'member_id', 'long_name', 'contact', 'phone', 'delivers')
    
admin.site.register(Producer, ProducerAdmin)


class ProcessorAdmin(admin.ModelAdmin):
    form = ProcessorForm
    list_display = ('short_name', 'long_name', 'contact', 'phone')
    
admin.site.register(Processor, ProcessorAdmin)


class DistributorAdmin(admin.ModelAdmin):
    form = DistributorForm
    list_display = ('short_name', 'member_id', 'long_name', 'contact', 'phone')
    
admin.site.register(Distributor, DistributorAdmin)


class CustomerAdmin(admin.ModelAdmin):
    form = CustomerForm
    list_display = ('short_name', 'member_id', 'long_name', 'contact', 'phone', 'charge', 'apply_charge')
    
admin.site.register(Customer, CustomerAdmin)


class ProductAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'long_name', 'parent', 'price', 'fee_override', 'pay_producer', 'expiration_days', 'meat')
    list_filter = ['meat', 'parent']
    search_fields = ['short_name', 'long_name']
    
admin.site.register(Product, ProductAdmin)


class ProductPlanAdmin(admin.ModelAdmin):
    list_display = ('product', 'producer', 'from_date', 'to_date', 'quantity', 'distributor')
    list_filter = ['producer', 'product']
    date_hierarchy = 'from_date'
    
admin.site.register(ProductPlan, ProductPlanAdmin)


class ProcessingInline(admin.TabularInline):
    model = Processing


class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'producer', 'custodian', 'inventory_date', 'expiration_date', 'planned', 'remaining', 'received', 'onhand', 'notes')
    # Todo: how to sort for admin?
    #ordering = ('product',)
    list_filter = ['producer', 'product']
    search_fields = ['producer__short_name, product__short_name']
    date_hierarchy = 'inventory_date'
    inlines = [ ProcessingInline, ]
    
admin.site.register(InventoryItem, InventoryItemAdmin)


class ProcessingAdmin(admin.ModelAdmin):
    list_display = ('inventory_item', 'process_date', 'processor', 'cost', 'payment')
    list_filter = ['processor', 'inventory_item']
    date_hierarchy = 'process_date'
  
admin.site.register(Processing, ProcessingAdmin)


class OrderItemInline(admin.TabularInline):
    model = OrderItem

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_date', 'customer', 'distributor', 'transportation_fee', 'paid', 'transportation_payment')
    ordering = ('order_date',)
    list_filter = ['customer', 'paid']
    date_hierarchy = 'order_date'
    inlines = [ OrderItemInline, ]
  
admin.site.register(Order, OrderAdmin)


#class OrderItemAdmin(admin.ModelAdmin):
#    list_display = ('order', 'product', 'quantity', 'unit_price', 'extended_price')
  
#admin.site.register(OrderItem, OrderItemAdmin)


class ProcessTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'input_type', 'use_existing_input_lot', 'number_of_processing_steps', 'output_type', 'number_of_output_lots', 'notes')
  
admin.site.register(ProcessType, ProcessTypeAdmin)

class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
  
admin.site.register(ServiceType, ServiceTypeAdmin)

class ProcessAdmin(admin.ModelAdmin):
    list_display = ('process_type', 'process_date')
  
admin.site.register(Process, ProcessAdmin)


class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'transaction_date', 'order_item', 'process', 'product', 'inventory_item', 'quantity', 'notes', 'payment')
    #both ordering statements below caused mysterious error in admin:
    #no such column: orders_orderitem.order
    #ordering = ('order_item', 'inventory_item')
    #verbose_name_plural = 'Inventory Transactions'
    #ordering = ('inventory_item')
    #list_select_related = True
    list_filter = ['transaction_type', 'inventory_item']
    #search_fields = ['product.short_name']
    search_fields = ['inventory_item__producer__short_name', 'order_item__order__customer__short_name', 'inventory_item__product__short_name']
    date_hierarchy = 'transaction_date'
  
admin.site.register(InventoryTransaction, InventoryTransactionAdmin)

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_date', 'paid_to', 'amount', 'reference')
  
admin.site.register(Payment, PaymentAdmin)


class ServiceTransactionAdmin(admin.ModelAdmin):
    list_display = ('service_type', 'process', 'processor', 'transaction_date', 'cost', 'payment')
  
admin.site.register(ServiceTransaction, ServiceTransactionAdmin)

