
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *


from yaml.events import Event

class ExtendedEvent(Event):
        pass

class ExtendedMarkerEvent(ExtendedEvent):
        def __init__(self, mark=None):
                self.start_mark = mark
                self.end_mark = mark

class ElementEvent(ExtendedMarkerEvent):
        def __init__(self, index, mark=None):
                super(ElementEvent, self).__init__(mark)
                self.index = index

class PairEvent(ExtendedMarkerEvent):
        def __init__(self, mark=None):
                super(PairEvent, self).__init__(mark)

class PairKeyEvent(ExtendedMarkerEvent):
        def __init__(self, mark=None):
                super(PairKeyEvent, self).__init__(mark)

class PairValueEvent(ExtendedMarkerEvent):
        def __init__(self, mark=None):
                super(PairValueEvent, self).__init__(mark)


class ElementStartEvent(ElementEvent):
        def __init__(self, index, mark=None):
                super(ElementStartEvent, self).__init__(index, mark)

class ElementEndEvent(ElementEvent):
        def __init__(self, index, mark=None):
                super(ElementEndEvent, self).__init__(index, mark)

class PairStartEvent(PairEvent):
        def __init__(self, mark=None):
                super(PairStartEvent, self).__init__(mark)

class PairEndEvent(PairEvent):
        def __init__(self, mark=None):
                super(PairEndEvent, self).__init__(mark)

class PairKeyStartEvent(PairKeyEvent):
        def __init__(self, mark=None):
                super(PairKeyStartEvent, self).__init__(mark)

class PairKeyEndEvent(PairKeyEvent):
        def __init__(self, mark=None):
                super(PairKeyEndEvent, self).__init__(mark)

class PairValueStartEvent(PairValueEvent):
        def __init__(self, mark=None):
                super(PairValueStartEvent, self).__init__(mark)

class PairValueEndEvent(PairValueEvent):
        def __init__(self, mark=None):
                super(PairValueEndEvent, self).__init__(mark)
