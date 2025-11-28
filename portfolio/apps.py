from django.apps import AppConfig

class PortfolioConfig(AppConfig):
    def ready(self):
        # import signals / tasks to ensure they are registered
        import portfolio.tasks

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portfolio'
