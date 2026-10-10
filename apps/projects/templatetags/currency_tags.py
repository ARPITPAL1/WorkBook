from django import template
from apps.projects.utils import format_inr

register = template.Library()


@register.filter(name='inr_format')
def inr_format(value):
    """
    Format a number or Decimal with Indian numbering system and '₹' prefix.
    Example: {{ project.approved_initial_budget|inr_format }} -> ₹4,50,00,000.00
    """
    return format_inr(value)


@register.filter(name='inr_no_symbol')
def inr_no_symbol(value):
    """
    Format a number or Decimal with Indian numbering system without the symbol.
    Example: {{ project.approved_initial_budget|inr_no_symbol }} -> 4,50,00,000.00
    """
    return format_inr(value, symbol="")
