from django.conf import settings


class ExtDatasetsRouter:
    """
    A router to control all database operations on models in the
    ext_datasets application.
    """

    def db_for_read(self, model, **hints):
        """
        Attempts to read ext_datasets models go to datasets db.
        """
        if model._meta.app_label == 'ext_datasets':
            return settings.DATASETS_DB_NAME
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write auth models go to datasets db.
        """
        if model._meta.app_label == 'ext_datasets':
            return settings.DATASETS_DB_NAME
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the ext_datasets app only appears in the datasets db
        """
        if settings.DATASETS_DB_NAME != 'default':
            if app_label == 'ext_datasets':
                return db == settings.DATASETS_DB_NAME
            else:
                return db != settings.DATASETS_DB_NAME
        return None
