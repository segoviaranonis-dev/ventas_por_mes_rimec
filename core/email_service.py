"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MÓDULO: core/email_service.py
VERSION: 1.0.0 (UNIVERSAL EMAIL ENGINE)
AUTOR: Héctor & Claude AI
DESCRIPCIÓN: Servicio agnóstico de envío de emails con soporte para templates HTML,
             attachments y múltiples destinatarios.

CARACTERÍSTICAS:
    ✓ SMTP con TLS
    ✓ Templates HTML con Jinja2
    ✓ Attachments (PDFs, Excel, etc.)
    ✓ Múltiples destinatarios (TO, CC, BCC)
    ✓ Logging integrado
    ✓ Manejo robusto de errores
    ✓ Mode dry-run para testing

USO BÁSICO:
    from core.email_service import EmailService

    # Email simple
    EmailService.send(
        to=["user@example.com"],
        subject="Título",
        body="<h1>Contenido HTML</h1>"
    )

    # Email con template
    EmailService.send_with_template(
        to=["user@example.com"],
        subject="Factura Interna",
        template_name="email_factura_confirmada",
        context={"nro_pedido": "PV-2026-0123", ...}
    )

    # Email con PDF adjunto
    EmailService.send(
        to=["user@example.com"],
        subject="Tu factura",
        body="<p>Adjunto la factura</p>",
        attachments=[
            ("factura.pdf", pdf_bytes, "application/pdf")
        ]
    )
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr, formatdate
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.settings import settings


class EmailServiceError(Exception):
    """Excepción base para errores de EmailService."""
    pass


