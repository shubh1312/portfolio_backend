from django.contrib import admin
from . import models

@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email','name','created_at')

@admin.register(models.Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('name','user','is_default','active','created_at')
    list_filter = ('active','is_default')

@admin.register(models.BrokerType)
class BrokerTypeAdmin(admin.ModelAdmin):
    list_display = ('code','display_name')

@admin.register(models.BrokerAccount)
class BrokerAccountAdmin(admin.ModelAdmin):
    list_display = ('display_name','portfolio','broker_type','external_account_id','status','created_at')
    list_filter = ('status','broker_type')

@admin.register(models.BrokerAccountCredential)
class BrokerAccountCredentialAdmin(admin.ModelAdmin):
    list_display = ('broker_account', 'encrypted','updated_at')

@admin.register(models.Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ('symbol','broker_account','quantity','avg_price','as_of','market_value')
    list_filter = ('asset_type','currency')

@admin.register(models.Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('trade_type','symbol','broker_account','quantity','price','trade_time')
    list_filter = ('trade_type',)
