# utils/email_utils.py
"""Email sending utilities.

Provides a thin wrapper around Django's email APIs to render templates
and send multipart HTML/text messages used by registration and password flows.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_system_email(
    subject,
    message=None,
    recipient_list=None,
    from_email=None,
    fail_silently=False,
    html_message=None,
    template_name=None,
    context=None,
):
    """
    Generic utility to send emails with optional HTML + TXT templates.
    """
    from_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "Prime Academy <no-reply@primeacademy.org>")

    # If template_name is given, render both .txt and .html
    if template_name and context is not None:
        message = render_to_string(f"{template_name}.txt", context)
        html_message = render_to_string(f"{template_name}.html", context)

    if html_message:
        email = EmailMultiAlternatives(subject, message, from_email, recipient_list)
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=fail_silently)
    else:
        from django.core.mail import send_mail
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=fail_silently,
        )

