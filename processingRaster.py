# -*- coding: utf-8 -*-
"""
/***************************************************************************
processingRaster
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
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.gui import *
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry

from osgeo import gdal, ogr, osr

import os
import time
import platform
import processing

from .tools import EXT_RASTER, EXT_VECTOR, FORMAT_IMA, messInfo, messErreur, layerList, setLayerVisible, getGeometryImage

#########################################################################
# FONCTION computeNdvi()                                                #
#########################################################################
def computeNdvi(dlg, conf, dir_raster_src, dir_dest, rasterName, ndviName, extension_input_raster): 

    # Calcul despeckele indice Ndvi
    li = layerList()
    
    messInfo(dlg,"Calcul du NDVI.")
    messInfo(dlg,"")
    
    rasterPath = dir_raster_src + os.sep + rasterName + extension_input_raster
    ndviPath = dir_dest + os.sep + ndviName + EXT_RASTER
    
    # Test si c'est une image multibande
    cols, rows, bands = getGeometryImage(rasterPath)
    if bands < 4 :
        QMessageBox.information(None, "Attention !!!", ndviPath + " ne peut pas être créé. L'image raster d'entrée n'a pas un nombre de bande suffisant.", QMessageBox.Ok, QMessageBox.NoButton)         
        messErreur(dlg, ndviPath + " ne peut pas être créé.")
        return None
        
    # Selection des bandes pour le calcul du NDVI
    num_channel_red = 0
    num_channel_nir = 0
    d = conf.channelOrderDic
    key = "Red"
    if key in conf.channelOrderDic.keys():
        num_channel_red = int(conf.channelOrderDic[key])
    key = "NIR"    
    if key in conf.channelOrderDic.keys():
        num_channel_nir = int(conf.channelOrderDic[key])
        
    if (num_channel_red == 0 or num_channel_nir == 0):
        QMessageBox.information(None, "Attention !!!", ndviPath + " ne peut pas être créé. NDVI needs Red and NIR channels to be computed).", QMessageBox.Ok, QMessageBox.NoButton)         
        messErreur(dlg, ndviPath + " ne peut pas être créé.")
        return None 
    
    # Suppression du fichier de sortie si il existe 
    if os.path.exists(ndviPath):
        try:
            os.remove(ndviPath)            
        except: 
            QMessageBox.information(None, "Attention !!!", ndviPath + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)         
            messErreur(dlg, ndviPath + " ne peut pas être effacé.")
            return None     

    # Calcul
    if conf.rbOTB.isChecked():    
        # Calculatrice raster OTB                        
        try:
            expression = '(im1b%s - im1b%s)/(im1b%s + im1b%s)' %(str(num_channel_nir), str(num_channel_red), str(num_channel_nir), str(num_channel_red))
            #processing.algorithmHelp("otb:BandMath")
            #processing.runalg('otb:bandmath', rasterPath, '128',expression, ndviPath)
            parameters = {"il":[rasterPath], "out":ndviPath, "exp":expression, "outputpixeltype":2, "ram":128}
            processing.run('otb:BandMath', parameters)
        except:
            messErreur(dlg,"Erreur de traitement sur otb:BandMath ndvi.")
            return None
        # Fin OTB
        
    else: 
        # Calculatrice raster QGIS
        entries = []
        
        raster = li[rasterName]
        extent = raster.extent()
        height = raster.height()
        width = raster.width()        

        b_red = QgsRasterCalculatorEntry()
        b_red.ref = 'b@%s' %(str(num_channel_red))
        b_red.raster = raster
        b_red.bandNumber = num_channel_red
        entries.append(b_red)

        b_nir = QgsRasterCalculatorEntry()
        b_nir.ref = 'b@%s' %(str(num_channel_nir))
        b_nir.raster = raster
        b_nir.bandNumber = num_channel_nir
        entries.append(b_nir)
                                 
        expression =  '(b@%s - b@%s)/(b@%s + b@%s)' %(str(num_channel_nir), str(num_channel_red), str(num_channel_nir), str(num_channel_red))      
        calc = QgsRasterCalculator( expression, ndviPath, FORMAT_IMA, extent, width, height, entries )

        ret = calc.processCalculation()   
           
        if ret != 0:
            QMessageBox.information(None, "Attention !!!", " Erreur d'exécution, cela peut être du à une insuffisance mémoire, image trop volumineuse.", QMessageBox.Ok, QMessageBox.NoButton)        
            messErreur(dlg,"Erreur lors du lancement de QgsRasterCalculator.")       
            return None
        # Fin QGIS    
            
    if os.path.exists(ndviPath):
        ndvi = QgsRasterLayer(ndviPath, ndviName)
    else:
        QMessageBox.information(None, "Attention !!!", ndviPath + " n'a pas été créé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)        
        messErreur(dlg, ndviPath + " n'a pas été créé.")
        return None             
        
    if not ndvi.isValid():
        messErreur(dlg, ndviPath + " ne peut pas être chargé.")
        return None         

    return ndvi

#########################################################################
# FONCTION computeNdwi2()                                               #
#########################################################################
def computeNdwi2(dlg, conf, dir_raster_src, dir_dest, rasterName, ndwi2Name, extension_input_raster): 

    # Calcul despeckele indice Ndwi2
    li = layerList()
    
    messInfo(dlg,"Calcul du NDWI2.")
    messInfo(dlg,"")
    
    rasterPath = dir_raster_src + os.sep + rasterName + extension_input_raster
    ndwi2Path = dir_dest + os.sep + ndwi2Name + EXT_RASTER
    
    # Test si c'est une image multibande
    cols, rows, bands = getGeometryImage(rasterPath)
    if bands < 4 :
        QMessageBox.information(None, "Attention !!!", ndwi2Path + " ne peut pas être créé. L'image rasterraster d'entrée  n'a pas un nombre de bande suffisant.", QMessageBox.Ok, QMessageBox.NoButton)         
        messErreur(dlg, ndwi2Path + " ne peut pas être créé.")
        return None
        
    # Selection des bandes pour le calcul du NDWI2
    num_channel_green = 0
    num_channel_nir = 0
    d = conf.channelOrderDic
    key = "Green"
    if key in conf.channelOrderDic.keys():
        num_channel_green = int(conf.channelOrderDic[key])
    key = "NIR"    
    if key in conf.channelOrderDic.keys():
        num_channel_nir = int(conf.channelOrderDic[key])
        
    if (num_channel_green == 0 or num_channel_nir == 0):
        QMessageBox.information(None, "Attention !!!", ndviPath + " ne peut pas être créé. NDVI needs Green and NIR channels to be computed).", QMessageBox.Ok, QMessageBox.NoButton)         
        messErreur(dlg, ndviPath + " ne peut pas être créé.")
        return None  
    
    # Suppression du fichier de sortie si il existe 
    if os.path.exists(ndwi2Path):
        try:
            os.remove(ndwi2Path)            
        except: 
            QMessageBox.information(None, "Attention !!!", ndwi2Path + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)         
            messErreur(dlg, ndwi2Path + " ne peut pas être effacé.")
            return None     

    # Calcul
    if conf.rbOTB.isChecked():    
        # Calculatrice raster OTB                        
        try:
            expression = '(im1b%s - im1b%s)/(im1b%s + im1b%s)' %(str(num_channel_green), str(num_channel_nir), str(num_channel_green), str(num_channel_nir))
            processing.algorithmHelp("otb:BandMath")
            #processing.runalg('otb:bandmath', rasterPath, '128',expression, ndwi2Path)
            parameters = {"il":[rasterPath], "out":ndwi2Path, "exp":expression, "outputpixeltype":2, "ram":128}
            processing.run('otb:BandMath', parameters)
        except:
            messErreur(dlg, "Erreur de traitement sur otb:BandMath ndwi2.")
            return None
        # Fin OTB
        
    else: 
        # Calculatrice raster QGIS
        entries = []
        
        raster = li[rasterName]
        extent = raster.extent()
        height = raster.height()
        width = raster.width()        

        b_green = QgsRasterCalculatorEntry()
        b_green.ref = 'b@%s' %(str(num_channel_green))
        b_green.raster = raster
        b_green.bandNumber = num_channel_green
        entries.append(b_green)

        b_nir = QgsRasterCalculatorEntry()
        b_nir.ref = 'b@%s' %(str(num_channel_nir))
        b_nir.raster = raster
        b_nir.bandNumber = num_channel_nir
        entries.append(b_nir)
                                 
        expression =  '(b@%s - b@%s)/(b@%s + b@%s)' %(str(num_channel_green), str(num_channel_nir), str(num_channel_green), str(num_channel_nir))
        calc = QgsRasterCalculator( expression, ndwi2Path, FORMAT_IMA, extent, width, height, entries )

        ret = calc.processCalculation()   
           
        if ret != 0:
            QMessageBox.information(None, "Attention !!!", " Erreur d'exécution, cela peut être du à une insuffisance mémoire, image trop volumineuse.", QMessageBox.Ok, QMessageBox.NoButton)
            messErreur(dlg,"Erreur lors du lancement de QgsRasterCalculator.")       
            return None
        # Fin QGIS
            
    if os.path.exists(ndwi2Path):
        ndwi2 = QgsRasterLayer(ndwi2Path, ndwi2Name)
    else:
        QMessageBox.information(None, "Attention !!!", ndwi2Path + " n'a pas été créé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)        
        messErreur(dlg, ndwi2Path + " n'a pas été créé.")
        return None             
        
    if not ndwi2.isValid():
        messErreur(dlg, ndwi2Path + " ne peut pas être chargé.")
        return None         

    return ndwi2

#########################################################################
# FONCTION despeckeleLee()                                              #
#########################################################################
def despeckeleLee(dlg, conf, dir_raster_src, dir_dest, rasterName, leeName, extension_input_raster): 

    # Calcul despeckele option Lee
    li = layerList()
    
    messInfo(dlg,"Calcul du despeckele Lee.")
    messInfo(dlg,"")
    
    rasterPath = dir_raster_src + os.sep + rasterName + extension_input_raster
    leePath = dir_dest + os.sep + leeName + EXT_RASTER
    radius = dlg.spinBoxRadius.value()
    nb_looks = dlg.doubleSpinBoxLooks.value()
        
    # Suppression du fichier de sortie si il existe 
    if os.path.exists(leePath):
        try:
            os.remove(leePath)            
        except: 
            QMessageBox.information(None, "Attention !!!", leePath + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)         
            messErreur(dlg, leePath + " ne peut pas être effacé.")
            return None     

    # Calcul
    if conf.rbOTB.isChecked():   
        try:
            #processing.algorithmHelp("otb:Despeckle")
            #processing.runalg('otb:despecklelee', rasterPath, '128', 0, radius, nb_looks, leePath)
            parameters = {"in":rasterPath, "out":leePath, "filter":'lee', "filter.lee.rad":radius, "filter.lee.nblooks":nb_looks, "outputpixeltype":2, "ram":128}
            processing.run('otb:Despeckle', parameters)
        except:
            messErreur(dlg, "Erreur de traitement sur otb:Despeckle Lee.")
            return None
        # Fin OTB
        
    else: 
        # Despeckele Lee par GRASS
        entries = []
        raster = li[rasterName]
        extent = raster.extent()
        height = raster.height()
        width = raster.width()   

        try:
            # En attente de faire fonctionner le despeckle avec GRASS !!!
            print("DEBUG  lancement grass:despeckle Lee")
            processing.algorithmHelp("grass:i.despeckle")
            #processing.runalg('grass7:i.despeckle', rasterPath, 'lee', radius, nb_looks, leePath)
            print("DEBUG  fin grass:despeckle Lee")
        except:
            messErreur(dlg,"Erreur de traitement sur grass:despeckle.")
            return None
        # Fin GRASS            
 
    if os.path.exists(leePath):
        lee = QgsRasterLayer(leePath, leeName)
    else:
        QMessageBox.information(None, "Attention !!!", leePath + " n'a pas été créé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)        
        messErreur(dlg, leePath + " n'a pas été créé.")
        return None             
        
    if not lee.isValid():
        messErreur(dlg, leePath + " ne peut pas être chargé.")
        return None         

    return lee

#########################################################################
# FONCTION despeckeleGamma()                                            #
#########################################################################
def despeckeleGamma(dlg, conf, dir_raster_src, dir_dest, rasterName, gammaName, extension_input_raster): 
 
    # Calcul despeckele option Gamma
    li = layerList()
    
    messInfo(dlg,"Calcul du despeckele Gamma.")
    messInfo(dlg,"")
    
    rasterPath = dir_raster_src + os.sep + rasterName + extension_input_raster
    gammaPath = dir_dest + os.sep + gammaName + EXT_RASTER
    radius = dlg.spinBoxRadius.value()
    nb_looks = dlg.doubleSpinBoxLooks.value()
    
    # Suppression du fichier de sortie si il existe    
    if os.path.exists(gammaPath):
        try:
            os.remove(gammaPath)            
        except: 
            QMessageBox.information(None, "Attention !!!", gammaPath + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)         
            messErreur(dlg, gammaPath + " ne peut pas être effacé.")
            return None     

    # Calcul
    if conf.rbOTB.isChecked():    
        # Despeckele Gamma par OTB
        try:
            #processing.algorithmHelp("otb:Despeckle")
            #processing.runalg('otb:despecklegammamap', rasterPath, '128', 0, radius, nb_looks, gammaPath)
            parameters = {"in":rasterPath, "out":gammaPath, "filter":'gammamap', "filter.gammamap.rad":radius, "filter.gammamap.nblooks":nb_looks, "outputpixeltype":2, "ram":128}
            processing.run('otb:Despeckle', parameters)
        except:
            messErreur(dlg,"Erreur de traitement sur otb:Despeckle Gamma.")
            return None
        # Fin OTB
        
    else: 
        # Despeckele Gamma par GRASS
        entries = []
        
        raster = li[rasterName]
        extent = raster.extent()
        height = raster.height()
        width = raster.width()
        
        try:
            # En attente de faire fonctionner le despeckle avec GRASS !!!
            print("DEBUG  lancement grass:despeckle Gamma")
            processing.algorithmHelp("grass:i.despeckle")
            #processing.runalg('grass:i.despeckle', rasterPath, 'gamma', radius, nb_looks, gammaPath)
            print("DEBUG  fin grass:despeckle Gamma")
        except:
            messErreur(dlg, "Erreur de traitement sur grass:despeckle.")
            return None   
        # Fin GRASS
        
    if os.path.exists(gammaPath):
        gamma = QgsRasterLayer(gammaPath, gammaName)
    else:
        QMessageBox.information(None, "Attention !!!", gammaPath + " n'a pas été créé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)        
        messErreur(dlg, gammaPath + " n'a pas été créé.")
        return None             
        
    if not gamma.isValid():
        messErreur(dlg, gammaPath + " ne peut pas être chargé.")
        return None         

    return gamma

#########################################################################
# FONCTION computeMaskThreshold()                                       #
#########################################################################    
def computeMaskThreshold(dlg, conf, dir_raster_treat, dir_dest, rasterTreatName, rasterSeuilName, seuilStr, deltaStr, extension_input_raster):  
    
    # Calcul du masque d'eau fonction du seuil choisi        
    seuil = float(seuilStr)
    if not dlg.rbSeuil.isChecked():
        delta = 0
        values_seuil_list = [0]
    else:
        delta = float(deltaStr)
        values_seuil_list = [-1, 0, +1]       
                        
    messInfo(dlg,"Seuil: " + seuilStr)
    messInfo(dlg,"")  

    if dlg.rbComputeNdvi.isChecked():
        direction = True
    elif dlg.rbComputeNdwi2.isChecked():    
        direction = False
    else:
        direction = True
        
    if direction :
        direction_operator_str = "<"   # Operateur inferieur
    else :    
        direction_operator_str = ">"   # Operateur superieur
        
    if conf.rbOTB.isChecked(): 
        # Calculatrice OTB                                
        init = 41253
    else:
        # Calculatrice QGIS
        init = 32526    
        
    masks_list = []    
    for i in values_seuil_list :
        newSeuil = seuil + i*delta
        
        if float(newSeuil) == 0:
            newSeuilStr = '0'
            newSeuil10Str = '0'
        else:
            newSeuilStr = str(newSeuil)
            newSeuil10Str = str(newSeuil*10)
            while newSeuilStr[0] == '0' and len(newSeuilStr) >= 2 and newSeuilStr[1] != '.' :
                newSeuilStr = newSeuilStr[1:]
            if '.' in newSeuilStr :
                while newSeuilStr[-1] == '0': 
                    newSeuilStr = newSeuilStr[:len(newSeuilStr)-1]
                if  newSeuilStr[-1] == '.':           
                    newSeuilStr = newSeuilStr[:len(newSeuilStr)-1]
            
        if newSeuil != init:
            init = newSeuil
            
            if delta == 0:
                layerSeuilName = rasterSeuilName + seuilStr
            else:
                layerSeuilName = rasterSeuilName + newSeuilStr
                    
            layerSeuilPath = dir_dest + os.sep + layerSeuilName + EXT_RASTER
                        
            if os.path.exists(layerSeuilPath):
                try:
                    os.remove(layerSeuilPath)
                except: 
                    QMessageBox.information(None, "Attention !!!", layerSeuilPath + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)                    
                    messErreur(dlg, layerSeuilPath + " ne peut pas être effacé.")
                    return None                
        
            messInfo(dlg, "Calcul du masque 'Eau' avec le seuil: " + newSeuilStr)
            messInfo(dlg, "")
            
            # Calculatrice OTB 
            if conf.rbOTB.isChecked():
                rasterTreatPath = dir_raster_treat + os.sep + rasterTreatName + extension_input_raster            
                try:
                    expression = 'im1b1' + direction_operator_str + newSeuilStr + '?1:2'
                    #processing.algorithmHelp("otb:BandMath") 
                    #processing.runalg('otb:bandmath', rasterTreatPath, '128',expression ,layerSeuilPath)
                    parameters = {"il":[rasterTreatPath], "out":layerSeuilPath, "exp":expression, "outputpixeltype":2, "ram":128}
                    processing.run('otb:BandMath', parameters)                  
                except:               
                    messErreur(dlg, "Erreur lors du lancement de otb:BandMath seuillage.")
                    return None
            # Fin OTB
            
            # Calculatrice QGIS             
            else:
                entries = []
                li = layerList()
                raster = li[rasterTreatName]         
                extent = raster.extent()
                height = raster.height()
                width = raster.width()                    

                s1 = QgsRasterCalculatorEntry()
                s1.ref = 's@1'
                s1.raster = raster
                s1.bandNumber = 1
                entries.append(s1)                        
    
                if platform.system()=="Linux":
                    # Bug calculatrice raster sous linux
                    calc = QgsRasterCalculator( '(10*s@1' + direction_operator_str + newSeuil10Str + ')', layerSeuilPath, FORMAT_IMA, extent, width, height, entries )
                    
                else:
                    calc = QgsRasterCalculator( '(s@1' + direction_operator_str + newSeuilStr + ')', layerSeuilPath, FORMAT_IMA, extent, width, height, entries )
                
                ret = calc.processCalculation()   
                if ret != 0:
                    QMessageBox.information(None, "Attention !!!", " Erreur d'exécution, cela peut être du à une insuffisance mémoire, image trop volumineuse.", QMessageBox.Ok, QMessageBox.NoButton)
                    messErreur(dlg, "Erreur de traitement sur QgsRasterCalculator.")              
                    return None
            # Fin QGIS  
            
            if os.path.exists(layerSeuilPath):
                mask = QgsRasterLayer(layerSeuilPath, layerSeuilName)
            else:
                QMessageBox.information(None, "Attention !!!", layerSeuilPath + " n'a pas été créé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)                      
                messErreur(dlg, layerSeuilPath + " n'a pas été créé.")
                return None
        
            if not mask.isValid():
                messErreur(dlg, layerSeuilPath + " ne peut pas être chargé.")
                return None                         
        
            # Add list pour return
            masks_list.append(mask)    
    
    return masks_list

#########################################################################
# FONCTION filterRaster()                                               #
#########################################################################
def filterRaster(dlg, conf, dir_dest, rasterSeuilName, rasterFilterName):

    # Filtre que l'on propose pour éliminer les zones d'eau mineures
    li = layerList()    
    layerSeuil = li[rasterSeuilName]
    layerSeuilPath = dir_dest + os.sep + rasterSeuilName + EXT_RASTER
    layerFiltreIlotsPath = dir_dest + os.sep + rasterFilterName + EXT_RASTER
        
    for elem in li:
        if elem == rasterFilterName:
            QgsProject.instance().removeMapLayer(li[elem].id())
                    
    if os.path.exists(layerFiltreIlotsPath):
        try:
            os.remove(layerFiltreIlotsPath)
        except: 
            QMessageBox.information(None, "Attention !!!", layerFiltreIlotsPath + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)         
            messErreur(dlg, layerFiltreIlotsPath + " ne peut pas être effacé.")
            return None           
            
    # Filtrage OTB 
    if conf.rbOTB.isChecked(): 

        seuilCMR = dlg.seuilCMR.text()
        if seuilCMR == '':
            QMessageBox.information(None, "Attention !!!", "Valeur de radius incorrecte !", QMessageBox.Ok, QMessageBox.NoButton)
            return None   
        try: 
            seuilCMR = int(seuilCMR)
        except:
            QMessageBox.information(None, "Attention !!!", "Valeur de radius incorrecte !", QMessageBox.Ok, QMessageBox.NoButton)
            return None
        if not 0 <= int(seuilCMR) <= 30:
            QMessageBox.information(None, "Attention !!!", "Valeur de radius incorrecte !", QMessageBox.Ok, QMessageBox.NoButton)
            return None
 
        messInfo(dlg, "Lancement du filtre 'Classification Map Regularization' sur le raster: " + rasterSeuilName)
        messInfo(dlg, "Radius: " + str(seuilCMR))
        messInfo(dlg, "")

        try:
            #processing.algorithmHelp("otb:ClassificationMapRegularization")
            #processing.runalg('otb:classificationmapregularization', layerSeuilPath, seuilCMR, True, 0, 0, False, 0, 128, layerFiltreIlotsPath)
            parameters = {"io.in":layerSeuilPath, "io.out":layerFiltreIlotsPath, "ip.radius":seuilCMR, "ip.suvbool":True, "ip.nodatalabel":0, "ip.undecidedlabel":0, "ip.onlyisolatedpixels":False, "ip.isolatedthreshold":0,  "outputpixeltype":2, "ram":128}
            processing.run('otb:ClassificationMapRegularization', parameters)
        except:
            messErreur(dlg, "Erreur de traitement par (filtre Classification Map Regularization) de %s !!!" %(layerFiltreIlotsPath)) 
            return None
    # Fin OTB
            
    # Filtrage QGIS (Gdal)            
    else:
    
        seuilTamiser = dlg.seuilTamiser.text()
        if seuilTamiser == '':
            QMessageBox.information(None, "Attention !!!", "Valeur de seuil incorrecte !", QMessageBox.Ok, QMessageBox.NoButton)
            return None   
        try: 
            seuilTamiser = int(seuilTamiser)
        except:
            QMessageBox.information(None, "Attention !!!", "Valeur de seuil incorrecte !", QMessageBox.Ok, QMessageBox.NoButton)
            return None
        if not 0 <= int(seuilTamiser) < 10000:
            QMessageBox.information(None, "Attention !!!", "Valeur de seuil incorrecte !", QMessageBox.Ok, QMessageBox.NoButton)
            return None
            
        if dlg.rbTamiser4.isChecked():
            conn = False
        else:
            conn = True
            
        messInfo(dlg, "Lancement du filtrage sur le raster: " + rasterSeuilName)
        messInfo(dlg,"Seuil: " + str(seuilTamiser))
        messInfo(dlg,"")
        
        try:
            #processing.algorithmHelp("gdal:sieve")
            #processing.runalg('gdalogr:sieve', layerSeuil,seuilTamiser,conn,layerFiltreIlotsPath)
            parameters = {"INPUT":layerSeuil, "THRESHOLD":seuilTamiser, "EIGHT_CONNECTEDNESS":conn, "NO_MASK":True, "MASK_LAYER":"", "OUTPUT":layerFiltreIlotsPath}
            processing.run('gdal:sieve', parameters)
        except:
            messErreur(dlg, "Erreur de traitement par gdal:sieve (filtre) de %s !!!"%(layerFiltreIlotsPath))
            return None
    # Fin QGIS
    
     # Test si le filtrage à reussi  
    if os.path.exists(layerFiltreIlotsPath):
        layer = QgsRasterLayer(layerFiltreIlotsPath, rasterFilterName)
    else:
        QMessageBox.information(None, "Attention !!!", layerFiltreIlotsPath + " n'a pas été créé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)     
        messErreur(dlg, layerFiltreIlotsPath + " n'a pas été créé.")
        return None    
    
    if not layer.isValid():
        messErreur(dlg, layerFiltreIlotsPath + " ne peut pas être chargé.")
        return None
               
    return layer

#########################################################################
# FONCTION polygonizeRaster()                                           #
#########################################################################
def polygonizeRaster(dlg, dir_dest, rasterToPolygonizeName, vectorPolygonName):

    # Fonction de vectorisation
    li = layerList()
    rasterToPolygonize = li[rasterToPolygonizeName]
                        
    messInfo(dlg,"Vectorisation du raster: " + rasterToPolygonizeName)
    messInfo(dlg,"")    
    
    outputVectorPath = dir_dest + os.sep + vectorPolygonName + EXT_VECTOR
              
    if os.path.exists(outputVectorPath):
        try:
            os.remove(outputVectorPath)
        except:            
            QMessageBox.information(None, "Attention !!!", outputVectorPath + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement.", QMessageBox.Ok, QMessageBox.NoButton)
            messErreur(dlg, outputVectorPath  + " ne peut pas être effacé.")
            return None
        
    if rasterToPolygonize:
        try:
            #processing.algorithmHelp("gdal:polygonize")
            #processing.runandload('gdalogr:polygonize', rasterToPolygonize,'DN',  outputVectorPath)
            parameters = {"INPUT":rasterToPolygonize, "BAND":1, "FIELD":'DN', "EIGHT_CONNECTEDNESS":False, "OUTPUT":outputVectorPath}
            processing.run('gdal:polygonize', parameters)
        except:
            messErreur(dlg, "Erreur pendant l'exécution de gdal:polygonize.")
            return None
    else:
        messErreur(dlg, "fin de traitement sur gdal:polygonize, " + rasterToPolygonizeName + " n'est pas valide.")
        return None     
       
    # Test si la vectorisation à reussi    
    if os.path.exists(outputVectorPath):
        layer = QgsVectorLayer(outputVectorPath, vectorPolygonName, "ogr")
    else:
        QMessageBox.information(None, "Attention !!!", outputVectorPath + " n'a pas été créé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)     
        messErreur(dlg, outputVectorPath + " n'a pas été créé.")
        return None   
    
    if not layer.isValid():
        messErreur(dlg, outputVectorPath + " ne peut pas être chargé.")
        return None
    
    messInfo(dlg, "Fin vectorisation du raster: " + rasterToPolygonizeName)
    messInfo(dlg, "") 
    
    return layer
    