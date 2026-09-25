from django.contrib import admin

from .models import Bill, BillItem, Payment


class ItemInline(admin.TabularInline):
    model = BillItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "patient", "issued_date", "status")
    list_filter = ("status",)
    inlines = [ItemInline, PaymentInline]
