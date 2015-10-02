
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *



import yaml
from .elaborator import Elaborator, ElaboratorSettings
from .saxifier import Saxifier

def _collapse(*dicts):
    result = {}
    for d in dicts:
        result.update(d)
    return result

def _get_settings(*args, **kwargs):
    all = args + (kwargs,)
    collapsed = _collapse(*all)

    return ElaboratorSettings.default._replace(**collapsed)

def process_stream(stream, Loader=yaml.Loader, **kwargs):
    """
    Elaborate on the first YAML document in the stream.
    """
    loader = Loader(stream)
    settings = _get_settings(kwargs, parser=loader)
    
    try:
        elaborator = Elaborator(settings)
        for ee in elaborator.process(): yield ee
    finally:
        loader.dispose()

def saxify_event_stream(event_stream, sax_handler, **kwargs):
    return Saxifier(event_stream, sax_handler, **kwargs).run()