class EmailService:
    """Servicio universal de envío de emails."""

    # Rutas
    BASE_DIR = Path(__file__).parent.parent
    TEMPLATES_DIR = BASE_DIR / "templates" / "email"

    # Ambiente Jinja2 (lazy loading)
    _jinja_env = None

    @classmethod
    def _get_jinja_env(cls):
        """Inicializa ambiente Jinja2 para templates de email."""
        if cls._jinja_env is None:
            cls._jinja_env = Environment(
                loader=FileSystemLoader([str(cls.TEMPLATES_DIR)]),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True
            )
        return cls._jinja_env

    @classmethod
    def _log(cls, message: str, level: str = "INFO"):
        """Log interno (evita dependencia circular)."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [EmailService] [{level}] {message}")

    @classmethod
    def send(
        cls,
        to: List[str],
        subject: str,
        body: str,
        cc: List[str] = None,
        bcc: List[str] = None,
        attachments: List[Tuple[str, bytes, str]] = None,
        dry_run: bool = False
    ) -> bool:
        """
        Envía un email con soporte completo para HTML, attachments y múltiples destinatarios.

        Args:
            to: Lista de destinatarios principales
            subject: Asunto del email
            body: Cuerpo HTML del email
            cc: Lista de destinatarios en copia (opcional)
            bcc: Lista de destinatarios en copia oculta (opcional)
            attachments: Lista de tuplas (filename, bytes, mimetype)
            dry_run: Si True, solo simula el envío (útil para testing)

        Returns:
            True si el envío fue exitoso, False en caso contrario

        Raises:
            EmailServiceError: Si hay un error crítico en la configuración
        """
        # Validar configuración
        if not settings.EMAIL_ENABLED:
            cls._log("Email deshabilitado en settings (EMAIL_ENABLED=False)", "WARNING")
            return False

        if not settings.EMAIL_USERNAME or not settings.EMAIL_PASSWORD:
            raise EmailServiceError(
                "Credenciales de email no configuradas. "
                "Revisar EMAIL_USERNAME y EMAIL_PASSWORD en .env"
            )

        if not to:
            raise EmailServiceError("Debe especificar al menos un destinatario")

        # Preparar mensaje
        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM_ADDRESS))
        msg['To'] = ", ".join(to)
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)

        if cc:
            msg['Cc'] = ", ".join(cc)

        # Body HTML
        msg.attach(MIMEText(body, 'html', 'utf-8'))

        # Attachments
        if attachments:
            for filename, file_bytes, mimetype in attachments:
                part = MIMEApplication(file_bytes, _subtype=mimetype.split('/')[-1])
                part.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(part)

        # Lista completa de destinatarios (para SMTP)
        all_recipients = to + (cc or []) + (bcc or [])

        # Dry run mode
        if dry_run:
            cls._log(f"[DRY-RUN] Email preparado:", "INFO")
            cls._log(f"  TO: {to}", "INFO")
            cls._log(f"  CC: {cc}", "INFO")
            cls._log(f"  BCC: {bcc}", "INFO")
            cls._log(f"  Subject: {subject}", "INFO")
            cls._log(f"  Attachments: {len(attachments or [])}", "INFO")
            return True

        # Enviar email
        try:
            cls._log(f"Conectando a {settings.EMAIL_HOST}:{settings.EMAIL_PORT}...", "INFO")

            with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
                if settings.EMAIL_USE_TLS:
                    server.starttls()

                server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                server.send_message(msg, from_addr=settings.EMAIL_FROM_ADDRESS, to_addrs=all_recipients)

            cls._log(f"✓ Email enviado exitosamente a {len(all_recipients)} destinatario(s)", "INFO")
            return True

        except smtplib.SMTPAuthenticationError as e:
            cls._log(f"Error de autenticación SMTP: {e}", "ERROR")
            raise EmailServiceError(f"Credenciales inválidas: {e}")

        except smtplib.SMTPException as e:
            cls._log(f"Error SMTP: {e}", "ERROR")
            return False

        except Exception as e:
            cls._log(f"Error inesperado al enviar email: {e}", "ERROR")
            return False

    @classmethod
    def send_with_template(
        cls,
        to: List[str],
        subject: str,
        template_name: str,
        context: Dict,
        **kwargs
    ) -> bool:
        """
        Envía un email usando un template Jinja2.

        Args:
            to: Lista de destinatarios
            subject: Asunto del email
            template_name: Nombre del template (sin .html)
            context: Diccionario con datos para el template
            **kwargs: Argumentos adicionales para send() (cc, bcc, attachments, etc.)

        Returns:
            True si el envío fue exitoso

        Example:
            EmailService.send_with_template(
                to=["vendedor@rimec.com"],
                subject="Factura Confirmada",
                template_name="email_factura_confirmada",
                context={
                    "nro_pedido": "PV-2026-0123",
                    "total": 10000000,
                    "vendedor_nombre": "Juan Pérez"
                }
            )
        """
        env = cls._get_jinja_env()

        # Merge context con variables base
        full_context = {
            "company_name": settings.COMPANY_NAME,
            "system_name": settings.SYSTEM_NAME,
            "timestamp": datetime.now().strftime('%d/%m/%Y %H:%M'),
            "primary_color": settings.UI_PRIMARY,
        }
        full_context.update(context)

        # Renderizar template
        try:
            template = env.get_template(f"{template_name}.html")
            body = template.render(**full_context)
        except Exception as e:
            cls._log(f"Error al renderizar template '{template_name}': {e}", "ERROR")
            raise EmailServiceError(f"Template '{template_name}.html' no encontrado o inválido: {e}")

        # Enviar usando el método base
        return cls.send(to=to, subject=subject, body=body, **kwargs)

    @classmethod
    def validate_config(cls) -> Tuple[bool, str]:
        """
        Valida la configuración de email.

        Returns:
            (is_valid, message)
        """
        if not settings.EMAIL_ENABLED:
            return False, "Email deshabilitado (EMAIL_ENABLED=False)"

        if not settings.EMAIL_USERNAME:
            return False, "EMAIL_USERNAME no configurado"

        if not settings.EMAIL_PASSWORD:
            return False, "EMAIL_PASSWORD no configurado"

        if not settings.EMAIL_HOST:
            return False, "EMAIL_HOST no configurado"

        return True, "Configuración válida"

    @classmethod
    def test_connection(cls) -> Tuple[bool, str]:
        """
        Prueba la conexión SMTP.

        Returns:
            (success, message)
        """
        is_valid, msg = cls.validate_config()
        if not is_valid:
            return False, msg

        try:
            with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10) as server:
                if settings.EMAIL_USE_TLS:
                    server.starttls()
                server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                return True, "Conexión exitosa"

        except smtplib.SMTPAuthenticationError:
            return False, "Credenciales inválidas"

        except smtplib.SMTPException as e:
            return False, f"Error SMTP: {e}"

        except Exception as e:
            return False, f"Error de conexión: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES DE CONVENIENCIA PARA CASOS ESPECÍFICOS
# ─────────────────────────────────────────────────────────────────────────────

def send_factura_interna_confirmation(
    vendedor_email: str,
    supervisor_email: str,
    nro_pedido: str,
    cliente_nombre: str,
    total_general: float,
    total_pares: int,
    pdf_bytes: bytes,
    pdf_filename: str = "factura_interna.pdf"
) -> bool:
    """
    Envía email de confirmación de Factura Interna con PDF adjunto.

    Args:
        vendedor_email: Email del vendedor
        supervisor_email: Email del supervisor
        nro_pedido: Número del pedido (ej. "PV-2026-0123")
        cliente_nombre: Nombre del cliente
        total_general: Monto total del pedido
        total_pares: Cantidad total de pares
        pdf_bytes: PDF en bytes
        pdf_filename: Nombre del archivo PDF

    Returns:
        True si el envío fue exitoso
    """
    return EmailService.send_with_template(
        to=[vendedor_email],
        cc=[supervisor_email] if supervisor_email else None,
        subject=f"✓ Factura Confirmada — {nro_pedido}",
        template_name="email_factura_confirmada",
        context={
            "nro_pedido": nro_pedido,
            "cliente_nombre": cliente_nombre,
            "total_general": total_general,
            "total_pares": total_pares,
        },
        attachments=[
            (pdf_filename, pdf_bytes, "application/pdf")
        ]
    )


def send_admin_notification(subject: str, body: str) -> bool:
    """
    Envía notificación a los administradores del sistema.

    Args:
        subject: Asunto del email
        body: Cuerpo HTML del email

    Returns:
        True si el envío fue exitoso
    """
    admin_emails = [e.strip() for e in settings.EMAIL_ADMIN_ADDRESSES if e.strip()]

    if not admin_emails:
        EmailService._log("No hay emails de admin configurados", "WARNING")
        return False

    return EmailService.send(
        to=admin_emails,
        subject=f"[NEXUS CORE] {subject}",
        body=body
    )


# [EXECUTION-CONFIRMED] v1.0.0 - Universal Email Engine with SMTP + Jinja2
