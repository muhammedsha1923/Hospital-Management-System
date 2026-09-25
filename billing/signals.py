from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Bill, BillItem, Payment


@receiver([post_save, post_delete], sender=BillItem)
@receiver([post_save, post_delete], sender=Payment)
def update_bill_status(sender, instance, **kwargs):
    instance.bill.refresh_status()


@receiver(post_save, sender=Bill)
def bill_saved(sender, instance, created, **kwargs):
    if not created:
        instance.refresh_status()  # discount may have changed
