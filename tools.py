# -*- coding: utf-8 -*-
"""
/***************************************************************************
 tools
                                 A QGIS plugin
 Cart'Eau. Plugin Cerema.
                              -------------------
        begin                : 2019-01-10
        modification         : 
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Christelle Bosc & Gilles Fouvet
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
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QTextCursor
from PyQt5.QtWidgets import QApplication, QGraphicsDropShadowEffect

from qgis.core import QgsApplication, QgsProject

from qgis.gui import *
import sys,os,glob
import math
from osgeo import ogr ,osr, gdal
from gdalconst import *
import unicodedata

#########################################################################
# CONSTANTES                                                            #
######################################################################### 

EXT_RASTER = '.tif'
EXT_VECTOR = '.shp'
EXT_TEXT = '.txt'
EXT_ADOBE = '.pdf'
FORMAT_IMA = 'GTiff'
FORMAT_VECT = 'ESRI Shapefile'

EXT_IMAGES_LIST = ['tif','TIF','tiff','TIFF','ecw','ECW','jp2','JP2','asc','ASC','img','IMG']
FORMAT_EXTENTION_SELECT = "Raster (*.tif *.tiff *.TIF *.TIFF);;Raster (*.jp2 *.JP2);;Raster (*.ecw *.ECW);;Raster (*.asc *.ASC);;Raster (*.img *.IMG)"
FORMAT_EXTENTION_ASSEMBLE = "Raster (*.tif *.tiff *.TIF *.TIFF)"

#########################################################################
# FONCTION messInfo()                                                   #
######################################################################### 
def messInfo(dlg, info):
    # Affichage des informations et du suivi du traitement dans la fenêtre "Messages" du Plugin
    dlg.mess.append(info)
    dlg.mess.repaint()
    dlg.mess.moveCursor(QTextCursor.End)
    dlg.mess.ensureCursorVisible()
    QApplication.instance().processEvents()
    return

#########################################################################
# FONCTION messErreur()                                                 #
#########################################################################    
def messErreur(dlg, mess):
    messInfo(dlg,"Erreur ! ----> " + mess)
    messInfo(dlg,"")
    messInfo(dlg,"Fin de traitement.")
    return   

#########################################################################
# FONCTION layerList()                                                  #
#########################################################################    
def layerList():
    # Les couches présentes dans QGIS
    allLayers = QgsProject.instance().layerTreeRoot().layerOrder()

    liste = {}
    for i in allLayers:
        liste[i.name()] = i
    return liste

#########################################################################
# FONCTION setLayerVisible()                                            #
#########################################################################
def setLayerVisible(layername, state):
    allLayers = QgsProject.instance().layerTreeRoot().layerOrder()
    for lyr in allLayers:
        if lyr.name() == layername :
            QgsProject.instance().layerTreeRoot().findLayer(lyr.id()).setItemVisibilityChecked(state)
            break
    return
    
#########################################################################
# FONCTION setStyleShadowQLabel()                                       #
#########################################################################    
def setStyleShadowQLabel(qLabel):
    # Style couleur ombré (enable) et grisé (disable) les widgets QLabel
    effectShadow = QGraphicsDropShadowEffect()
    effectShadow.setBlurRadius(10)                         # defaut: 1
    effectShadow.setColor(QColor(100,100,100, 180))        # defaut: QColor(63, 63, 63, 180)
    effectShadow.setOffset(4, 4)                           # defaut: 8,8
    qLabel.setGraphicsEffect(effectShadow)
    qLabel.setStyleSheet(":enabled {color: black} :disabled {color: grey}")
    return
    
#########################################################################
# FONCTION extractAsLine()                                              #
#########################################################################    
def extractAsLine(geom):
    # Fonction utilisée pour la linéarisation des polygones 
    multiGeom = QgsGeometry()
    lines = []
    if geom.type() == QGis.Polygon:
        if geom.isMultipart():
            multiGeom = geom.asMultiPolygon()
            for i in multiGeom:
                lines.extend(i)
        else:
            multiGeom = geom.asPolygon()
            lines = multiGeom
        return lines
    else:
        return []
        
#########################################################################
# FONCTION removeAccents()                                              #
#########################################################################    
def removeAccents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return str("".join([c for c in nfkd_form if not unicodedata.combining(c)]))

#########################################################################
# FONCTION correctedPath()                                              #
#########################################################################
# Fonction de correction des chemins
# (ajout de slash en fin de chaîne)
def correctedPath(nPath):
    nPath = str(nPath)
    a = len(nPath)
    subC = os.sep
    b = nPath.rfind(subC, 0, a)
    if a != b : return (nPath + os.sep)
    else: return nPath
    return 
    
#########################################################################
# FONCTION getThemeIcon()                                               #
#########################################################################
# Fonction de reconstruction du chemin absolu vers la ressource image
def getThemeIcon(theName):
    myPath = correctedPath(os.path.dirname(__file__));
    myDefPathIcons = myPath + os.sep + "icons" + os.sep
    myDefPath = myPath.replace("\\",os.sep)+ theName;
    myDefPathIcons = myDefPathIcons.replace("\\", os.sep)+ theName;
    myCurThemePath = QgsApplication.activeThemePath() + os.sep + "plugins" + os.sep + theName;
    myDefThemePath = QgsApplication.defaultThemePath() + os.sep + "plugins" + os.sep + theName;
    # Attention, ci-dessous, le chemin est à persoonaliser :
    # Remplacer "extension" par le nom du répertoire de l'extension.
    myQrcPath = "python" + os.sep + "plugins" + os.sep + "CeremaCartEau3" + os.sep + theName;
    if QFile.exists(myDefPath): return myDefPath
    elif QFile.exists(myDefPathIcons): return myDefPathIcons  
    elif QFile.exists(myCurThemePath): return myCurThemePath
    elif QFile.exists(myDefThemePath): return myDefThemePath
    elif QFile.exists(myQrcPath): return myQrcPath
    elif QFile.exists(theName): return theName
    else: return ""
    return

#########################################################################
# FONCTION getEmpriseFile()                                             #
#########################################################################
#   Role : Cette fonction permet de retourner les coordonnées xmin,xmax,ymin,ymax de l'emprise d'un fichier shape
#   Paramètres :
#       vector_input : nom du fichier vecteur d'entrée
#       format_shape : format du fichier shape
#   Paramètres de retour :
#       xmin, xmax, ymin, ymax
def getEmpriseFile(empr_file, format_shape='ESRI Shapefile'):

    xmin = 0
    xmax = 0
    ymin = 0
    ymax = 0
    
    # Recuperation du  driver pour le format shape
    driver = ogr.GetDriverByName(format_shape)

    # Ouverture du fichier d'emprise
    data_source = driver.Open(empr_file, 0)
    if data_source is not None:

        # Recuperation des couches de donnees
        layer = data_source.GetLayer(0)
        num_features = layer.GetFeatureCount()
        extent = layer.GetExtent()

        # Fermeture du fichier d'emprise
        data_source.Destroy()

        xmin = extent[0]
        xmax = extent[1]
        ymin = extent[2]
        ymax = extent[3]
    
    data_source = None
    
    return xmin,xmax,ymin,ymax
    
#########################################################################
# FONCTION getEmpriseImage()                                            #
#########################################################################
#   Role : Cette fonction permet de retourner les coordonnées xmin,xmax,ymin,ymax de l'emprise de l'image
#   Paramètres :
#       image_raster : fichier image d'entrée
#   Paramétres de retour :
#       xmin : valeur xmin de l'emprise de l'image
#       xmax : valeur xmax de l'emprise de l'image
#       ymin : valeur ymin de l'emprise de l'image
#       ymax : valeur ymax de l'emprise de l'image
def getEmpriseImage(image_raster):

    xmin = 0
    xmax = 0
    ymin = 0
    ymax = 0

    dataset = gdal.Open(image_raster, GA_ReadOnly)
    if dataset is not None:
        cols = dataset.RasterXSize
        rows = dataset.RasterYSize
        geotransform = dataset.GetGeoTransform()
        pixel_width = geotransform[1]  # w-e pixel resolution
        pixel_height = geotransform[5] # n-s pixel resolution
        xmin = geotransform[0]         # top left x
        ymax = geotransform[3]         # top left y
        xmax = xmin + (cols * pixel_width)
        ymin = ymax + (rows * pixel_height)

    dataset = None

    return xmin, xmax, ymin, ymax
    
#########################################################################
# FONCTION getPixelWidthXYImage()                                       #
#########################################################################
#   Role : Cette fonction permet de retourner les dimensions d'un pixel de l'image en X et en Y
#   Paramètres :
#       image_raster : fichier image d'entrée
#   Paramètres de retour :
#       pixel_width : la dimension d'un pixel en largeur
#       pixel_height : la dimension d'un pixel en hauteur
def getPixelWidthXYImage(image_raster):

    pixel_width = 0.0
    pixel_height = 0.0
    dataset = gdal.Open(image_raster, GA_ReadOnly)
    if dataset is not None:
        geotransform = dataset.GetGeoTransform()
        pixel_width = geotransform[1]  # w-e pixel resolution
        pixel_height = geotransform[5] # n-s pixel resolution
    dataset = None

    return pixel_width, pixel_height
    
#########################################################################
# FONCTION getNodataValueImage()                                        #
#########################################################################
#   Role : Cette fonction permet de retourner la valeur du nodata defini pour l'image ou None si le nodata n'est pas défini
#   Paramètres :
#       image_raster : fichier image d'entrée
#       num_band     : la valeur de la bande choisi par defaut bande 1
#   Paramètres de retour :
#       value_nodata : la valeur des pixels nodata si defini None sinon
def getNodataValueImage(image_raster, num_band=1):

    value_nodata = None

    dataset = gdal.Open(image_raster, GA_ReadOnly)
    if dataset is not None:
        # Get band
        band = dataset.GetRasterBand(num_band)
        if band != None :
            # Read the nodata band
            value_nodata = band.GetNoDataValue()
            band = None

    dataset = None

    return value_nodata    

#########################################################################
# FONCTION getGeometryImage()                                           #
#########################################################################
#   Role : Cette fonction permet de retourner le nombre de colonne, le nombre de ligne et le nombre de bande de l'image
#   Paramètres :
#       image_raster : fichier image d'entrée
#   Paramètres de retour :
#       cols : le nombre de colonnes de l'image
#       rows : le nombre de lignes de l'image
#       bands : le nombre de bandes de l'image

def getGeometryImage(image_raster):

    cols = 0
    rows = 0
    bands = 0
    dataset = gdal.Open(image_raster, GA_ReadOnly)
    if dataset is not None:
        cols = dataset.RasterXSize
        rows = dataset.RasterYSize
        bands = dataset.RasterCount
    dataset = None

    return cols, rows, bands
    
#########################################################################
# FONCTION getDataTypeImage()                                           #
#########################################################################
#   Role : Cette fonction permet de retourner le type de data de l'image (UInt8, Uint16, Float32...)
#   Paramètres :
#       image_raster : fichier image d'entrée
#       num_band     : la valeur de la bande choisi par defaut bande 1
#   Paramètres de retour :
#       data_type : le type des data si defini None sinon

def getDataTypeImage(image_raster, num_band=1):

    data_type = None

    dataset = gdal.Open(image_raster, GA_ReadOnly)
    if dataset is not None:
        # Get band
        band = dataset.GetRasterBand(num_band)
        if band != None :
            # Read the nodata band
            data_type = band.DataType
            #data_type_name =  gdal.GetDataTypeName(band.DataType)
            band = None

    dataset = None

    return data_type
    
#########################################################################
# FONCTION getProjectionImage()                                         #
#########################################################################
#   Role : Cette fonction permet de retourner la valeur de la projection de l'image
#   Paramètres :
#       image_raster : fichier image d'entrée
#   Paramètres de retour :
#       epsg : la valeur de la projection de l'image
def getProjectionImage(image_raster):

    epsg = 0
    dataset = gdal.Open(image_raster, GA_ReadOnly)
    if dataset is not None:

        srs = osr.SpatialReference()
        srs.ImportFromWkt(dataset.GetProjection())
        epsg = srs.GetAttrValue('AUTHORITY',1)
    dataset = None

    return epsg
    
#########################################################################
# FONCTION updateReferenceProjection()                                  #
#########################################################################
#   Role : Cette fonction permet de mettre a jour la projection d'un fichier avec un fichier de réfèrence
#   Paramètres :
#       image : fichier image à  modifier
#       epsg : choix du système de projection que l'on veut appliquer à  l'image. Par exemple : epsg = 2154

def updateReferenceProjection(image, epsg):

    # Ouverture du fichier a modifier
    dataset_output = gdal.Open(image, GA_Update)
    
    if dataset_output is not None:
        srs = osr.SpatialReference()

        # Récupération du système du fichier origine
        srs.ImportFromWkt(dataset_output.GetProjectionRef())
        srs.ImportFromEPSG(int(epsg))
        projection = srs.ExportToWkt()

        # Mise a jour de la nouvelle projection  pour le fichier à  mettre à  jour
        dataset_output.SetProjection(projection)

    # Close dataset
    dataset_output = None

    return
    
#########################################################################
# FONCTION roundPixelEmpriseSize()                                      #
#########################################################################
#   Role : Calcul des valeur arrondis d'une emprise arrondi à  la taille du pixel de l'image
#   Paramètres :
#       pixel_size_x : Taille du pixel en x (en m)
#       pixel_size_y : Taille du pixel en y (en m)
#       empr_xmin    : L'emprise brute d'entrée coordonnée xmin
#       empr_xmax    : L'emprise brute d'entrée coordonnée xmax
#       empr_ymin    : L'emprise brute d'entrée coordonnée ymin
#       empr_ymax    : L'emprise brute d'entrée coordonnée ymax
#   Paramètres de retour :
#       round_xmin    : L'emprise corrigée de sortie coordonnée xmin
#       round_xmax    : L'emprise corrigée de sortie coordonnée xmax
#       round_ymin    : L'emprise corrigée de sortie coordonnée ymin
#       round_ymax    : L'emprise corrigée de sortie coordonnée ymax
#
def roundPixelEmpriseSize(pixel_size_x, pixel_size_y, empr_xmin, empr_xmax, empr_ymin, empr_ymax):

    # Calculer l'arrondi pour une emprise à  la taille d'un pixel pres (+/-)
    val_round = abs(pixel_size_x)

    pos_xmin = int(math.floor(empr_xmin))
    round_xmin = pos_xmin - pos_xmin % val_round
    pos_xmax = int(math.ceil(empr_xmax))
    round_xmax = pos_xmax - pos_xmax % val_round
    if round_xmax < pos_xmax :
        round_xmax = round_xmax + val_round
    pos_ymin = int(math.floor(empr_ymin))
    round_ymin = pos_ymin - pos_ymin % val_round
    pos_ymax = int(math.ceil(empr_ymax))
    round_ymax = pos_ymax - pos_ymax % val_round
    if round_ymax < pos_ymax :
        round_ymax = round_ymax + val_round

    return round_xmin, round_xmax, round_ymin, round_ymax
    
#########################################################################
# FONCTION getMinMaxValueBandImage()                                    #
#########################################################################
#   Rôle : Cette fonction permet de récupérer la valeur minimale et maximale d'un canal d'une l'image
#   Paramètres :
#       image_raster : fichier image d'entrée
#       channel : Le numéro de bande de l'image
#   Paramètres de retour :
#       image_max_band : la valeur pixel minimale d'une bande de l'image
#       image_mini_band : la valeur pixel maximale d'une bande de l'image

def getMinMaxValueBandImage(image_raster, channel):

    dataset = gdal.Open(image_raster, GA_ReadOnly)
    band = dataset.GetRasterBand(channel)
    a = band.ComputeRasterMinMax()

    maximum = -65535.0
    minimum = 65535.0
    if maximum < a[1]:
        maximum =a [1]
    if minimum > a[0]:
        minimum = a[0]
    dataset = None

    # Valeur maximale des pixels sur la bande
    image_max_band = maximum
    # Valeur minimale des pixels sur la bande
    image_mini_band = minimum

    return image_max_band, image_mini_band    