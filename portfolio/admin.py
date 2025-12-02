from decimal import Decimal
from django.contrib import admin
from . import models


@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'created_at')


@admin.register(models.Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_default', 'active', 'created_at')
    list_filter = ('active', 'is_default')


@admin.register(models.BrokerType)
class BrokerTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'display_name')


@admin.register(models.BrokerAccount)
class BrokerAccountAdmin(admin.ModelAdmin):
    list_display = ('display_name_or_ext', 'portfolio', 'broker_type', 'status', 'created_at')
    list_filter = ('broker_type', 'status')

    @admin.display(description="Account")
    def display_name_or_ext(self, obj: models.BrokerAccount):
        return obj.display_name or obj.external_account_id


@admin.register(models.BrokerAccountCredential)
class BrokerAccountCredentialAdmin(admin.ModelAdmin):
    list_display = ('broker_account', 'encrypted', 'created_at', 'updated_at')


@admin.register(models.Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'isin', 'asset_type', 'close_price', 'last_price', 'as_of', 'received_at')
    list_filter = ('asset_type',)
    search_fields = ('symbol', 'isin')


@admin.register(models.Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ('stock_symbol', 'broker_account', 'quantity', 'avg_price',
                    'currency', 'as_of', 'created_at')
    list_filter = ('broker_account', 'stock__asset_type', 'currency')
    search_fields = ('stock__symbol', 'broker_account__external_account_id')

    @admin.display(description="Symbol")
    def stock_symbol(self, obj: models.Holding):
        return obj.stock.symbol

    @admin.display(description="Asset type")
    def asset_type(self, obj: models.Holding):
        return obj.stock.asset_type


@admin.register(models.Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('broker_account', 'stock_symbol', 'trade_type',
                    'quantity', 'price', 'currency', 'trade_time')
    list_filter = ('broker_account', 'stock__asset_type', 'trade_type', 'currency')
    search_fields = ('stock__symbol', 'broker_account__external_account_id')

    @admin.display(description="Symbol")
    def stock_symbol(self, obj: models.Transaction):
        return obj.stock.symbol

    @admin.display(description="Asset type")
    def asset_type(self, obj: models.Transaction):
        return obj.stock.asset_type
