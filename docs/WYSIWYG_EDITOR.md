# WYSIWYG Editor for Scripts

## Overview

This document describes the WYSIWYG (What You See Is What You Get) text editor implementation for the mProv Control Center scripts section.

## Features

The WYSIWYG editor has been added to the following models in the scripts app:
- **Script**: For describing what scripts do
- **File**: For describing uploaded files
- **Ansible Playbook**: For describing playbook functionality
- **Ansible Role**: For describing role purposes
- **Ansible Collection**: For describing collection contents

## Editor Capabilities

The CKEditor-based WYSIWYG editor includes:
- **Text Formatting**: Bold, Italic, Underline
- **Lists**: Numbered and Bulleted lists
- **Alignment**: Left, Center, Right, Justify
- **Links**: Insert and remove hyperlinks
- **Source View**: Toggle between WYSIWYG and HTML source
- **Maximize**: Full-screen editing mode
- **Indentation**: Increase and decrease indent levels

## Usage

1. Navigate to any of the script-related admin pages
2. Click "Add" to create a new item or edit an existing one
3. Switch to the "Description" tab
4. Use the rich text editor to format your description

## Technical Details

### Configuration

The editor is configured in `settings.py`:
```python
CKEDITOR_CONFIGS = {
    'script_editor': {
        'toolbar': 'Custom',
        'toolbar_Custom': [
            ['Bold', 'Italic', 'Underline'],
            ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
            ['Link', 'Unlink'],
            ['RemoveFormat', 'Source'],
            ['Maximize'],
        ],
        'height': 300,
        'width': '100%',
    },
}
```

### Database Field

Each model now includes a `description` field:
```python
description = RichTextField(
    blank=True, 
    null=True, 
    config_name='script_editor', 
    help_text="Optional description of what this [item] does"
)
```

### Admin Organization

The admin interface uses fieldsets to organize fields into tabs:
- **Basic Information**: Name, filename, type, version
- **Description**: WYSIWYG editor for rich text descriptions
- **Dependencies**: Related items and dependencies

## Notes

- The description field is optional (blank=True, null=True)
- Descriptions are stored as HTML in the database
- The editor uses CKEditor 4 (as bundled with django-ckeditor)
