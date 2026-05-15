from django import template
register = template.Library()

@register.filter
def pct(value):
    """Convert 0.887 to 88.7"""
    try:
        return round(float(value) * 100, 1)
    except:
        return value

@register.filter
def acc_color(value):
    """Return Tailwind color class based on accuracy."""
    try:
        v = float(value)
        if v >= 0.85: return 'text-green-600'
        if v >= 0.70: return 'text-amber-600'
        return 'text-red-600'
    except:
        return 'text-gray-500'
