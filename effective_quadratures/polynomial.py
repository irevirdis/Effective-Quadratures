#!/usr/bin/env python
"""Operations involving multivariate polynomials"""
from parameter import Parameter
from indexset import IndexSet
import numpy as np
from utils import error_function, evalfunction, find_repeated_elements, meshgrid
#****************************************************************************
# Functions to code:
#    
# 1. a getPDF function that samples the polynomial using independent samples from parameters
# 2. a getSamples function that can generate random indepepndent samples based on parameters
#****************************************************************************
class Polynomial(object):
    """
    This class defines a polynomial and its associated functions. 

    :param array of Parameters uq_parameters: A list of Parameters
    :param IndexSet index_set: An instance of the IndexSet class, in case the user wants to overwrite the indices
        that are obtained using the orders of the univariate parameters in Parameters uq_parameters. The latter 
        corresponds to a tensor grid index set and is the default option if no index_set parameter input is given.
    
    **Sample declarations** 
    ::
        >> s = Parameter(lower=-2, upper=2, param_type='Uniform', points=4)
        >> T = IndexSet('Total order', [3,3])
        >> polyObject = Polynomial([s,s],T) # basis is defined by T

        >> s = Parameter(lower=-2, upper=2, param_type='Uniform')
        >> polyObject = Polynomial([s,s]) # Tensor basis is used
    """
    # Constructor
    def __init__(self, uq_parameters, index_sets=None):
    
        self.uq_parameters = uq_parameters

        # Here we set the index sets if they are not provided
        if index_sets is None:
            # Determine the highest orders for a tensor grid
            highest_orders = []
            for i in range(0, len(uq_parameters)):
                highest_orders.append(uq_parameters[i].order)
            
            self.index_sets = IndexSet('Tensor grid', highest_orders)
        else:
            self.index_sets = index_sets
    
    def getIndexSet(self):
        """
        Returns the index set used for computing the multivariate polynomials

        :param Polynomial self: An instance of the Polynomial class
        :return: index_set, cardinality-by-dimension matrix which is obtained by calling the getIndexSet() routine of the IndexSet object
        :rtype: ndarray

        **Sample declaration**
        :: 
            >> s = Parameter(lower=-2, upper=2, param_type='Uniform')
            >> polyObject = Polynomial([s,s])
            >> I = polyObject.getIndexSet()
        """
        return self.index_sets.getIndexSet()

    # Do we really need additional_orders?
    def getPointsAndWeights(self, override_orders=None):
        """
        Returns the nD Gaussian quadrature points and weights based on the recurrence coefficients of each Parameter. This function
        computes anisotropic and isotropic tensor product rules using a series of Kronecker product operations on univariate Gauss 
        quadrature points and weights. For details on the univariate rules, see Parameter.getLocalQuadrature()

        :param Polynomial self: An instance of the Polynomial class
        :param array override_orders: Optional input of orders that overrides the orders defined for each Parameter.
            This functionality is used by the integrals function.
        :return: points, N-by-d matrix that contains the tensor grid Gauss quadrature points
        :rtype: ndarray
        :return: weights, 1-by-N matrix that contains the tensor grid Gauss quadrature weights
        :rtype: ndarray


        **Sample declaration**
        :: 
            >> s = Parameter(lower=-2, upper=2, param_type='Uniform')
            >> polyObject = Polynomial([s,s])
            >> p, w = polyObject.getPointsAndWeights()
        """
        # Initialize some temporary variables
        stackOfParameters = self.uq_parameters
        dimensions = int(len(stackOfParameters))
        
        orders = []
        if override_orders is None:
            for i in range(0, dimensions):
                orders.append(stackOfParameters[i].order)
        else:
            orders = override_orders
        
        # Initialize points and weights
        pp = [1.0]
        ww = [1.0]

        # number of parameters
        # For loop across each dimension
        for u in range(0, dimensions):

            # Call to get local quadrature method (for dimension 'u')
            local_points, local_weights = stackOfParameters[u].getLocalQuadrature(orders[u])

            # Tensor product of the weights
            ww = np.kron(ww, local_weights)

            # Tensor product of the points
            dummy_vec = np.ones((len(local_points), 1))
            dummy_vec2 = np.ones((len(pp), 1))
            left_side = np.array(np.kron(pp, dummy_vec))
            right_side = np.array( np.kron(dummy_vec2, local_points) )
            pp = np.concatenate((left_side, right_side), axis = 1)

        # Ignore the first column of pp
        points = pp[:,1::]
        weights = ww

        # Now re-scale the points and return only if its not a Gaussian!
        for i in range(0, dimensions):
            for j in range(0, len(points)):
                if (stackOfParameters[i].param_type == "Uniform"):
                    points[j,i] = 0.5 * ( points[j,i] + 1.0 )*( stackOfParameters[i].upper - stackOfParameters[i].lower) + stackOfParameters[i].lower
        
                elif (stackOfParameters[i].param_type == "Beta" ):
                    points[j,i] =  ( points[j,i] )*( stackOfParameters[i].upper - stackOfParameters[i].lower) + stackOfParameters[i].lower
        
                elif (stackOfParameters[i].param_type == "Gaussian"):
                    points[j,i] = points[j,i] # No scaling!

        # Return tensor grid quad-points and weights
        return points, weights

    def getMultivariatePolynomial(self, stackOfPoints, indexsets=None):
        """
        Returns multivariate orthonormal polynomials and their derivatives

        :param Polynomial self: An instance of the Polynomial class
        :param: ndarray stackOfPoints: An m-by-d matrix that contains points along which the polynomials (and their derivatives) must be evaluated
            at; here m represents the total number of points across d dimensions. Note that the derivatives are only computed if the Parameters 
            have the derivative_flag set to 1.
        :return: polynomial, m-by-N matrix where m are the number of points at which the multivariate orthonormal polynomial must be evaluated at, and
            N is the cardinality of the index set used when declaring a Polynomial object.
        :rtype: ndarray
        :return: derivatives, m-by-N matrix for each cell (total cells are d) where m are the number of points at which the multivariate orthonormal polynomial must be evaluated at, and
            N is the cardinality of the index set used when declaring a Polynomial object.
        :rtype: cell object


        **Sample declaration**
        :: 
            >> s = Parameter(lower=-1, upper=1, param_type='Uniform', points=2, derivative_flag=1)
            >> uq_parameters = [s,s]
            >> uq = Polynomial(uq_parameters)
            >> pts, x1, x2 = utils.meshgrid(-1.0, 1.0, 10, 10)
            >> P , Q = uq.getMultivariatePolynomial(pts)
        """

        # "Unpack" parameters from "self"
        empty = np.mat([0])
        stackOfParameters = self.uq_parameters
        isets = self.index_sets
        if indexsets is None:
            if isets.index_set_type == 'Sparse grid':
                ic, not_used, index_set = isets.getIndexSet()
            else:
                index_set = isets.getIndexSet()
        else:
            index_set = indexsets

        dimensions = len(stackOfParameters)
        p = {}
        d = {}
        C_all = {}

        # Save time by returning if univariate!
        if dimensions == 1 and stackOfParameters[0].derivative_flag == 0:
            poly , derivatives =  stackOfParameters[0].getOrthoPoly(stackOfPoints)
            derivatives = empty
            return poly, derivatives
        elif dimensions == 1 and stackOfParameters[0].derivative_flag == 1:
            poly , derivatives =  stackOfParameters[0].getOrthoPoly(stackOfPoints)
            return poly, derivatives
        else:
            for i in range(0, dimensions):
                p[i] , d[i] = stackOfParameters[i].getOrthoPoly(stackOfPoints[:,i], int(np.max(index_set[:,i] + 1) ) )

        # Now we multiply components according to the index set
        no_of_points = len(stackOfPoints)
        polynomial = np.zeros((len(index_set), no_of_points))
        derivatives = np.zeros((len(index_set), no_of_points, dimensions))

        # One loop for polynomials
        for i in range(0, len(index_set)):
            temp = np.ones((1, no_of_points))
            for k in range(0, dimensions):
                polynomial[i,:] = p[k][int(index_set[i,k])] * temp
                temp = polynomial[i,:]
        
        # Second loop for derivatives!
        if stackOfParameters[0].derivative_flag == 1:
            P_others = np.zeros((len(index_set), no_of_points))

            # Going into for loop!
            for j in range(0, dimensions):
                # Now what are the remaining dimnensions?
                C_local = np.zeros((len(index_set), no_of_points))
                remaining_dimensions = np.arange(0, dimensions)
                remaining_dimensions = np.delete(remaining_dimensions, j)
                total_elements = remaining_dimensions.__len__

                # Now we compute the "C" matrix
                for i in range(0, len(index_set)): 
                    # Temporary variable!
                    P_others = np.zeros((len(index_set), no_of_points))
                    temp = np.ones((1, no_of_points))

                    # Multiply ortho-poly components in these "remaining" dimensions   
                    for k in range(0, len(remaining_dimensions)):
                        entry = remaining_dimensions[k]
                        P_others[i,:] = p[entry][int(index_set[i, entry])] * temp
                        temp = P_others[i,:]
                        if len(remaining_dimensions) == 0: # in which case it is emtpy!
                            C_all[i,:] = d[j][int(index_set[i,j])]
                        else:
                            C_local[i,:] = d[j][int(index_set[i, j])] * P_others[i,:]       
                C_all[j] = C_local
                del C_local
            return polynomial, C_all
        empty = np.mat([0])
        return polynomial, empty


    def getPolynomialCoefficients(self, function):  
        """
        Returns multivariate orthonormal polynomial coefficients. Depending on the choice of the index set, this function will either return a tensor grid
        of pseudospectral coefficients or a sparse grid using the SPAM technique by Constantine et al (2012). 
    
        :param Polynomial self: An instance of the Polynomial class
        :param: callable function: The function that needs to be approximated (or interpolated)
        :return: coefficients: The pseudospectral coefficients
        :rtype: ndarray
        :return: indexset: The indices used for the pseudospectral computation
        :rtype: ndarray
        :return: evaled_pts: The points at which the function was evaluated
        :rtype: ndarray

        """
        # Method to compute the coefficients
        method = self.index_sets.index_set_type
        # Get the right polynomial coefficients
        if method == "Tensor grid":
            coefficients, indexset, evaled_pts = getPseudospectralCoefficients(self, function)
        if method == "Sparse grid":
            coefficients, indexset, evaled_pts = getSparsePseudospectralCoefficients(self, function)
        else:
            coefficients, indexset, evaled_pts = getPseudospectralCoefficients(self, function)
        return coefficients,  indexset, evaled_pts

    def getPolynomialApproximation(self, function, plotting_pts, coefficients=None, indexset=None):
        
        """
        Returns the polynomial approximation of a function. This routine effectively multiplies the coefficients of a polynomial
        expansion with its corresponding basis polynomials. 
    
        :param Polynomial self: An instance of the Polynomial class
        :param: callable function: The function that needs to be approximated (or interpolated)
        :param: ndarray plotting_pts: The points at which the polynomial approximation should be evaluated at
        :return: polyapprox: The polynomial expansion of a function
        :rtype: numpy matrix

        """
        # Check to see if we need to call the coefficients
        if coefficients is None or indexset is None:
            coefficients,  indexset, evaled_pts = self.getPolynomialCoefficients(function)

        P , Q = self.getMultivariatePolynomial(plotting_pts, indexset)
        P = np.mat(P)
        C = np.mat(coefficients)
        polyapprox = P.T * C
        return polyapprox


