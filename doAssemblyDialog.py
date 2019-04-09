# -*- coding: utf-8 -*-
"""
/***************************************************************************
 doAssembyDialogDialog
                                 A QGIS plugin
 Extraction des zones eau Plugin Cerema
                             -------------------
        begin                : 2019-01-10
        git sha              : $Format:%H$
        copyright            : (C) 2019 Cerema by Christelle Bosc & Gilles Fouvet
        email                : Christelle.Bosc@cerema.fr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt5 import uic
from PyQt5 import QtWidgets

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'assemblyDialog.ui'))

class CeremaAssemblyDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(CeremaAssemblyDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
