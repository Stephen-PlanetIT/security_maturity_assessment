import os

# Inject a sample PLANET_BRAND_COLORS payload for testing
os.environ["PLANET_BRAND_COLORS"] = '{"primaryColor":"#1A4D8F","backgroundColor":"#FFFFFF","secondaryBackgroundColor":"#F0F2F6","textColor":"#262730"}'

from config import get_planet_branding_palette

palette = get_planet_branding_palette()
print(palette)