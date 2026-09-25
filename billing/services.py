from .models import Bill, BillItem


def sync_room_charge(admission, user):
    """Create (or update) the invoice for an admission with a single room-charge line."""
    bill, _ = Bill.objects.get_or_create(admission=admission, defaults={"patient": admission.patient, "created_by": user})
    n = admission.nights
    desc = f"{admission.bed} — {n} night{'s' if n != 1 else ''} @ {admission.daily_rate}"
    item = bill.items.filter(category=BillItem.Category.ROOM).first()
    if item:
        item.description, item.quantity, item.unit_price = desc, n, admission.daily_rate
        item.save()
    else:
        BillItem.objects.create(bill=bill, category=BillItem.Category.ROOM, description=desc, quantity=n, unit_price=admission.daily_rate)
    return bill
