from django.core.management.base import BaseCommand
from portfolio import models
from portfolio.triggers import registry
from django.utils import timezone

class Command(BaseCommand):
    help = 'Sync holdings for active portfolios using broker triggers.'

    def handle(self, *args, **options):
        self.stdout.write('Starting holdings sync...')
        # iterate active portfolios
        portfolios = models.Portfolio.objects.filter(active=True).select_related('user')
        for p in portfolios:
            self.stdout.write(f'Processing portfolio: {p.name} (id={p.id})')
            for account in p.broker_accounts.all().select_related('broker_type'):
                self.stdout.write(f' - Broker account: {account} ({account.broker_type.code})')
                trigger_cls = registry.get_trigger_for_code(account.broker_type.code)
                if not trigger_cls:
                    self.stdout.write(f'   No trigger found for {account.broker_type.code}, skipping.')
                    continue
                try:
                    trigger = trigger_cls(account)
                    snapshot = trigger.fetch_holdings()
                    # snapshot is expected: list of dicts {symbol, quantity, avg_price, asset_type, isin, market_value, as_of, source_snapshot_id, meta}
                    for h in snapshot:
                        obj, created = models.Holding.objects.update_or_create(
                            broker_account=account,
                            symbol=h['symbol'],
                            as_of=h.get('as_of', timezone.now()),
                            defaults={
                                'asset_type': h.get('asset_type','stock'),
                                'isin': h.get('isin'),
                                'quantity': h.get('quantity',0),
                                'avg_price': h.get('avg_price',0),
                                'currency': h.get('currency','INR'),
                                'cost_value': h.get('cost_value'),
                                'market_value': h.get('market_value'),
                                'source_snapshot_id': h.get('source_snapshot_id'),
                                'meta': h.get('meta'),
                            }
                        )
                        self.stdout.write(f"    Saved holding {obj.symbol} qty={obj.quantity}")
                except Exception as e:
                    self.stdout.write(f'   Error while fetching for account {account}: {e}')

        self.stdout.write('Holdings sync completed.')
