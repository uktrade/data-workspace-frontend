from django import template

register = template.Library()


@register.filter
def get_attr(model, field):
    return getattr(model, field)


@register.filter
def add_class(field, class_attr):
    if 'class' in field.field.widget.attrs:
        field.field.widget.attrs['class'] = '{} {}'.format(
            field.field.widget.attrs['class'],
            class_attr
        )
    else:
        field.field.widget.attrs['class'] = class_attr
    return field


@register.filter
def add_field_error(field):
    return add_class(field, '{}--error'.format(
        field.field.widget.attrs.get('class')
    ))