#--------------------------------------------------------------------------------------------------------------
#
#  PRIVATE FUNCTIONS!
#
#--------------------------------------------------------------------------------------------------------------
def getPseudospectralCoefficients(self, function, override_orders=None):
    
    stackOfParameters = self.uq_parameters
    dimensions = len(stackOfParameters)
    q0 = [1]
    Q = []
    orders = []

    # If additional orders are provided, then use those!
    if override_orders is None:
        for i in range(0, dimensions):
            orders.append(stackOfParameters[i].order)
            Qmatrix = stackOfParameters[i].getJacobiEigenvectors()
            Q.append(Qmatrix)

            if orders[i] == 1:
                q0 = np.kron(q0, Qmatrix)
            else:
                q0 = np.kron(q0, Qmatrix[0,:])   
            
    else:
        for i in range(0, dimensions):
            orders.append(override_orders[i])
            Qmatrix = stackOfParameters[i].getJacobiEigenvectors(orders[i])
            Q.append(Qmatrix)

            if orders[i] == 1:
                q0 = np.kron(q0, Qmatrix)
            else:
                q0 = np.kron(q0, Qmatrix[0,:])

    # Compute multivariate Gauss points and weights!
    if override_orders is None:
        p, w = self.getPointsAndWeights()
    else:
        p, w = self.getPointsAndWeights(override_orders)

    # Evaluate the first point to get the size of the system
    fun_value_first_point = function(p[0,:])
    u0 =  q0[0,0] * fun_value_first_point
    N = 1
    gn = int(np.prod(orders))
    Uc = np.zeros((N, gn))
    Uc[0,1] = u0

    function_values = np.zeros((1,gn))
    for i in range(0, gn):
        function_values[0,i] = function(p[i,:])

    # Now we evaluate the solution at all the points
    for j in range(0, gn): # 0
        Uc[0,j]  = q0[0,j] * function_values[0,j]

    # Compute the corresponding tensor grid index set:
    order_correction = []
    for i in range(0, len(orders)):
        temp = orders[i] - 1
        order_correction.append(temp)

    tensor_grid_basis = IndexSet('Tensor grid',  order_correction)
    tensor_set = tensor_grid_basis.getIndexSet()

    # Now we use kronmult
    K = efficient_kron_mult(Q, Uc)
    F = function_values
    K = np.column_stack(K)
    return K, tensor_set, p


