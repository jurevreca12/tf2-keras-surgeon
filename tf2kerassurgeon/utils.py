"""Utilities used across other modules."""
import warnings
import numpy as np
import collections
from tensorflow.keras.layers import Layer
from tensorflow.keras.activations import linear


def clean_copy(model):
    """Returns a copy of the model without other model uses of its layers."""
    weights = model.get_weights()
    new_model = model.__class__.from_config(model.get_config())
    new_model.set_weights(weights)
    return new_model


def get_channels_attr(layer):
    layer_config = layer.get_config()
    if 'units' in layer_config.keys():
        channels_attr = 'units'
    elif 'filters' in layer_config.keys():
        channels_attr = 'filters'
    else:
        raise ValueError('This layer has not got any channels.')
    return channels_attr

def get_node_depth(model, node):
    """Get the depth of a node in a model.

    Arguments:
        model: Keras Model object
        node: Keras Node object

    Returns:
        The node depth as an integer. The model outputs are at depth 0.

    Raises:
        KeyError: if the node is not contained in the model.
    """
    for (depth, nodes_at_depth) in get_nodes_by_depth(model).items():
        if node in nodes_at_depth:
            return depth
    raise KeyError('The node is not contained in the model.')


def find_nodes_in_model(model, layer):
    """Find the indices of layer's inbound nodes which are in model"""
    model_nodes = get_model_nodes(model)
    node_indexes = [] # Renamed this since it was confusing with TF/Keras Node.node_indices
    for i, node in enumerate(single_list(get_inbound_nodes(layer))):
        if node in model_nodes:
            node_indexes.append(i)
    return node_indexes


def get_model_nodes(model):
    """Return all nodes in the model"""
    return [node for v in get_nodes_by_depth(model).values() for node in v]


def get_shallower_nodes(node):
    possible_nodes = get_outbound_nodes(node.outbound_layer)
    next_nodes = []
    for n in possible_nodes:
        for input_tensor in single_list(n.input_tensors):
            layer, node_index, tensor_index = input_tensor._keras_history
            if layer._inbound_nodes[node_index] is node:
                next_nodes.append(n)
    return next_nodes


def get_node_inbound_nodes(node):
    inbound_nodes = []
    for layer in single_list(node.inbound_layers):
        for n in get_inbound_nodes(layer):
            for output_tensor in single_list(n.output_tensors):
                if output_tensor.ref() in map(lambda x:x.ref(), single_list(node.input_tensors)):
                    inbound_nodes.append(n)
    return inbound_nodes


def get_inbound_nodes(layer):
    try:
        return getattr(layer, '_inbound_nodes')
    except AttributeError:
        warnings.warn("Please update keras to version 2.1.3 or greater."
                      "Support for earlier versions will be dropped in a "
                      "future release.")
        return layer.inbound_nodes


def get_outbound_nodes(layer):
    try:
        return getattr(layer, '_outbound_nodes')
    except AttributeError:
        warnings.warn("Please update keras to version 2.1.3 or greater."
                      "Support for earlier versions will be dropped in a "
                      "future release.")
        return layer.outbound_nodes


def get_nodes_by_depth(model):
    try:
        return getattr(model, '_nodes_by_depth')
    except AttributeError:
        warnings.warn("Please update keras to version 2.1.3 or greater."
                      "Support for earlier versions will be dropped in a "
                      "future release.")
        return model.nodes_by_depth


def get_node_index(node):
    for i, n in enumerate(single_list(get_inbound_nodes(node.outbound_layer))):
        if node == n:
            return i


def find_activation_layer(layer, node_index):
    """

    Args:
        layer(Layer):
        node_index:
    """
    output_shape = layer.get_output_shape_at(node_index)
    maybe_layer = layer
    node = single_list(get_inbound_nodes(maybe_layer))[node_index]
    # Loop will be broken by an error if an output layer is encountered
    while True:
        # If maybe_layer has a nonlinear activation function return it and its index
        activation = getattr(maybe_layer, 'activation', linear)
        if activation.__name__ != 'linear':
            if maybe_layer.get_output_shape_at(node_index) != output_shape:
                ValueError('The activation layer ({0}), does not have the same'
                           ' output shape as {1}'.format(maybe_layer.name,
                                                         layer.name))
            return maybe_layer, node_index

        # If not, move to the next layer in the datastream
        next_nodes = get_shallower_nodes(node)
        # test if node is a list of nodes with more than one item
        if len(next_nodes) > 1:
            ValueError('The model must not branch between the chosen layer'
                       ' and the activation layer.')
        node = single_list(next_nodes)[0]
        node_index = get_node_index(node)
        maybe_layer = node.outbound_layer

        # Check if maybe_layer has weights, no activation layer has been found
        if maybe_layer.weights and (
                not maybe_layer.__class__.__name__.startswith('Global')):
            AttributeError('There is no nonlinear activation layer between {0}'
                           ' and {1}'.format(layer.name, maybe_layer.name))

            
def single_element(x):
    """If x contains a single element, return it; otherwise return x"""
    try:
        if len(x) == 1:
            x = x[0]
    except TypeError:
       return x
    return x


def single_list(x):
    """ If an Element is a single instead of a list, when a list is expected it created a single element list"""
    try:
        enumerate(x)
    except TypeError: 
        return [x]
    return x


def all_equal(iterator):
    try:
        iterator = iter(iterator)
        first = next(iterator)
        return all(
            np.array_equal(first, rest) for rest in iterator)
    except StopIteration:
        return True


class MeanCalculator:
    def __init__(self, sum_axis):
        self.values = None
        self.n = 0
        self.sum_axis = sum_axis

    def add(self, v):
        if self.values is None:
            self.values = v.sum(axis=self.sum_axis)
        else:
            self.values += v.sum(axis=self.sum_axis)
        self.n += v.shape[self.sum_axis]

    def calculate(self):
        return self.values / self.n
