# Copyright 2017 University of Maryland.
#
# This file is part of Sesame. It is subject to the license terms in the file
# LICENSE.rst found in the top-level directory of this distribution.

import numpy as np
from itertools import chain

from .observables import get_n, get_p
from .defects  import defectsF, defectsJ
# remember that efn and efp are zero at equilibrium

def getFandJ_eq(sys, v, periodic_bcs):
    Nx, Ny, Nz = sys.xpts.shape[0], sys.ypts.shape[0], sys.zpts.shape[0]

    # lists of rows, columns and data that will create the sparse Jacobian
    global rows, columns, data
    rows = []
    columns = []
    data = []

    # right hand side vector
    vec = np.zeros((Nx*Ny*Nz,))

    ###########################################################################
    #                     organization of the Jacobian matrix                 #
    ###########################################################################
    # A site with coordinates (i,j,k) corresponds to a site number s as follows:
    # k = s//(Nx*Ny)
    # j = s - s//Nx
    # i = s - j*Nx - k*Nx*Ny
    #
    # Row for v_s
    # ----------------------------
    # fv_row = s
    #
    # Columns for v_s
    # -------------------------------
    # v_s_col = s
    # v_sp1_col = s+1
    # v_sm1_col = s-1
    # v_spN_col = s + Nx
    # v_smN_col = s - Nx

    # defined for the interior only
    def laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, dym1, dy, 
                  dzm1, dz, dxbar, dybar, dzbar):
        res = ((vs - vsm1) / dxm1 - (vsp1 - vs) / dx) / dxbar\
            + ((vs - vsmN) / dym1 - (vspN - vs) / dy) / dybar\
            + ((vs - vsmNN) / dzm1 - (vspNN - vs) / dz) / dzbar 
        return res

    # defined to handle the abrupt boundary conditions
    def poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites):
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        dv_sm1, dv_sp1, dv_smN, dv_spN, dv_smNN, dv_spNN = 0, 0, 0, 0, 0, 0
        v_s = v[sites]
        if dx.all() != 0:
            dv_sp1 = (v[sites+1] - v_s) / dx
        if dxm1.all() != 0:
            dv_sm1 = (v_s - v[sites-1]) / dxm1
        if dy.all() != 0:
            dv_spN = (v[sites+Nx] - v_s) / dy
        if dym1.all() != 0:
            dv_smN = (v_s - v[sites-Nx]) / dym1
        if dz.all() != 0:
            dv_spNN = (v[sites+Nx*Ny] - v_s) / dz
        if dzm1.all() != 0:
            dv_smNN = (v_s - v[sites-Nx*Ny]) / dzm1

        fv = (dv_sm1 - dv_sp1) / dxbar + (dv_smN - dv_spN) / dybar\
           + (dv_smNN - dv_spNN) / dzbar - rho[sites]

        return fv

    # also defined to handle the abrupt boundary conditions
    def poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites):

        global rows, columns, data

        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        # compute differences of potentials
        dv_sm1, dv_sp1, dv_smN, dv_spN, dv_smNN, dv_spNN = 0, 0, 0, 0, 0, 0
        dv = -drho_dv[sites]

        if dx.all() != 0:
            dv_sp1 = -1 / (dx * dxbar)
            dv += -dv_sp1
            rows += sites.tolist()
            columns += (sites+1).tolist()
            data += dv_sp1.tolist()
        if dxm1.all() != 0:
            dv_sm1 = -1 / (dxm1 * dxbar)
            dv += -dv_sm1
            rows += sites.tolist()
            columns += (sites-1).tolist()
            data += dv_sm1.tolist()
        if dy.all() != 0:
            dv_spN = -1 / (dy * dybar)
            dv += -dv_spN
            rows += sites.tolist()
            columns += (sites+Nx).tolist()
            data += dv_spN.tolist()
        if dym1.all() != 0:
            dv_smN = 1 / (dym1 * dybar)
            dv += -dv_smN
            rows += sites.tolist()
            columns += (sites-Nx).tolist()
            data += dv_smN.tolist()
        if dz.all() != 0:
            dv_spNN = -1 / (dz * dzbar)
            dv += -dv_spNN
            rows += sites.tolist()
            columns += (sites+Nx*Ny).tolist()
            data += dv_spNN.tolist()
        if dzm1.all() != 0:
            dv_smNN = -1 / (dzm1 * dzbar)
            dv += -dv_smNN
            rows += sites.tolist()
            columns += (sites-Nx*Ny).tolist()
            data += dv_smNN.tolist()

        rows += sites.tolist()
        columns += sites.tolist()
        data += dv.tolist()



    ###########################################################################
    #                     For all sites in the system                         #
    ###########################################################################
    # carrier densities
    n = sys.Nc * np.exp(+sys.bl + v)
    p = sys.Nv * np.exp(-sys.Eg - sys.bl - v)

    # bulk charges
    rho = sys.rho - n + p
    drho_dv = -n - p

    # charge defects
    if len(sys.defects_list) != 0:
        defectsF(sys, sys.defects_list, n, p, rho)
        defectsJ(sys, sys.defects_list, n, p, drho_dv)

    # charge devided by epsilon
    rho = rho / sys.epsilon
    drho_dv = drho_dv / sys.epsilon

    # reshape the array as array[y-indices, x-indices]
    _sites = np.arange(Nx*Ny*Nz, dtype=int).reshape(Nz, Ny, Nx)


    ###########################################################################
    #     inside the system: 0 < i < Nx-1,  0 < j < Ny-1, 0 < k < Nz-1        #
    ###########################################################################
    # We compute fn, fp, fv derivatives. Those functions are only defined on the
    # inner part of the system. All the edges containing boundary conditions.

    # list of the sites inside the system
    sites = _sites[1:Nz-1, 1:Ny-1, 1:Nx-1].flatten()

    # lattice distances
    dx = np.tile(sys.dx[1:], (Ny-2)*(Nz-2))
    dy = np.repeat(sys.dy[1:], (Nx-2)*(Nz-2))
    dz = np.repeat(sys.dz[1:], (Nx-2)*(Ny-2))
    dxm1 = np.tile(sys.dx[:-1], (Ny-2)*(Nz-2))
    dym1 = np.repeat(sys.dy[:-1], (Nx-2)*(Nz-2))
    dzm1 = np.repeat(sys.dz[:-1], (Nx-2)*(Ny-2))
    dxbar = (dx + dxm1) / 2.
    dybar = (dy + dym1) / 2.
    dzbar = (dz + dzm1) / 2.

    #------------------------------ fv ----------------------------------------
    fv = ((v[sites]-v[sites-1]) / dxm1 - (v[sites+1]-v[sites]) / dx) / dxbar\
       + ((v[sites]-v[sites-Nx]) / dym1 - (v[sites+Nx]-v[sites]) / dy) / dybar\
       + ((v[sites]-v[sites-Nx*Ny]) / dzm1 - (v[sites+Nx*Ny]-v[sites])\
       / dz) / dzbar - rho[sites]

    # update the vector rows for the inner part of the system
    vec[sites] = fv

    #-------------------------- fv derivatives --------------------------------
    dvmNN = -1./(dzm1 * dzbar)
    dvmN = -1./(dym1 * dybar)
    dvm1 = -1./(dxm1 * dxbar)
    dv = 2./(dx * dxm1) + 2./(dy * dym1) + 2./(dz * dzm1) - drho_dv[sites]
    dvp1 = -1./(dx * dxbar)
    dvpN = -1./(dy * dybar)
    dvpNN = -1./(dz * dzbar)

    # update the sparse matrix row and columns for the inner part of the system
    dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
    dfv_cols = zip(sites-Nx*Ny, sites-Nx, sites-1, sites, sites+1, sites+Nx, sites+Nx*Ny)
    dfv_data = zip(dvmNN, dvmN, dvm1, dv, dvp1, dvpN, dvpNN)

    rows += list(chain.from_iterable(dfv_rows))
    columns += list(chain.from_iterable(dfv_cols))
    data += list(chain.from_iterable(dfv_data))


    ###########################################################################
    #       left boundary: i = 0, 0 <= j <= Ny-1, 0 <= k <= Nz-1              #
    ###########################################################################
    # list of the sites on the left side
    sites = _sites[:, :, 0].flatten()

    if sys.contacts_bcs[0] == "Neutral":
        # update vector with no surface charges
        vec[sites] = v[sites+1]-v[sites]
        # update Jacobian
        dv = -np.ones(len(sites),)
        dvp1 = np.ones(len(sites),)
        dav_rows = zip(sites, sites)
        dav_cols = zip(sites, sites+1)
        dav_data = zip(dv, dvp1)

    if sys.contacts_bcs[0] == "Ohmic" or sys.contacts_bc[0] == 'Schottky':
        # update vector with zeros
        vec[sites] = 0
        # update Jacobian
        dav_rows = [sites]
        dav_cols = [sites]
        dav_data = [np.ones((len(sites,)))]

    rows += list(chain.from_iterable(dav_rows))
    columns += list(chain.from_iterable(dav_cols))
    data += list(chain.from_iterable(dav_data))

    ###########################################################################
    #       right boundary: i = Nx-1, 0 <= j <= Ny-1, 0 <= k <= Nz-1          #
    ###########################################################################
    # list of the sites on the right side
    sites = _sites[:, :, Nx-1].flatten()

    if sys.contacts_bcs[1] == "Neutral":
        # update vector with no surface charges
        vec[sites] = v[sites-1]-v[sites-2]
        # update Jacobian
        dv = np.ones(len(sites),)
        dvm1 = -np.ones(len(sites),)
        dbv_rows = zip(sites, sites)
        dbv_cols = zip(sites-1, sites)
        dbv_data = zip(dvm1, dv)

    if sys.contacts_bcs[1] == "Ohmic" or sys.contacts_bcs[1] == "Schottky":
        # update vector with zeros
        vec[sites] = 0
        # update Jacobian
        dbv_rows = [sites]
        dbv_cols = [sites]
        dbv_data = [np.ones((len(sites,)))]

    rows += list(chain.from_iterable(dbv_rows))
    columns += list(chain.from_iterable(dbv_cols))
    data += list(chain.from_iterable(dbv_data))


    if periodic_bcs:
        ###########################################################################
        #           boundary: 0 < i < Nx-1, j = Ny-1, 0 < k < Nz-1               #
        ###########################################################################
        # We want periodic boundary conditions. This means that we can apply Poisson
        # equation assuming that the potential outside the system is the same as the
        # one on the opposite edge.

        # list of the sites in the top row
        sites = _sites[1:Nz-1, Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = np.tile(sys.dx[1:], Nz-2)
        dy = np.repeat((sys.dy[0] + sys.dy[-1])/2, (Nx-2)*(Nz-2))
        dz = np.repeat(sys.dz[:-1], Nx-2)
        dxm1 = np.tile(sys.dx[:-1], Nz-2)
        dym1 = np.repeat(sys.dy[-1], (Nx-2)*(Nz-2))
        dzm1 = np.zeros(Nz-1)
        dzm1 = np.repeat(sys.dz[:-1], Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        #---------------------------------- fv -------------------------------------
        vsmNN = v[sites-Nx*Ny]
        vsmN = v[sites-Nx]
        vsm1 = v[sites-1]
        vs = v[sites]
        vsp1 = v[sites+1]
        vspN = v[sites - Nx*(Ny-1)] # BC
        vspNN = v[sites + Nx*Ny]

        fv = laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, \
                       dym1, dy, dzm1, dz, dxbar, dybar, dzbar) - rho[sites]

        # update the vector rows for the inner part of the system
        vec[sites] = fv

        #-------------------------- fv derivatives --------------------------------
        dvmNN = -1./(dzm1 * dzbar)
        dvmN = -1./(dym1 * dybar)
        dvm1 = -1./(dxm1 * dxbar)
        dv = 2./(dx * dxm1) + (1/dy + 1/dym1)/dybar + (1/dz + 1/dzm1)/dzbar - drho_dv[sites]
        dvp1 = -1./(dx * dxbar)
        dvpN = -1./(dy * dybar) # BC
        dvpNN = -1./(dz * dzbar)

        # update the sparse matrix row and columns
        dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
        dfv_cols = zip(sites-Nx*Ny, sites-Nx, sites-1, sites, sites+1,\
                       sites-Nx*(Ny-1), sites+Nx*Ny)
        dfv_data = zip(dvmNN, dvmN, dvm1, dv, dvp1, dvpN, dvpNN)

        rows += list(chain.from_iterable(dfv_rows))
        columns += list(chain.from_iterable(dfv_cols))
        data += list(chain.from_iterable(dfv_data))


        ###########################################################################
        #          bottom boundary: 0 < i < Nx-1, j = 0, 0 < k < Nz-1             #
        ###########################################################################
        # list of the sites in the bottom row
        sites = _sites[1:Nz-1, 0, 1:Nx-1].flatten()

        # lattice distances
        dx = np.tile(sys.dx[1:], Nz-2)
        dy = np.repeat(sys.dy[0], (Nx-2)*(Nz-2))
        dz = np.repeat(sys.dz[1:], Nx-2)
        dxm1 = np.tile(sys.dx[:-1], Nz-2)
        dym1 = np.repeat((sys.dy[0] + sys.dy[-1])/2, (Nx-2)*(Nz-2))
        dzm1 = np.repeat(sys.dz[:-1], Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        #---------------------------------- fv -------------------------------------
        vsmNN = v[sites-Nx*Ny]
        vsmN = v[sites + Nx*(Ny-1)] # BC
        vsm1 = v[sites-1]
        vs = v[sites]
        vsp1 = v[sites+1]
        vspN = v[sites + Nx]
        vspNN = v[sites + Nx*Ny]

        fv = laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, \
                       dym1, dy, dzm1, dz, dxbar, dybar, dzbar) - rho[sites]

        # update the vector rows for the inner part of the system
        vec[sites] = fv

        #-------------------------- fv derivatives --------------------------------
        dvmNN = -1./(dzm1 * dzbar)
        dvmN = -1./(dym1 * dybar) # BC
        dvm1 = -1./(dxm1 * dxbar)
        dv = 2./(dx * dxm1) + (1/dy + 1/dym1)/dybar + (1/dz + 1/dzm1)/dzbar - drho_dv[sites]
        dvp1 = -1./(dx * dxbar)
        dvpN = -1./(dy * dybar)
        dvpNN = -1./(dz * dzbar)

        # update the sparse matrix row and columns
        dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
        dfv_cols = zip(sites-Nx*Ny, sites+Nx*(Ny-1), sites-1, sites, sites+1,\
                       sites+Nx, sites+Nx*Ny)
        dfv_data = zip(dvmNN, dvmN, dvm1, dv, dvp1, dvpN, dvpNN)

        rows += list(chain.from_iterable(dfv_rows))
        columns += list(chain.from_iterable(dfv_cols))
        data += list(chain.from_iterable(dfv_data))

        ###########################################################################
        #             boundary: 0 < i < Nx-1, 0 < j < Ny-1,  k = Nz-1             #
        ###########################################################################
        sites = _sites[Nz-1, 1:Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = np.tile(sys.dx[1:], Ny-2)
        dy = np.repeat(sys.dy[1:], Nx-2)
        dz = np.repeat((sys.dz[-1] + sys.dz[0])/2., (Nx-2)*(Ny-2))
        dxm1 = np.tile(sys.dx[:-1], Ny-2)
        dym1 = np.repeat(sys.dy[:-1], Nx-2)
        dzm1 = np.repeat(sys.dz[-1], (Nx-2)*(Ny-2))
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        #---------------------------------- fv -------------------------------------
        vsmNN = v[sites - Nx*Ny]
        vsmN = v[sites - Nx]
        vsm1 = v[sites - 1]
        vs = v[sites]
        vsp1 = v[sites + 1]
        vspN = v[sites + Nx]
        vspNN = v[sites - Nx*Ny*(Nz-1)] # BC

        fv = laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, \
                       dym1, dy, dzm1, dz, dxbar, dybar, dzbar) - rho[sites]

        # update the vector rows for the inner part of the system
        vec[sites] = fv

        #-------------------------- fv derivatives --------------------------------
        dvmNN = -1./(dzm1 * dzbar)
        dvmN = -1./(dym1 * dybar)
        dvm1 = -1./(dxm1 * dxbar)
        dv = 2./(dx * dxm1) + (1/dy + 1/dym1)/dybar + (1/dz + 1/dzm1)/dzbar - drho_dv[sites]
        dvp1 = -1./(dx * dxbar)
        dvpN = -1./(dy * dybar)
        dvpNN = -1./(dz * dzbar)

        # update the sparse matrix row and columns
        dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
        dfv_cols = zip(sites-Nx*Ny*(Nz-1), sites-Nx*Ny, sites-Nx, sites-1, sites,\
                       sites+1,sites+Nx)
        dfv_data = zip(dvpNN, dvmNN, dvmN, dvm1, dv, dvp1, dvpN)

        rows += list(chain.from_iterable(dfv_rows))
        columns += list(chain.from_iterable(dfv_cols))
        data += list(chain.from_iterable(dfv_data))


        ###########################################################################
        #             boundary: 0 < i < Nx-1, 0 < j < Ny-1,  k = 0                #
        ###########################################################################
        sites = _sites[0, 1:Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = np.tile(sys.dx[1:], Ny-2)
        dy = np.repeat(sys.dy[1:], Nx-2)
        dz = np.repeat(sys.dz[0], (Nx-2)*(Ny-2))
        dxm1 = np.tile(sys.dx[:-1], Ny-2)
        dym1 = np.repeat(sys.dy[:-1], Nx-2)
        dzm1 = np.repeat((sys.dz[-1] + sys.dz[0])/2., (Nx-2)*(Ny-2))
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        #---------------------------------- fv -------------------------------------
        vsmNN = v[sites + Nx*Ny*(Nz-1)] # BC
        vsmN = v[sites - Nx]
        vsm1 = v[sites - 1]
        vs = v[sites]
        vsp1 = v[sites + 1]
        vspN = v[sites + Nx]
        vspNN = v[sites + Nx*Ny]

        fv = laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, \
                       dym1, dy, dzm1, dz, dxbar, dybar, dzbar) - rho[sites]

        # update the vector rows for the inner part of the system
        vec[sites] = fv

        #-------------------------- fv derivatives --------------------------------
        dvmNN = -1./(dzm1 * dzbar)
        dvmN = -1./(dym1 * dybar)
        dvm1 = -1./(dxm1 * dxbar)
        dv = 2./(dx * dxm1) + (1/dy + 1/dym1)/dybar + (1/dz + 1/dzm1)/dzbar - drho_dv[sites]
        dvp1 = -1./(dx * dxbar)
        dvpN = -1./(dy * dybar)
        dvpNN = -1./(dz * dzbar)

        # update the sparse matrix row and columns
        dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
        dfv_cols = zip(sites-Nx, sites-1, sites, sites+1, sites+Nx, sites+Nx*Ny,
                       sites+Nx*Ny*(Nz-1))
        dfv_data = zip(dvmN, dvm1, dv, dvp1, dvpN, dvpNN, dvmNN)

        rows += list(chain.from_iterable(dfv_rows))
        columns += list(chain.from_iterable(dfv_cols))
        data += list(chain.from_iterable(dfv_data))

        ###########################################################################
        #                   boundary: 0 < i < Nx-1, j = 0,  k = 0                 #
        ###########################################################################
        sites = _sites[0, 0, 1:Nx-1].flatten()

        # lattice distances
        dx = sys.dx[1:]
        dy = np.repeat(sys.dy[0], Nx-2)
        dz = np.repeat(sys.dz[0], Nx-2)
        dxm1 = sys.dx[:-1]
        dym1 = np.repeat((sys.dy[0] + sys.dy[-1])/2., Nx-2)
        dzm1 = np.repeat((sys.dz[0] + sys.dz[-1])/2., Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        #---------------------------------- fv -------------------------------------
        vsmNN = v[sites + Nx*Ny*(Nz-1)] # BC
        vsmN = v[sites + Nx*(Ny-1)] # BC
        vsm1 = v[sites - 1]
        vs = v[sites]
        vsp1 = v[sites + 1]
        vspN = v[sites + Nx]
        vspNN = v[sites + Nx*Ny]

        fv = laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, \
                       dym1, dy, dzm1, dz, dxbar, dybar, dzbar) - rho[sites]

        # update the vector rows for the inner part of the system
        vec[sites] = fv

        #-------------------------- fv derivatives --------------------------------
        dvmNN = -1./(dzm1 * dzbar)
        dvmN = -1./(dym1 * dybar)
        dvm1 = -1./(dxm1 * dxbar)
        dv = 2./(dx * dxm1) + (1/dy + 1/dym1)/dybar + (1/dz + 1/dzm1)/dzbar - drho_dv[sites]
        dvp1 = -1./(dx * dxbar)
        dvpN = -1./(dy * dybar)
        dvpNN = -1./(dz * dzbar)

        # update the sparse matrix row and columns
        dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
        dfv_cols = zip(sites-1, sites, sites+1, sites+Nx, sites+Nx*(Ny-1),\
                       sites+Nx*Ny, sites+Nx*Ny*(Nz-1))
        dfv_data = zip(dvm1, dv, dvp1, dvpN, dvmN, dvpNN, dvmNN)

        rows += list(chain.from_iterable(dfv_rows))
        columns += list(chain.from_iterable(dfv_cols))
        data += list(chain.from_iterable(dfv_data))


        ###########################################################################
        #                   boundary: 0 < i < Nx-1, j = 0,  k = Nz-1              #
        ###########################################################################
        sites = _sites[Nz-1, 0, 1:Nx-1].flatten()

        # lattice distances
        dx = sys.dx[1:]
        dy = np.repeat(sys.dy[0], Nx-2)
        dz = np.repeat((sys.dz[0] + sys.dz[-1])/2., Nx-2)
        dxm1 = sys.dx[:-1]
        dym1 = np.repeat((sys.dy[0] + sys.dy[-1])/2., Nx-2)
        dzm1 = np.repeat(sys.dz[-1], Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        #---------------------------------- fv -------------------------------------
        vsmNN = v[sites - Nx*Ny]
        vsmN = v[sites + Nx*(Ny-1)] # BC
        vsm1 = v[sites - 1]
        vs = v[sites]
        vsp1 = v[sites + 1]
        vspN = v[sites + Nx]
        vspNN = v[sites - Nx*Ny*(Nz-1)] # BC

        fv = laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, \
                       dym1, dy, dzm1, dz, dxbar, dybar, dzbar) - rho[sites]

        # update the vector rows for the inner part of the system
        vec[sites] = fv

        #-------------------------- fv derivatives --------------------------------
        dvmNN = -1./(dzm1 * dzbar)
        dvmN = -1./(dym1 * dybar)
        dvm1 = -1./(dxm1 * dxbar)
        dv = 2./(dx * dxm1) + (1/dy + 1/dym1)/dybar + (1/dz + 1/dzm1)/dzbar - drho_dv[sites]
        dvp1 = -1./(dx * dxbar)
        dvpN = -1./(dy * dybar)
        dvpNN = -1./(dz * dzbar)

        # update the sparse matrix row and columns
        dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
        dfv_cols = zip(sites-Nx*Ny*(Nz-1), sites-Nx*Ny, sites-1, sites, sites+1,\
                       sites+Nx, sites+Nx*(Ny-1))
        dfv_data = zip(dvpNN, dvmNN, dvm1, dv, dvp1, dvpN, dvmN)

        rows += list(chain.from_iterable(dfv_rows))
        columns += list(chain.from_iterable(dfv_cols))
        data += list(chain.from_iterable(dfv_data))


        ###########################################################################
        #                   boundary: 0 < i < Nx-1, j = Ny-1,  k = 0              #
        ###########################################################################
        sites = _sites[0, Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = sys.dx[1:]
        dy = np.repeat((sys.dy[0] + sys.dy[-1])/2., Nx-2)
        dz = np.repeat(sys.dz[0], Nx-2)
        dxm1 = sys.dx[:-1]
        dym1 = np.repeat(sys.dy[-1], Nx-2)
        dzm1 = np.repeat((sys.dz[0] + sys.dz[-1])/2., Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        #---------------------------------- fv -------------------------------------
        vsmNN = v[sites + Nx*Ny*(Nz-1)] # BC
        vsmN = v[sites - Nx]
        vsm1 = v[sites - 1]
        vs = v[sites]
        vsp1 = v[sites + 1]
        vspN = v[sites - Nx*(Ny-1)] # BC
        vspNN = v[sites + Nx*Ny]

        fv = laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, \
                       dym1, dy, dzm1, dz, dxbar, dybar, dzbar) - rho[sites]

        # update the vector rows for the inner part of the system
        vec[sites] = fv

        #-------------------------- fv derivatives --------------------------------
        dvmNN = -1./(dzm1 * dzbar)
        dvmN = -1./(dym1 * dybar)
        dvm1 = -1./(dxm1 * dxbar)
        dv = 2./(dx * dxm1) + (1/dy + 1/dym1)/dybar + (1/dz + 1/dzm1)/dzbar - drho_dv[sites]
        dvp1 = -1./(dx * dxbar)
        dvpN = -1./(dy * dybar)
        dvpNN = -1./(dz * dzbar)

        # update the sparse matrix row and columns
        dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
        dfv_cols = zip(sites-Nx*(Ny-1), sites-Nx, sites-1, sites, sites+1,\
                       sites+Nx*Ny, sites+Nx*Ny*(Nz-1))
        dfv_data = zip(dvpN, dvmN, dvm1, dv, dvp1, dvpNN, dvmNN)

        rows += list(chain.from_iterable(dfv_rows))
        columns += list(chain.from_iterable(dfv_cols))
        data += list(chain.from_iterable(dfv_data))


        ###########################################################################
        #                boundary: 0 < i < Nx-1, j = Ny-1,  k = Nz-1              #
        ###########################################################################
        sites = _sites[Nz-1, Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = sys.dx[1:]
        dy = np.repeat((sys.dy[0] + sys.dy[-1])/2., Nx-2)
        dz = np.repeat((sys.dz[0] + sys.dz[-1])/2., Nx-2)
        dxm1 = sys.dx[:-1]
        dym1 = np.repeat(sys.dy[-1], Nx-2)
        dzm1 = np.repeat(sys.dz[-1], Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        #---------------------------------- fv -------------------------------------
        vsmNN = v[sites - Nx*Ny]
        vsmN = v[sites - Nx]
        vsm1 = v[sites - 1]
        vs = v[sites]
        vsp1 = v[sites + 1]
        vspN = v[sites - Nx*(Ny-1)] #BC
        vspNN = v[sites - Nx*Ny*(Nz-1)] # BC

        fv = laplacian(vsmNN, vsmN, vsm1, vs, vsp1, vspN, vspNN, dxm1, dx, \
                       dym1, dy, dzm1, dz, dxbar, dybar, dzbar) - rho[sites]

        # update the vector rows for the inner part of the system
        vec[sites] = fv

        #-------------------------- fv derivatives --------------------------------
        dvmNN = -1./(dzm1 * dzbar)
        dvmN = -1./(dym1 * dybar)
        dvm1 = -1./(dxm1 * dxbar)
        dv = 2./(dx * dxm1) + (1/dy + 1/dym1)/dybar + (1/dz + 1/dzm1)/dzbar - drho_dv[sites]
        dvp1 = -1./(dx * dxbar)
        dvpN = -1./(dy * dybar)
        dvpNN = -1./(dz * dzbar)

        # update the sparse matrix row and columns
        dfv_rows = zip(sites, sites, sites, sites, sites, sites, sites)
        dfv_cols = zip(sites-Nx*Ny*(Nz-1), sites-Nx*Ny, sites-Nx*(Ny-1), sites-Nx,\
                       sites-1, sites, sites+1)
        dfv_data = zip(dvpNN, dvmNN, dvpN, dvmN, dvm1, dv, dvp1)

        rows += list(chain.from_iterable(dfv_rows))
        columns += list(chain.from_iterable(dfv_cols))
        data += list(chain.from_iterable(dfv_data))

    else:
        ###########################################################################
        #           boundary: 0 < i < Nx-1, j = Ny-1, 0 < k < Nz-1                #
        ###########################################################################

        # list of the sites in the top row
        sites = _sites[1:Nz-1, Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = np.tile(sys.dx[1:], Nz-2)
        dy = np.array([0])
        dz = np.repeat(sys.dz[:-1], Nx-2)
        dxm1 = np.tile(sys.dx[:-1], Nz-2)
        dym1 = np.repeat(sys.dy[-1], (Nx-2)*(Nz-2))
        dzm1 = np.zeros(Nz-1)
        dzm1 = np.repeat(sys.dz[:-1], Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        vec[sites] = poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        

        ###########################################################################
        #          bottom boundary: 0 < i < Nx-1, j = 0, 0 < k < Nz-1             #
        ###########################################################################
        # list of the sites in the bottom row
        sites = _sites[1:Nz-1, 0, 1:Nx-1].flatten()

        # lattice distances
        dx = np.tile(sys.dx[1:], Nz-2)
        dy = np.repeat(sys.dy[0], (Nx-2)*(Nz-2))
        dz = np.repeat(sys.dz[1:], Nx-2)
        dxm1 = np.tile(sys.dx[:-1], Nz-2)
        dym1 = np.array([0])
        dzm1 = np.repeat(sys.dz[:-1], Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        vec[sites] = poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites)

        ###########################################################################
        #             boundary: 0 < i < Nx-1, 0 < j < Ny-1,  k = Nz-1             #
        ###########################################################################
        sites = _sites[Nz-1, 1:Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = np.tile(sys.dx[1:], Ny-2)
        dy = np.repeat(sys.dy[1:], Nx-2)
        dz = np.array([0])
        dxm1 = np.tile(sys.dx[:-1], Ny-2)
        dym1 = np.repeat(sys.dy[:-1], Nx-2)
        dzm1 = np.repeat(sys.dz[-1], (Nx-2)*(Ny-2))
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        vec[sites] = poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites)

        ###########################################################################
        #             boundary: 0 < i < Nx-1, 0 < j < Ny-1,  k = 0                #
        ###########################################################################
        sites = _sites[0, 1:Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = np.tile(sys.dx[1:], Ny-2)
        dy = np.repeat(sys.dy[1:], Nx-2)
        dz = np.repeat(sys.dz[0], (Nx-2)*(Ny-2))
        dxm1 = np.tile(sys.dx[:-1], Ny-2)
        dym1 = np.repeat(sys.dy[:-1], Nx-2)
        dzm1 = np.array([0])
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        vec[sites] = poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites)

        ###########################################################################
        #                   boundary: 0 < i < Nx-1, j = 0,  k = 0                 #
        ###########################################################################
        sites = _sites[0, 0, 1:Nx-1].flatten()

        # lattice distances
        dx = sys.dx[1:]
        dy = np.repeat(sys.dy[0], Nx-2)
        dz = np.repeat(sys.dz[0], Nx-2)
        dxm1 = sys.dx[:-1]
        dym1 = np.array([0])
        dzm1 = np.array([0])
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        vec[sites] = poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites)

        ###########################################################################
        #                   boundary: 0 < i < Nx-1, j = 0,  k = Nz-1              #
        ###########################################################################
        sites = _sites[Nz-1, 0, 1:Nx-1].flatten()

        # lattice distances
        dx = sys.dx[1:]
        dy = np.repeat(sys.dy[0], Nx-2)
        dz = np.array([0])
        dxm1 = sys.dx[:-1]
        dym1 = np.array([0])
        dzm1 = np.repeat(sys.dz[-1], Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        vec[sites] = poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites)

        ###########################################################################
        #                   boundary: 0 < i < Nx-1, j = Ny-1,  k = 0              #
        ###########################################################################
        sites = _sites[0, Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = sys.dx[1:]
        dy = np.array([0])
        dz = np.repeat(sys.dz[0], Nx-2)
        dxm1 = sys.dx[:-1]
        dym1 = np.repeat(sys.dy[-1], Nx-2)
        dzm1 = np.array([0])
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        vec[sites] = poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites)

        ###########################################################################
        #                boundary: 0 < i < Nx-1, j = Ny-1,  k = Nz-1              #
        ###########################################################################
        sites = _sites[Nz-1, Ny-1, 1:Nx-1].flatten()

        # lattice distances
        dx = sys.dx[1:]
        dy = np.array([0])
        dz = np.array([0])
        dxm1 = sys.dx[:-1]
        dym1 = np.repeat(sys.dy[-1], Nx-2)
        dzm1 = np.repeat(sys.dz[-1], Nx-2)
        dxbar = (dx + dxm1) / 2.
        dybar = (dy + dym1) / 2.
        dzbar = (dz + dzm1) / 2.

        vec[sites] = poisson(v, dxm1, dx, dym1, dy, dzm1, dz, sites)
        poisson_derivs(v, dxm1, dx, dym1, dy, dzm1, dz, sites)


    return vec, rows, columns, data
