from django.contrib import admin
from django.dispatch import receiver
from .models import Script, ScriptType, AnsiblePlaybook, AnsibleRole, AnsibleCollection, File

class ScriptAdmin(admin.ModelAdmin):
  model = Script
  readonly_fields = ['slug']
  list_display = ['name', 'filename', 'scriptType']
  exclude = ('slug',)
  fieldsets = (
    ('Basic Information', {
      'fields': ('name', 'filename', 'scriptType', 'version')
    }),
    ('Description', {
      'fields': ('description',),
      'classes': ('wide',)
    }),
    ('Dependencies', {
      'fields': ('dependsOn',)
    }),
  )

class FileAdmin(admin.ModelAdmin):
  model = File
  readonly_fields = ['slug']
  list_display = ['name', 'filename']
  exclude = ('slug',)
  fieldsets = (
    ('Basic Information', {
      'fields': ('name', 'filename', 'version')
    }),
    ('Description', {
      'fields': ('description',),
      'classes': ('wide',)
    }),
  )

class AnsiblePlaybookAdmin(admin.ModelAdmin):
  model = AnsiblePlaybook
  readonly_fields = ['slug']
  list_display = ['name', 'filename', 'scriptType']
  exclude = ('slug',)
  fieldsets = (
    ('Basic Information', {
      'fields': ('name', 'filename', 'scriptType', 'version')
    }),
    ('Description', {
      'fields': ('description',),
      'classes': ('wide',)
    }),
    ('Dependencies', {
      'fields': ('dependsOn',)
    }),
  )

  
class AnsibleRoleAdmin(admin.ModelAdmin):
  model = AnsibleRole
  readonly_fields = ['slug']
  list_display = ['name', 'roleurl', 'scriptType']
  exclude = ('slug',)
  fieldsets = (
    ('Basic Information', {
      'fields': ('name', 'roleurl', 'scriptType', 'version')
    }),
    ('Description', {
      'fields': ('description',),
      'classes': ('wide',)
    }),
    ('Dependencies', {
      'fields': ('dependsOn',)
    }),
  )

class AnsibleCollectionAdmin(admin.ModelAdmin):
  model = AnsibleCollection
  readonly_fields = ['slug']
  list_display = ['name', 'collectionurl', 'scriptType']
  exclude = ('slug',)
  fieldsets = (
    ('Basic Information', {
      'fields': ('name', 'collectionurl', 'scriptType', 'version')
    }),
    ('Description', {
      'fields': ('description',),
      'classes': ('wide',)
    }),
    ('Dependencies', {
      'fields': ('dependsOn',)
    }),
  )


class ScriptTypeAdmin(admin.ModelAdmin):
  model = ScriptType
  list_display = ['name']


admin.site.register(File, FileAdmin)
admin.site.register(AnsiblePlaybook, AnsiblePlaybookAdmin)
admin.site.register(AnsibleRole, AnsibleRoleAdmin)
admin.site.register(AnsibleCollection, AnsibleCollectionAdmin)
admin.site.register(Script, ScriptAdmin)