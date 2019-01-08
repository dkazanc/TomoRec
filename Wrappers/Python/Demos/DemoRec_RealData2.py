#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPLv3 license (ASTRA toolbox)

Script to reconstruct tomographic X-ray data (ice cream crystallisation process)
obtained at Diamond Light Source (UK synchrotron), beamline I13

Dependencies: 
    * astra-toolkit, install conda install -c astra-toolbox astra-toolbox
    * CCPi-RGL toolkit (for regularisation), install with 
    conda install ccpi-regulariser -c ccpi -c conda-forge
    or conda build of  https://github.com/vais-ral/CCPi-Regularisation-Toolkit
    * TomoPhantom, https://github.com/dkazanc/TomoPhantom

<<<
IF THE SHARED DATA ARE USED FOR PUBLICATIONS/PRESENTATIONS etc., PLEASE CITE:
E. Guo et al. 2018. Revealing the microstructural stability of a 
three-phase soft solid (ice cream) by 4D synchrotron X-ray tomography.
Journal of Food Engineering, vol.237
>>>
@author: Daniil Kazantsev: https://github.com/dkazanc
"""

import h5py
import numpy as np
import matplotlib.pyplot as plt

# loading data 
datapathfile = '../../../data/data_icecream.h5'
h5f = h5py.File(datapathfile, 'r')
data_norm = h5f['icecream_normalised'][:]
data_raw = h5f['icecream_raw'][:]
angles_rad = h5f['angles'][:]
h5f.close()
#%%
print ("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
print ("%%%%%%%%%%%%Reconstructing with FBP method %%%%%%%%%%%%%%%%%")
print ("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
from tomophantom.supp.astraOP import AstraTools

N_size = 2000
det_y_crop = [i for i in range(0,2374)]
Atools = AstraTools(np.size(det_y_crop), angles_rad, N_size, 'gpu') # initiate a class object
FBPrec = Atools.fbp2D(np.transpose(data_norm[det_y_crop,:,0]))

plt.figure()
#plt.imshow(FBPrec[500:1500,500:1500], vmin=0, vmax=1, cmap="gray")
plt.imshow(FBPrec, vmin=0, vmax=1, cmap="gray")
plt.title('FBP reconstruction')

#%%
# Initialise FISTA-type PWLS reconstruction (run once)
from fista.tomo.recModIter import RecTools

# set parameters and initiate a class object
Rectools = RecTools(DetectorsDimH = np.size(det_y_crop),  # DetectorsDimH # detector dimension (horizontal)
                    DetectorsDimV = None,  # DetectorsDimV # detector dimension (vertical) for 3D case only
                    AnglesVec = angles_rad, # array of angles in radians
                    ObjSize = N_size, # a scalar to define reconstructed object dimensions
                    datafidelity='PWLS',# data fidelity, choose LS, PWLS, GH (wip), Student (wip)
                    OS_number = 12, # the number of subsets, NONE/(or > 1) ~ classical / ordered subsets
                    tolerance = 1e-08, # tolerance to stop outer iterations earlier
                    device='gpu')

lc = Rectools.powermethod(np.transpose(data_raw[det_y_crop,:,0])) # calculate Lipschitz constant (run once to initilise)

# Run FISTA-PWLS-OS reconstrucion algorithm 
RecFISTA_PWLS = Rectools.FISTA(np.transpose(data_norm[det_y_crop,:,0]), \
                              np.transpose(data_raw[det_y_crop,:,0]), \
                              iterationsFISTA = 3, \
                              lipschitz_const = lc)
"""
plt.figure()
plt.imshow(RecFISTA_PWLS, vmin=0, vmax=0.3, cmap="gray")
plt.title('FISTA-PWLS-OS reconstruction')
plt.show()
"""
#%%
print ("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
print ("Reconstructing with FISTA PWLS-OS-TV method % %%%%%%%%%%%%%%")
print ("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
RecFISTA_TV = Rectools.FISTA(np.transpose(data_norm[det_y_crop,:,0]), \
                              np.transpose(data_raw[det_y_crop,:,0]), \
                              iterationsFISTA = 9, \
                              regularisation = 'FGP_TV', \
                              regularisation_parameter = 0.0009,\
                              regularisation_iterations = 200,\
                              lipschitz_const = lc)

plt.figure()
plt.imshow(RecFISTA_TV, vmin=0, vmax=0.2, cmap="gray")
plt.title('FISTA-PWLS-OS-TV reconstruction')
plt.show()
#%%
print ("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
print ("Reconstructing with FISTA PWLS-OS-NDF(Huber) method % %%%%%%")
print ("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
RecFISTA_NDF_huber = Rectools.FISTA(np.transpose(data_norm[det_y_crop,:,0]), \
                              np.transpose(data_raw[det_y_crop,:,0]), \
                              iterationsFISTA = 9, \
                              regularisation = 'NDF', \
                              NDF_penalty = 1, \
                              edge_param = 0.012,\
                              regularisation_parameter = 0.01,\
                              regularisation_iterations = 400,\
                              lipschitz_const = lc)

plt.figure()
plt.imshow(RecFISTA_NDF_huber, vmin=0, vmax=0.2, cmap="gray")
plt.title('FISTA-PWLS-OS-NDF (Huber) reconstruction')
plt.show()
#%%
from ccpi.filters.regularisers import PatchSelect
print ("Pre-calculating weights for non-local patches...")

pars = {'algorithm' : PatchSelect, \
        'input' : RecFISTA_PWLS,\
        'searchwindow': 7, \
        'patchwindow': 2,\
        'neighbours' : 13 ,\
        'edge_parameter':0.3}
H_i, H_j, Weights = PatchSelect(pars['input'], pars['searchwindow'],pars['patchwindow'],pars['neighbours'],
              pars['edge_parameter'],'gpu')

plt.figure()
plt.imshow(Weights[0,:,:], vmin=0, vmax=1, cmap="gray")
plt.colorbar(ticks=[0, 0.5, 1], orientation='vertical')
#%%
print ("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
print ("Reconstructing with FISTA PWLS-OS-NLTV method %%%%%%%%%%%%%%")
print ("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
RecFISTA_regNLTV = Rectools.FISTA(np.transpose(data_norm[det_y_crop,:,0]), \
                              np.transpose(data_raw[det_y_crop,:,0]), \
                              iterationsFISTA = 9, \
                              regularisation = 'NLTV', \
                              regularisation_parameter = 0.0007,\
                              regularisation_iterations = 25,\
                              NLTV_H_i = H_i,\
                              NLTV_H_j = H_j,\
                              NLTV_Weights = Weights,\
                              lipschitz_const = lc)
fig = plt.figure()
plt.imshow(RecFISTA_regNLTV, vmin=0, vmax=0.2, cmap="gray")
plt.title('FISTA PWLS-OS-NLTV reconstruction')
plt.show()
#fig.savefig('ice_NLTV.png', dpi=200)
#%%