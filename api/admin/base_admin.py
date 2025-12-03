from django.contrib import admin


class BaseModelAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('admin/css/ckeditor-custom.css',)
        }
