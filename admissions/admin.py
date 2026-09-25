from django.contrib import admin

from .models import Admission, Bed

admin.site.register(Bed)
admin.site.register(Admission)
