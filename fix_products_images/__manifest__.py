# -*- coding: utf-8 -*-
{
    'name': 'Fix Product Template Images',
    'version': '1.1',
    'category': '',
    'summary': """
    # Fix Product Template Images
    ## [USE IT BY YOUR OWN RISK!]
    
    This script helps to add the missing images when you import products (with images) with the orm or external api.
    When you use this methods usually some images are not generated 
    (ex. Import webp image will not generate jpeg images.).
    
    Install this app and use the systray on the tap clicking it. This will trigger some orm methods to create the 
    missing ones. You can found the report on Logging.
    
    Create by vmac-odoo for task opw-4729908
    """,
    'data': [],
    'installable': True,
    'license': 'AGPL-3',
    'assets': {
        'web.assets_backend': [      
            'fix_products_images/static/src/js/systray_icon.js', 
        ]
    }
}
