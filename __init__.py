# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CeremaCartEau
                                 A QGIS plugin
 Extraction des zones eau Plugin Cerema
                             -------------------
        begin                : 2019-01-10
        copyright            : (C) 2019 Cerema by Christelle Bosc & Gilles Fouvet
        email                : Christelle.Bosc@cerema.fr
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load CeremaCartEau class from file CeremaCartEau.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .main import CeremaCartEau
    return CeremaCartEau(iface)
