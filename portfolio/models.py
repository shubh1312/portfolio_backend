from django.db import models
from django.utils import timezone


class User(models.Model):
    email = models.TextField(unique=True)
    name = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name or self.email}"


class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios')
    name = models.TextField()
    description = models.TextField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.user})"


class BrokerType(models.Model):
    code = models.TextField(unique=True)
    display_name = models.TextField()

    def __str__(self):
        return self.display_name


class BrokerAccount(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='broker_accounts')
    broker_type = models.ForeignKey(BrokerType, on_delete=models.RESTRICT, related_name='broker_accounts')
    external_account_id = models.TextField()
    display_name = models.TextField(null=True, blank=True)
    status = models.TextField(default='active')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['broker_type', 'external_account_id'],
                name='uniq_broker_account_per_broker_type',
            )
        ]

    def __str__(self):
        return f"{self.display_name or self.external_account_id} - {self.broker_type}"


class BrokerAccountCredential(models.Model):
    broker_account = models.OneToOneField(
        BrokerAccount,
        on_delete=models.CASCADE,
        related_name='credential',
    )
    credentials = models.JSONField()
    encrypted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Credentials for {self.broker_account}"


class Stock(models.Model):
    """
    Represents a stock/instrument + its latest known price snapshot.
    Matches the suggested `stock_prices` table.
    """
    symbol = models.CharField(max_length=20)          # e.g. INFY, TCS, RELIANCE
    isin = models.CharField(max_length=20, null=True, blank=True)
    asset_type = models.CharField(max_length=30)      # equity, etf, bond, etc.

    as_of = models.DateTimeField()                    # exact time price is for
    last_price = models.DecimalField(max_digits=12, decimal_places=4)
    close_price = models.DecimalField(max_digits=12, decimal_places=4,
                                      null=True, blank=True)

    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "stock_prices"
        indexes = [
            models.Index(fields=['symbol']),
            models.Index(fields=['isin']),
            models.Index(fields=['asset_type']),
            models.Index(fields=['as_of']),
        ]
        # You can tune this uniqueness rule as you like
        constraints = [
            models.UniqueConstraint(
                fields=['symbol', 'isin', 'asset_type'],
                name='uniq_stock_instrument',
            )
        ]

    def __str__(self):
        return f"{self.symbol} ({self.asset_type}) @ {self.as_of}"


class Holding(models.Model):
    broker_account = models.ForeignKey(
        BrokerAccount,
        on_delete=models.CASCADE,
        related_name='holdings',
    )
    stock = models.ForeignKey(
        Stock,
        on_delete=models.RESTRICT,
        related_name='holdings',
    )

    quantity = models.DecimalField(max_digits=30, decimal_places=6)
    avg_price = models.DecimalField(max_digits=30, decimal_places=6)
    currency = models.TextField(default='INR')

    as_of = models.DateTimeField()
    source_snapshot_id = models.TextField(null=True, blank=True)
    meta = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['broker_account']),
            models.Index(fields=['stock']),
            models.Index(fields=['as_of']),
        ]

    def __str__(self):
        return f"{self.stock.symbol} - {self.quantity}"

    # ------------------------------
    # Computed fields
    # ------------------------------
    @property
    def cost_value(self):
        """Total invested value."""
        return self.quantity * self.avg_price

    @property
    def market_value(self):
        """Current value using latest stock price."""
        if hasattr(self.stock, "last_price") and self.stock.last_price is not None:
            return self.quantity * self.stock.last_price
        return None

class Transaction(models.Model):
    broker_account = models.ForeignKey(
        BrokerAccount,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    stock = models.ForeignKey(
        Stock,
        on_delete=models.RESTRICT,   # or PROTECT
        related_name='transactions',
    )

    quantity = models.DecimalField(max_digits=30, decimal_places=6)
    price = models.DecimalField(max_digits=30, decimal_places=6)
    currency = models.TextField(default='INR')
    trade_type = models.TextField()   # e.g. BUY / SELL
    trade_time = models.DateTimeField()

    meta = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['broker_account']),
            models.Index(fields=['stock']),
            models.Index(fields=['trade_time']),
        ]

    def __str__(self):
        return f"{self.trade_type} {self.stock.symbol} {self.quantity}"
