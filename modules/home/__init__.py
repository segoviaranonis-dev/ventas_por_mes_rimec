# =============================================================================
# SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
# UBICACIÓN: modules/home/__init__.py
# VERSIÓN: 94.5.1 (BRIDGE SYNC READY)
# AUTOR: Héctor & Gemini AI
# DESCRIPCIÓN: Puente de exportación para el Hub Central.
#              Sincronizado con render_home (UI) y Navigator v94.4.0.
# =============================================================================

"""
Módulo Home - Pantalla de Bienvenida Ciudad RIMEC
"""

from .ui import render_home

__all__ = ['render_home']