def getSparsePseudospectralCoefficients(self, function):
    
    # INPUTS
    stackOfParameters = self.uq_parameters
    indexSets = self.index_sets
    dimensions = len(stackOfParameters)
    sparse_indices, sparse_factors, not_used = IndexSet.getIndexSet(indexSets)
    rows = len(sparse_indices)
    cols = len(sparse_indices[0])

    # For storage we use dictionaries
    individual_tensor_coefficients = {}
    individual_tensor_indices = {}
    points_store = {}
    indices = np.zeros((rows))

    for i in range(0,rows):
        orders = sparse_indices[i,:]
        K, I, points = getPseudospectralCoefficients(self, function, orders + 1)
        individual_tensor_indices[i] = I
        individual_tensor_coefficients[i] =  K
        points_store[i] = points
        indices[i] = len(I)

    sum_indices = int(np.sum(indices))
    store = np.zeros((sum_indices, dimensions+1))
    points_saved = np.zeros((sum_indices, dimensions))
    counter = int(0)
    for i in range(0,rows):
        for j in range(0, int(indices[i])):
             store[counter,0] = sparse_factors[i] * individual_tensor_coefficients[i][j]
             for d in range(0, dimensions):
                 store[counter,d+1] = individual_tensor_indices[i][j][d]
                 points_saved[counter,d] = points_store[i][j][d]
             counter = counter + 1

    # Now we use a while loop to iteratively delete the repeated elements while summing up the
    # coefficients!
    index_to_pick = 0
    flag = 1
    counter = 0

    rows = len(store)

    final_store = np.zeros((sum_indices, dimensions + 1))
    while(flag != 0):

        # find the repeated indices
        rep = find_repeated_elements(index_to_pick, store)
        coefficient_value = 0.0

        # Sum up all the coefficient values
        for i in range(0, len(rep)):
            actual_index = rep[i]
            coefficient_value = coefficient_value + store[actual_index,0]

        # Store into a new array
        final_store[counter,0] = coefficient_value
        final_store[counter,1::] = store[index_to_pick, 1::]
        counter = counter + 1

        # Delete index from store
        store = np.delete(store, rep, axis=0)

        # How many entries remain in store?
        rows = len(store)
        if rows == 0:
            flag = 0

    indices_to_delete = np.arange(counter, sum_indices, 1)
    final_store = np.delete(final_store, indices_to_delete, axis=0)

    # Now split final store into coefficients and their index sets!
    coefficients = np.zeros((1, len(final_store)))
    for i in range(0, len(final_store)):
        coefficients[0,i] = final_store[i,0]

    # Splitting final_store to get the indices!
    indices = final_store[:,1::]

    # Now just double check to make sure they are all integers
    for i in range(0, len(indices)):
        for j in range(0, dimensions):
            indices[i,j] = int(indices[i,j])
    
    K = np.column_stack(coefficients)
    return K, indices, points_saved

# Efficient kronecker product multiplication
# Adapted from David Gelich and Paul Constantine's kronmult.m
def efficient_kron_mult(Q, Uc):
    N = len(Q)
    n = np.zeros((N,1))
    nright = 1
    nleft = 1
    for i in range(0,N-1):
        rows_of_Q = len(Q[i])
        n[i,0] = rows_of_Q
        nleft = nleft * n[i,0]

    nleft = int(nleft)
    n[N-1,0] = len(Q[N-1]) # rows of Q[N]

    for i in range(N-1, -1, -1):
        base = 0
        jump = n[i,0] * nright
        for k in range(0, nleft):
            for j in range(0, nright):
                index1 = base + j
                index2 = int( base + j + nright * (n[i] - 1) )
                indices_required = np.arange(int( index1 ), int( index2 + 1 ), int( nright ) )
                small_Uc = np.mat(Uc[:, indices_required])
                temp = np.dot(Q[i] , small_Uc.T )
                temp_transpose = temp.T
                Uc[:, indices_required] = temp_transpose
            base = base + jump
        temp_val = np.max([i, 0]) - 1
        nleft = int(nleft/(1.0 * n[temp_val,0] ) )
        nright = int(nright * n[i,0])

    return Uc