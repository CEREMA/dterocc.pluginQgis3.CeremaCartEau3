# -*- coding: utf-8 -*-
"""
/***************************************************************************
 traitement
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
from PyQt5.QtCore import QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox

from qgis.gui import *
from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsProject, QgsGeometry, QgsVectorFileWriter, QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer, QgsWkbTypes, QgsFields, QgsField, QgsPointXY, QgsFeature, QgsMapLayer
from qgis.PyQt.QtCore import QVariant

from osgeo import gdal, ogr,osr
import os
import time

from .tools import EXT_RASTER, EXT_VECTOR, FORMAT_VECT, EXT_IMAGES_LIST, messInfo, messErreur, layerList, setLayerVisible
from .processingRaster import computeNdvi, computeNdwi2, despeckeleLee, despeckeleGamma, computeMaskThreshold, filterRaster, polygonizeRaster
from .assembly import assembleRasters

#########################################################################
# FONCTION loadRaster()                                                 #
#########################################################################
def loadRaster(dlg, path, layerName):	

    # Chargement d'un raster dans QGIS
    layer = QgsRasterLayer(path, layerName)
    if not layer.isValid():
        messErreur(dlg,layerName + " ne peut pas être chargé.")
        return

    QgsProject.instance().addMapLayer(layer)
    messInfo(dlg,"Le fichier raster " + layerName + " a été correctement chargé.")
    messInfo(dlg, "")
    ContrastEnhancement = QgsContrastEnhancement.StretchToMinimumMaximum
    layer.setContrastEnhancement(ContrastEnhancement,QgsRaster.ContrastEnhancementCumulativeCut)
    layer.triggerRepaint()          
    return layer

#########################################################################
# FONCTION loadShapeFromDir()                                           #
#########################################################################    
def loadShapeFromDir(dlg, path, layerName):

    # Chargement d'un fichier Shape dans QGIS
    layer = QgsVectorLayer(path, layerName, "ogr")
    if not layer.isValid():
        messErreur(dlg, layerName + " ne peut pas être chargé.")
        return

    QgsProject.instance().addMapLayer(layer)
    layer.triggerRepaint() 
    return layer

#########################################################################
# FONCTION geUserManuel()                                               #
#########################################################################    
def geUserManuel():

    TEXT_USER_MANUAL = "Ce plugin Qgis Cart'Eau a été développé dans le cadre d'un projet API pour le Symsagel (Syndicat Mixte de Gestion des Eaux du Bassin de la Lys), pour détecter les zones en eau à partir d'images satellites et fournir un vecteur de contour des zones en eau extrait des images en sortie. \
    \n\nLa méthode repose sur le principe de seuillage radiométrique (seuil maximum pour tous les cas sauf pour le NDWI2). \
    \n\nLe plugin permet de traiter des images satellites optique ou radar (à déterminer dans l'onglet Configuration). \
    \n\n\nLe plugin présente également en option: \
    \n\n- une étape permettant de rechercher une ou plusieurs images disponibles sur une emprise géographique fournie et de les assembler. Cette étape est utile pour assembler des imagettes issues d'une même image afin de reconstituer l'image source (cas des images Pléiades livrées par IGN). Il est déconseillé de l'utiliser pour des acquisitions différentes. \
    \n\n- une étape de prétraitement des images pour faciliter l'extraction des zones en eau : calcul d'indices radiométriques pour les images optiques (NDVi, NDWI2), ou despeckle pour les images radar (NB : les images radar se sont ni orthorectifiées ni calibrées dans ce plugin. Cela peut être fait auparavant dans SNAP) \
    \n\n- une étape de filtrage permettant de filtrer les zones en eau constituées de pixels isolés. \
    \n\nDeux outils peuvent être mobilisés grâce à l'onglet Configuration : les outils OTB ou Qgis. La configuration OTB est indipensable pour l'étape de Despeckle pour les images Radar. Sinon, les 2 configurations sont possibles dans les autres cas. Ce qui diffère ce sont les calculs d'indices (calculatrice raster QGIS et BandMath OTB) et les filtres (filtre gdal_sieve en configuation Qgis et filtre majoritaire en configuration OTB)"
    return TEXT_USER_MANUAL 
        
#########################################################################
# FONCTION runAssemble()                                                #
#########################################################################        
def runAssemble(iface, dlg, conf, assb, fromActiveLayerVector, fromActiveLayerAssembled):

    #  Choix du filtre sur les extensions       
    if  conf.rbOptique.isChecked() :
        ext_list = EXT_IMAGES_LIST
    else :
        ext_list = EXT_IMAGES_LIST  
        
    li = layerList()
   
    # Test la liste des répertoires sources
    repRasterAssemblyList = []
    nbRep = assb.clayer_dir_src.count()
    
    if nbRep == 0:
        QMessageBox.information(None, "Attention !!!", "La liste des répertoires de recherche des rasteurs est vide!", QMessageBox.Ok, QMessageBox.NoButton)
        return ""
        
    for repIndex in range(nbRep):
        rep = assb.clayer_dir_src.itemText(repIndex)
        rep = rep.replace('\\',os.sep)
        if not os.path.isdir(rep):
            QMessageBox.information(None, "Attention !!!", "Le répertoire %s est inexistant ou incorrect !"%(rep), QMessageBox.Ok, QMessageBox.NoButton)
            return ""
        else :
            repRasterAssemblyList.append(rep)

    # Selection du vecteur d'emprise        
    empriseZone = ""
    ficVector = assb.clayer_vector.currentText().replace('\\',os.sep)

    if ficVector == "":
        QMessageBox.information(None, "Attention !!!", "Le fichier vecteur d'emprise est inexistant ou non défini !", QMessageBox.Ok, QMessageBox.NoButton)
        return ""
        
    if fromActiveLayerVector and (ficVector in li) :
        layerVector = li[ficVector]
        empriseZone = layerVector.dataProvider().dataSourceUri().split("|")[0]
    else:
        empriseZone = ficVector
         
    # verification du vecteur    
    if not os.path.isfile(empriseZone) :
        messErreur(dlg, " Le fichier d'emprise %s ne peut pas être chargé, fichier inexistant ou incorrect."%(ficVector))
        QMessageBox.information(None, "Attention !!!", "Le fichier vecteur d'emprise est inexistant ou incorrect !", QMessageBox.Ok, QMessageBox.NoButton)
        return ""    

    # Selection du raster resultat de fusion
    ficAssembled = assb.clayer_assembled.currentText()
    rasterAssembly = ""
    
    if fromActiveLayerAssembled:
        if ficAssembled in li :
            layerRaster = li[ficAssembled]
            rasterAssembly = layerRaster.dataProvider().dataSourceUri()
        else :
            QMessageBox.information(None, "Attention !!!", "Le raster assemblé " + ficAssembled + " n'existe pas (ou plus) dans la liste des couches disponibles. Vérifiez réininitialisé la liste des couches d'entrée ou selectionner un fichier raster de sortie.", QMessageBox.Ok, QMessageBox.NoButton)        
            messErreur(dlg, "Le raster " + ficAssembled + " n'existe pas dans la liste des rasters de destination.")
            return ""      
    else: 
        rasterAssembly = ficAssembled
    extension_input_raster = os.path.splitext(os.path.basename(rasterAssembly))[1]
    
    # verification du nom du fichier raster
    if rasterAssembly == "" :
        QMessageBox.information(None, "Attention !!!", "Le fichier raster est inexistant ou incorrect ou le format n'est pas supporté par le plugin !", QMessageBox.Ok, QMessageBox.NoButton)
        return ""
   
    if os.path.isfile(rasterAssembly) :
        messErreur(dlg, "Le fichier d'assemblage %s existe déjà, définir un autre nom de fichier."%(rasterAssembly))
        return ""
    
    # Assemblage des rasters
    messInfo(dlg, "Assemblage des rasters des répertoires séléctionnés en cours..." )
    messInfo(dlg, "")
    
    if assembleRasters(dlg, empriseZone, repRasterAssemblyList, ext_list, rasterAssembly) < 0 :
        messErreur(dlg, "Erreur l'assemblage des rasters a échoué" )
    else :
        messInfo(dlg, "Assemblage des rasters terminé" )
        messInfo(dlg,"")
           
    return rasterAssembly
    
#########################################################################
# FONCTION runThresholding()                                            #
#########################################################################        
def runThresholding(iface, dlg, conf, layersName, dir_raster_src, dir_dest, ficRaster, seuilStr, fromActiveLayerRaster):

    # Recuperation du chemin compler du fichier raster source
    if fromActiveLayerRaster:
            if ficRaster == "":
                QMessageBox.information(None, "Attention !!!", "Le fichier raster est inexistant ou incorrect ou le foramt n'est pas supporté par le plugin !", QMessageBox.Ok, QMessageBox.NoButton)
                return None
    else:
        if os.path.isfile(ficRaster):
            try:
                dir_raster_src.decode('ascii')
                dir_dest.decode('ascii')
            except:
                QMessageBox.information(None, "Attention !!!", "Certaines fonctions comme gdal_polygonize n'acceptent pas les dossiers avec des caractères accentués. Le chemin d'accès au fichier raster n'est pas valable.", QMessageBox.Ok, QMessageBox.NoButton)
                return None
            if platform.system() == "Linux" and conf.rbOTB.isChecked():
                try:
                    ficRaster.decode('ascii')
                except:
                    QMessageBox.information(None, "Attention !!!", "Certaines fonctions comme Band Math (OTB) n'acceptent pas les caractères accentués. Le nom du raster n'est pas valable.", QMessageBox.Ok, QMessageBox.NoButton)
                    return None
        else :
            QMessageBox.information(None, "Attention !!!", "Le fichier raster est inexistant ou incorrect ou le foramt n'est pas supporté par le plugin !", QMessageBox.Ok, QMessageBox.NoButton)
            return None

    if dlg.rbSeuil.isChecked():
            if dlg.delta.text() in ('','+','-') or float(dlg.delta.text()) == 0:
                QMessageBox.information(None, "Attention !!!", "Valeur de delta incorrecte !", QMessageBox.Ok, QMessageBox.NoButton)
                dlg.delta.setFocus()
                return None
                    
    # On lance le seuillage
    messInfo(dlg, "Seuillage en cours..." )
    messInfo(dlg, "")
    
    canvas = iface.mapCanvas()
    li = layerList()
    
    # Nom du fichier raster
    if fromActiveLayerRaster:
        if ficRaster in li :
            layerRaster = li[ficRaster]
            rasterAssembly = layerRaster.dataProvider().dataSourceUri()
        else :
            QMessageBox.information(None, "Attention !!!", ficRaster + " n'existe plus dans la liste des couches disponible. Vérifiez réininitialisé la liste des couches d'entrée.", QMessageBox.Ok, QMessageBox.NoButton)        
            messErreur(dlg, ficRaster + " n'existe plus dans la liste.")
            return None      
        
    else: 
        rasterAssembly = ficRaster
    extension_input_raster = os.path.splitext(os.path.basename(rasterAssembly))[1]  
    messInfo(dlg, "Raster en entrée: " + layersName['raster'])
    
    li = layerList()
    canvas.refresh()
    
    # Variables
    global start_time
    raster = None

    # récupération du nom de base pour les fichiers temporaires et du répertoire de travail
    if fromActiveLayerRaster:
        if layersName['raster'] in li:
            raster = li[layersName['raster']]          
    else: 
        raster = loadRaster(dlg,ficRaster,layersName['raster'])    
    
    if not raster:
        messErreur(dlg, "Le raster ne peut pas être chargé.")   
        return None
          
    start_time = time.time()
        
    setLayerVisible(raster, True)

    # Création d'une couche vectorielle sur l'emprise du raster
    # Va permettre d'éliminer ultérieurement les bords du cadre lors de la recherche des contours
    LayerRasterExtendName = layersName['emprise']
    LayerRasterExtendPath = dir_dest + os.sep + LayerRasterExtendName + EXT_VECTOR
    
    if os.path.exists(LayerRasterExtendPath):
        try:
            os.remove(LayerRasterExtendPath)
        except: 
            QMessageBox.information(None, "Attention !!!", LayerRasterExtendPath + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)
            messErreur(dlg, LayerRasterExtendPath + " ne peut pas être effacé.")
            return None  
    
    messInfo(dlg, "Création de la couche: " + LayerRasterExtendName + ".")
    messInfo(dlg, "")

    crs = raster.crs()
    crsWkt = crs.toWkt()
    layerExtend = QgsVectorLayer("Polygon?crs=" + crsWkt, LayerRasterExtendName, "memory")
    
    if not layerExtend.isValid():
        messErreur(dlg, LayerRasterExtendPath + " ne peut pas être chargé.")
        return None  

    QgsProject.instance().addMapLayer(layerExtend)

    li = layerList()
    symbol = li[LayerRasterExtendName].renderer().symbol()
    symbol.setColor(QColor.fromRgb(0,0,255))
    symbol.setOpacity(0.4)
    
    provider = li[LayerRasterExtendName].dataProvider()
       
    fields = QgsFields()
    fields.append( QgsField( "HEIGHT", QVariant.Double ) )
    fields.append( QgsField( "WIDTH", QVariant.Double ) )

    for f in fields:
        provider.addAttributes([f])

    writer = QgsVectorFileWriter(LayerRasterExtendPath, "CP1250", fields, QgsWkbTypes.Polygon, crs, FORMAT_VECT)
    if writer.hasError() != QgsVectorFileWriter.NoError:
        messErreur(dlg, LayerRasterExtendPath + " ne peut pas être créé.")    
        return None 
        
    li[LayerRasterExtendName].startEditing()
     
    extent = raster.extent()
    minx = extent.xMinimum()
    miny = extent.yMinimum()
    maxx = extent.xMaximum()
    maxy = extent.yMaximum()
    height = raster.height()
    width = raster.width()
    cntx = minx + ( width / 2.0 )
    cnty = miny + ( height / 2.0 )
    area = width * height
    perim = ( 2 * width ) + (2 * height )
    rect = [ QgsPointXY( minx, miny ),
             QgsPointXY( minx, maxy ),
             QgsPointXY( maxx, maxy ),
             QgsPointXY( maxx, miny ),
             QgsPointXY( minx, miny ) ]
    geometry = QgsGeometry().fromPolygonXY( [ rect ] )
    feat = QgsFeature()
    feat.setGeometry( geometry )
    feat.setAttributes( [ height,width ] )
    writer.addFeature( feat )    
    provider.addFeatures([feat])
    del writer
        
    li[LayerRasterExtendName].commitChanges()
    setLayerVisible(li[LayerRasterExtendName], False)
          
    node = QgsProject.instance().layerTreeRoot().findLayer(li[LayerRasterExtendName].id())
    iface.layerTreeView().layerTreeModel().refreshLayerLegend(node)
    li[LayerRasterExtendName].triggerRepaint() 
    canvas.refresh()
    rasterTreatName = ""
    
    # Cas du traitement d'une image optique     
    if conf.rbOptique.isChecked():
    
        # Calcul du NDVI
        if dlg.rbComputeNdvi.isChecked():
            rasterTreatName = layersName['ndvi']
            dir_raster_treat = dir_dest        
            layer = computeNdvi(dlg, conf, dir_raster_src, dir_dest, layersName["raster"], layersName["ndvi"], extension_input_raster)       
            if layer is None :
                return None

            QgsProject.instance().addMapLayer(layer)
            setLayerVisible(layer, False)    
            extension_input_raster = EXT_RASTER    
        
        # Calcul du NDWI2
        elif dlg.rbComputeNdwi2.isChecked():
            rasterTreatName = layersName['ndwi2']
            dir_raster_treat = dir_dest          
            layer = computeNdwi2(dlg, conf, dir_raster_src, dir_dest, layersName["raster"], layersName["ndwi2"], extension_input_raster)       
            if layer is None :
                return None
                
            QgsProject.instance().addMapLayer(layer)
            setLayerVisible(layer, False)    
            extension_input_raster = EXT_RASTER
            
        else:
            rasterTreatName = layersName['raster']
            dir_raster_treat = dir_raster_src
     
    # Cas du traitement d'une image radar
    elif conf.rbRadar.isChecked():    
        
        # Despeckele Lee
        if dlg.rbDespeckLee.isChecked():
            rasterTreatName = layersName['lee']
            dir_raster_treat = dir_dest          
            layer = despeckeleLee(dlg, conf, dir_raster_src, dir_dest, layersName["raster"], layersName["lee"], extension_input_raster)       
            if layer is None :
                return None
                
            QgsProject.instance().addMapLayer(layer)
            setLayerVisible(layer, False)  
            extension_input_raster = EXT_RASTER
        
        # Despeckele Gamma
        elif dlg.rbDespeckGamma.isChecked():
            rasterTreatName = layersName['gamma']
            dir_raster_treat = dir_dest
            layer = despeckeleGamma(dlg, conf, dir_raster_src, dir_dest, layersName["raster"], layersName["gamma"], extension_input_raster)       
            if layer is None :
                return None
                
            QgsProject.instance().addMapLayer(layer)
            setLayerVisible(layer, False)    
            extension_input_raster = EXT_RASTER  
        else:
            rasterTreatName = layersName['raster']
            dir_raster_treat = dir_raster_src
            
    li = layerList()
    
    # Calcul du masque d'eau à partir du seuil estimé
    deltaStr = dlg.delta.text()
    layers_list = computeMaskThreshold(dlg, conf, dir_raster_treat, dir_dest, rasterTreatName, layersName['seuil'], seuilStr, deltaStr, extension_input_raster)
    if layers_list is None:
        return None
         
    # Informations de style
    for layer in layers_list :
        QgsProject.instance().addMapLayer(layer)
        fcn = QgsColorRampShader()
        fcn.setColorRampType(QgsColorRampShader.Type.Exact)
        lst = [QgsColorRampShader.ColorRampItem(1, QColor(QColor(0,0,255)))]
        fcn.setColorRampItemList(lst)
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(fcn)
        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1, shader)
        if renderer:
            layer.setRenderer(renderer)
            if layer.renderer():
                layer.renderer().setOpacity(0.5)
        layer.triggerRepaint()
        setLayerVisible(layer, False)         
    
    li = layerList()
    messInfo(dlg,"Temps de calcul:  " + str(round(time.time() - start_time)) + " secondes.")
    messInfo(dlg,"") 
    
    global start_timeVect
    start_timeVect = time.time()    
         
    layerName = li[layersName['raster']]
    setLayerVisible(layerName, False)

    layerSeuilName = layersName['seuil'] + seuilStr
    layerSeuil = li[layerSeuilName]
    setLayerVisible(layerSeuil, True)
    
    li[layersName['raster']].triggerRepaint() 
    canvas.refresh() 
    extent = li[layersName['raster']].extent()
    canvas.setExtent(extent)

    # Retour avec le bon nom du fichier seuillé
    layersName['seuil'] = layerSeuilName
    
    return layersName

#########################################################################
# FONCTION runFilter()                                                  #
#########################################################################
def runFilter(iface, dlg, conf, dir_dest, rasterSeuilName, rasterFilterName):

    # Passage des parametres pour le filtrage
    layer = filterRaster(dlg, conf, dir_dest, rasterSeuilName, rasterFilterName)
    
    if layer != None :
        # Informations de style
        canvas = iface.mapCanvas()
        
        QgsProject.instance().addMapLayer(layer)
        fcn = QgsColorRampShader()
        fcn.setColorRampType(QgsColorRampShader.Type.Exact)
        lst = [QgsColorRampShader.ColorRampItem(1, QColor(QColor(255,177,67)))]
        fcn.setColorRampItemList(lst)
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(fcn)
        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1, shader)
        if renderer:
            layer.setRenderer(renderer)
            if layer.renderer():
                layer.renderer().setOpacity(0.5)
                
        layer.triggerRepaint()
        setLayerVisible(layer, True)    
                    
        canvas.refresh()

        messInfo(dlg, "---> Lancez 'Filtrer' (fonction du radius choisi) pour appliquer un nouveau filtrage ou  'Vectoriser' pour poursuivre le traitement.  <---" )
        messInfo(dlg, "")    
        QMessageBox.information(None, "Traitement de filtrage", " Filtrage terminé.          ", QMessageBox.Ok, QMessageBox.NoButton) 
    
    return 
    
#########################################################################
# FONCTION runVectorize()                                               #
#########################################################################    
def runVectorize(iface, dlg, assb, dir_dest, layersName, seuilStr):

    # Les paramètres du filtre (on peut le relancer) sont validés
    li = layerList()
    dlg.btFilter.setEnabled(False)  
    
    if layersName['filtre'] in li:
        rasterToPolygonizeName = layersName['filtre']
    else:
        if layersName['seuil'] in li:
            rasterToPolygonizeName = layersName['seuil']
        else:
            messErreur(dlg, "Pas de couche raster à vectoriser.")
            return 
            
    # Polygonisation        
    layer = polygonizeRaster(dlg, dir_dest, rasterToPolygonizeName, layersName['polygonize'])
    
    if layer != None :
        canvas = iface.mapCanvas()
        QgsProject.instance().addMapLayer(layer)
    
        # Informations de style
        symbol = layer.renderer().symbol()
        symbol.setColor(QColor.fromRgb(207,224,222))
        symbol.setOpacity(0.2)
        setLayerVisible(layer, True)
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        iface.layerTreeView().layerTreeModel().refreshLayerLegend(node)
        layer.triggerRepaint() 
        
        canvas.setCurrentLayer(layer)
        canvas.refresh()        
                    
        # Mise a jour de la couche vecteur crée dans Qgqis                            
        if layersName['filtre'] in li:
            layerName = layersName['seuil'] + seuilStr
            if layerName in li:
                setLayerVisible(li[layerName], False)
        else:
            layerName = layersName['seuil'] + seuilStr
            if layerName in li:
                setLayerVisible(li[layerName], True)             
            
        extent = li[layersName['raster']].extent()
        canvas.setExtent(extent)   
    
    messInfo(dlg,"Temps de vectorisation:  " + str(round(time.time() - start_timeVect)) + " secondes.")
    messInfo(dlg,"")      
    
    # Pour les zones d'eau on poursuit directement en vectorisant toutes les parcelles inondées après filtrage s'il y a lieu (pas de sélection manuelle de chaque parcelle...)
    extractPolygonesWaterZones(iface, dlg, assb, dir_dest, layersName)
    
    return    

#########################################################################
# FONCTION extractPolygonesWaterZones()                                            #
#########################################################################    
def extractPolygonesWaterZones(iface, dlg, assb, dir_dest, layersName):

    # Part2 : Nous avons enfin notre shape (type géométrique: polygone)
    # On poursuit le traitement jusqu'à l'extraction des zones en eau
    canvas = iface.mapCanvas() 
    li = layerList() 
    layer = None     
    
    if layersName['polygonize'] in li:
        layer = li[layersName['polygonize']]                  
        setLayerVisible(li[layersName['polygonize']], False)
        
    if layersName['filtre'] in li:
        setLayerVisible(li[layersName['filtre']], False)        
             
    layerWaterName = layersName['eau']
    layerWaterPath = dir_dest + os.sep + layerWaterName + EXT_VECTOR
    
    if os.path.exists(layerWaterPath):
        try:
            os.remove(layerWaterPath)
        except: 
            QMessageBox.information(None,"Attention !!!", layerWaterPath + " ne peut pas être effacé. Vérifiez que le fichier n'est pas verrouillé par un autre utilisateur ou que le fichier peut être effacé manuellement (droits d'écriture sur le répertoire).", QMessageBox.Ok, QMessageBox.NoButton)         
            messErreur(dlg, layerWaterPath + " ne peut pas être effacé.")
            return    
    
    messInfo(dlg, "Création de la couche: " + layerWaterName + ".")
    messInfo(dlg,"")
            
    if layer is None :
        messErreur(dlg, layerWaterName + " ne peut pas être chargé.")
        return

    crs = layer.crs()
    crsWkt = crs.toWkt()    
    layerWater = QgsVectorLayer("Polygon?crs=" + crsWkt, layerWaterName, "memory")
    
    if layerWater:
        QgsProject.instance().addMapLayer(layerWater)
    else:
        messErreur(dlg, layerWaterName + " ne peut pas être chargé.")
        return        

    li = layerList()
    symbol = li[layerWaterName].renderer().symbol()
    symbol.setColor(QColor.fromRgb(0,0,255))
    
    provider = li[layerWaterName].dataProvider()
       
    fields = layer.fields()
    wfields = QgsFields()
    for f in fields:
        provider.addAttributes([QgsField(f.name(), f.type())])
        wfields.append(QgsField(f.name(), f.type()))
 
    writer = QgsVectorFileWriter(layerWaterPath, "CP1250", wfields, QgsWkbTypes.Polygon, crs, FORMAT_VECT)
    
    if writer.hasError() != QgsVectorFileWriter.NoError:
        messErreur(dlg, layerWaterPath + " ne peut pas être créé.")    
        return
    
    li[layerWaterName].startEditing() 
    
    # Zones d'eau on récupère tous les polygones
    for elem in layer.getFeatures():
        if elem['DN'] == 1:
            messInfo(dlg, "----> Ajout du polygone de Fid: " + str(elem.id()))
            geom = elem.geometry()                                             
            feature = QgsFeature(fields)
            feature.setGeometry(geom)
            feature.setAttributes(elem.attributes())
            provider.addFeatures([feature])
            writer.addFeature(feature) 

    del writer
        
    li[layerWaterName].commitChanges()
    setLayerVisible(li[layerWaterName], False)

    node = QgsProject.instance().layerTreeRoot().findLayer(li[layerWaterName].id())
    iface.layerTreeView().layerTreeModel().refreshLayerLegend(node)
    li[layerWaterName].triggerRepaint() 
    canvas.refresh()

    setLayerVisible(li[layersName['seuil']], False) 
    li[layersName['seuil']].triggerRepaint() 
    
    # Nous avons les poygones des zones immergées le traitement s'arrête ici
    setLayerVisible(li[layerWaterName], True)
    li[layerWaterName].triggerRepaint() 
    
    canvas.refresh()
    extent = li[layerWaterName].extent()
    canvas.setExtent(extent)         

    messInfo(dlg,"Temps total de traitement:  " + str(round(time.time() - start_time)) + " secondes.")
    messInfo(dlg,"")     
    
    endTreatment(iface, dlg, assb, layersName)   
    
    return

#########################################################################
# FONCTION endTreatment()                                               #
#########################################################################
def endTreatment(iface, dlg, assb, layersName):

    canvas = iface.mapCanvas()
    li = layerList()

    messInfo(dlg, "Traitement terminé.")
    messInfo(dlg, "Note: Le rafraîchissement de l'écran en fin de traitement peut prendre un certain temps (fonction de la taille du raster).")
    messInfo(dlg, "---------------------------------------------------------------------------------------------------")        
    canvas.refresh()
                
    layerRasterName = layersName['raster']                
    setLayerVisible(li[layerRasterName], True)
    li[layerRasterName].triggerRepaint() 
    extent = li[layerRasterName].extent()
    canvas.setExtent(extent)    

    # Liste des rasteurs
    dlg.clayer_raster.clear()
    layers = QgsProject.instance().layerTreeRoot().layerOrder()
    index = 0
    indexCoucheRaster = 0
    
    for layer in layers:
        if layer.type() == QgsMapLayer.RasterLayer:
            dlg.clayer_raster.addItem(layer.name())
            if layer.name() == layerRasterName:
                indexCoucheRaster = index
            index+=1
    dlg.clayer_raster.setCurrentIndex(indexCoucheRaster)  
    
    # Liste vecteurs
    assb.clayer_vector.clear()
    layers = QgsProject.instance().layerTreeRoot().layerOrder()
    index = 0
    indexCoucheVector = 0
    for layer in layers:
        if layer.type() == QgsMapLayer.VectorLayer:
            assb.clayer_vector.addItem(layer.name())
            if 'emprise_zone' in layersName.keys() :
                if layer.name() == layersName['emprise_zone']:
                    indexCoucheVector = index
            index+=1
    assb.clayer_vector.setCurrentIndex(indexCoucheVector)  

    return