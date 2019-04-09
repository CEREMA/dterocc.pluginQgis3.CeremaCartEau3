# -*- coding: utf-8 -*-
"""
/***************************************************************************
 assembly
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

from qgis.core import *
from qgis.gui import *

from osgeo import gdal, ogr,osr
from gdalconst import *
import processing
from processing.algs.gdal.GdalUtils import GdalUtils
import os, time, glob
import gdal_merge as gm

from .tools import FORMAT_IMA, messErreur, getEmpriseFile, getEmpriseImage, getPixelWidthXYImage, getNodataValueImage, getDataTypeImage, getProjectionImage, updateReferenceProjection, roundPixelEmpriseSize
 
#########################################################################
# FONCTION assembleRasters()                                            #
#########################################################################        
def assembleRasters(dlg, empriseVector, repRasterAssemblyList, ext_list, rasterAssembly):

    # Emprise de la zone selectionnée
    empr_xmin,empr_xmax,empr_ymin,empr_ymax = getEmpriseFile(empriseVector)
    
    repRasterAssembly_str = ""
    # Recherche des images dans l'emprise du vecteur
    for repertory in repRasterAssemblyList:
        images_find_list, images_error_list = findImagesFile(dlg, repertory, ext_list, empr_xmin, empr_xmax, empr_ymin, empr_ymax)
        repRasterAssembly_str += str(repertory) + "  "
    
    # Utilisation d'un fichier temporaire pour  l'assemblage    
    repertory_output = os.path.dirname(rasterAssembly)
    file_name = os.path.splitext(os.path.basename(rasterAssembly))[0]
    extension = os.path.splitext(rasterAssembly)[1]
    file_out_suffix_merge = "_merge"
    merge_file_tmp = repertory_output + os.sep + file_name + file_out_suffix_merge + extension

    # Suppression du fichier assemblè
    if os.path.exists(rasterAssembly):
        resp = QMessageBox.question(None, "Attention !!!", "Le fichier raster %s existe déjà  voulez-vous l'écraser?"%(rasterAssembly), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resp == 16384 :
            try:
                os.remove(rasterAssembly)
            except:
                messErreur(dlg, "Erreur le fichier raster %s ne peut pas être écrasé il est utilisé par un autre processus ou en lecture seul !!!"%(rasterAssembly))
                return -1
        else :
           return -1        
        
    if os.path.exists(merge_file_tmp):
        os.remove(merge_file_tmp)

    if len(images_find_list) > 0 and os.path.isfile(images_find_list[0]) :
        epsg = getProjectionImage(images_find_list[0])
        no_data_value = getNodataValueImage(images_find_list[0])
        data_type = getDataTypeImage(images_find_list[0])
        if no_data_value == None :
            no_data_value = 0
    else :
        messErreur(dlg, "Erreur il n'y a pas de fichier image correspondant à l'emprise dans le(s) répertoire(s) : %s!!!"%(repRasterAssembly_str) )
        return -1
        
    # Assembler les images trouvées
    assemblyImages(dlg, images_find_list, merge_file_tmp, data_type, no_data_value, epsg)
    
    # Découpage du fichier image assemblé par l'emprise
    if os.path.exists(merge_file_tmp) :
        cutImageByVector(dlg, empriseVector, merge_file_tmp, rasterAssembly, data_type, no_data_value, epsg)
    else :
        messErreur(dlg, "Erreur il n'y a pas de fichier assemblé %s à découper !!!"%(rasterAssembly))
        return -1
        
    # Suppression du fichier temporaire
    if os.path.exists(merge_file_tmp):
        os.remove(merge_file_tmp)

    return 0
    
#########################################################################
# FONCTION findImagesFile()                                             #
#########################################################################        
def findImagesFile(dlg, repertory, extension_list, empr_xmin, empr_xmax, empr_ymin, empr_ymax):
    images_find_list = []
    images_error_list = []
    
    # Recherche des fichier correspondant à l'extention dans le repertoire de recherche
    for imagefile in glob.glob(repertory + os.sep + '*.*'):
        ok = True
        if imagefile.rsplit('.',1)[1] in extension_list :
            try:
                dataset = gdal.Open(imagefile, GA_ReadOnly)
            except RuntimeError as err :
                messErreur(dlg, "Erreur Impossible d'ouvrir le fichier : %s !!!"%(imagefile))
                images_error_list.append(imagefile)
                ok = False
            if ok and dataset is None :
                images_error_list.append(imagefile)
                ok = False
            if ok :
                cols = dataset.RasterXSize
                rows = dataset.RasterYSize
                bands = dataset.RasterCount

                geotransform = dataset.GetGeoTransform()
                pixel_width = geotransform[1]  # w-e pixel resolution
                pixel_height = geotransform[5] # n-s pixel resolution

                imag_xmin = geotransform[0]     # top left x
                imag_ymax = geotransform[3]     # top left y
                imag_xmax = imag_xmin + (cols * pixel_width)
                imag_ymin = imag_ymax + (rows * pixel_height)

                # Si l'image et l'emprise sont complement disjointe l'image n'est pas selectionée
                if not ((imag_xmin > empr_xmax) or (imag_xmax < empr_xmin) or (imag_ymin > empr_ymax) or (imag_ymax < empr_ymin)) :
                    images_find_list.append(imagefile)
                    
    return images_find_list, images_error_list
    
#########################################################################
# FONCTION assemblyImages()                                             #
#########################################################################
def assemblyImages(dlg, images_list, output_file, data_type, no_data_value, epsg):

    # Utilisation de la commande gdal_merge pour fusioner les fichiers image source
    # Pour les parties couvertes par plusieurs images, l'image retenue sera la dernière mergée
    """
    try:
        #processing.algorithmHelp("gdal:merge")
        #processing.runalg('gdalogr:merge', images_list, False, False, no_data_value, data_type, output_file)
        parameters = {"INPUT":images_list, "PCT":False, "SEPARATE":False, "NODATA_OUTPUT":no_data_value, "DATA_TYPE":data_type, "OUTPUT":output_file}
        processing.run('gdal:merge', parameters)
    except :
        messErreur(dlg, "Erreur d'assemblage par gdal:merge de %s !!!"%(output_file))
        return None
    """
    # Récupération de la résolution du raster d'entrée
    pixel_size_x, pixel_size_y = getPixelWidthXYImage(images_list[0])
    
    # Creation de la commande avec gdal_merge
    command = [ '',
                '-o',
                output_file,
                '-of', 
                FORMAT_IMA, 
                '-a_nodata',
                str(no_data_value),
                "-ps",
                str(pixel_size_x),
                str(pixel_size_y)]
                
    for ima in images_list :
        command.append(ima)
    
    try:   
        gm.main(command)
    except:
        messErreur(dlg,u"Erreur de assemblage par gdal_merge de %s !!!"%(output_file))
        return None
    
    # Si le fichier de sortie mergé a perdu sa projection on force la projection à la valeur par defaut
    prj = getProjectionImage(output_file)

    if (prj == None or prj == 0) and (epsg != 0):
        updateReferenceProjection(output_file, int(epsg))

    return
    
#########################################################################
# FONCTION cutImageByVector()                                           #
#########################################################################
def cutImageByVector(dlg, cut_shape_file, input_image, output_image, data_type, no_data_value, epsg):

    # Découpage par gdal cliprasterbymasklayer
    """
    try:
        #processing.algorithmHelp("gdal:cliprasterbymasklayer")
        #parameters = {"INPUT": input_image, cut_shape_file, str(no_data_value), False, False, True, data_type, 0, 1, 1, 1, False, 0, False, "", "OUTPUT":output_image}
        parameters = {"INPUT": input_image, "MASK":cut_shape_file, "NODATA":no_data_value, "CROP_TO_CUTLINE":True, "KEEP_RESOLUTION":True, "DATA_TYPE":0,  "OUTPUT":output_image}
        processing.run('gdal:cliprasterbymasklayer', parameters)
    except:
        processing.algorithmHelp("gdal:cliprasterbymasklayer")
        messErreur(dlg, "Erreur au cours du decoupage de l'image %s par le vecteur %s !!!"%(input_image, cut_shape_file))
        return
    """
    
    # Autre solution avec calcul d'emprise arrondi et optimisé et callé sur les pixels de l'image d'entrée et decoupe avec gdalwarp

    # Récupération de la résolution du raster d'entrée
    pixel_size_x, pixel_size_y = getPixelWidthXYImage(input_image)

    # Récuperation de l'emprise de l'image
    ima_xmin, ima_xmax, ima_ymin, ima_ymax = getEmpriseImage(input_image)

    # Identification de l'emprise de vecteur de découpe
    empr_xmin,empr_xmax,empr_ymin,empr_ymax = getEmpriseFile(cut_shape_file)

    # Calculer l'emprise arrondi
    xmin, xmax, ymin, ymax = roundPixelEmpriseSize(pixel_size_x, pixel_size_y, empr_xmin, empr_xmax, empr_ymin, empr_ymax)

    # Trouver l'emprise optimale
    opt_xmin = xmin
    opt_xmax = xmax
    opt_ymin = ymin
    opt_ymax = ymax

    if ima_xmin > xmin :
        opt_xmin = ima_xmin
    if ima_xmax < xmax :
        opt_xmax = ima_xmax
    if ima_ymin > ymin :
        opt_ymin = ima_ymin
    if ima_ymax < ymax :
        opt_ymax = ima_ymax  
    
    # Creation de la commande avec gdalwarp
    command = ["gdalwarp",
               "-t_srs",
               "EPSG:"+str(epsg),
               "-te",
               str(opt_xmin),
               str(opt_ymin),
               str(opt_xmax),
               str(opt_ymax),
               "-tap", 
               "-multi", 
               "-co",
               "NUM_THREADS=ALL_CPUS",
               "-tr",
               str(pixel_size_x),
               str(pixel_size_y),
               "-dstnodata",
               str(no_data_value),
               "-cutline",
               cut_shape_file,
               "-overwrite",
               "-of",
               FORMAT_IMA,
               input_image,
               output_image]
    
    # Execute runGdal
    try :
        GdalUtils.runGdal(command)    
    except:
        messErreur(dlg,"Erreur au cours du decoupage de l'image %s par le vecteur %s  avec gdalwarp!!!"%(input_image, cut_shape_file))
        return None 

    return
    
