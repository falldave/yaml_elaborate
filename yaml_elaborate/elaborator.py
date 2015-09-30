
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *



__all__ = ['Elaborator', 'ElaboratorError']

from yaml.error import MarkedYAMLError
from yaml.events import (StreamStartEvent, StreamEndEvent,
        DocumentStartEvent, DocumentEndEvent,
        SequenceStartEvent, SequenceEndEvent,
        MappingStartEvent, MappingEndEvent,
        AliasEvent,
        ScalarEvent)
from yaml.nodes import ScalarNode, SequenceNode, MappingNode

from .events import (ElementStartEvent, ElementEndEvent, PairStartEvent,
        PairEndEvent, PairKeyStartEvent, PairKeyEndEvent,
        PairValueStartEvent, PairValueEndEvent)

from collections import namedtuple


def _drain(*generators):
    for generator in generators:
        for item in generator:
            pass

# _Sink

class _Sink(object):
    # Class for callable objects that stash a value.
    def __init__(self, initial_value=None):
        self.value = initial_value

    def __call__(self, new_value):
        self.value = new_value

def _put(sink_callable, value):
    # Call ``sink_callable(value)`` unless ``sink_callable`` is missing.
    if sink_callable:
        sink_callable(value)



# ElaboratorError

class ElaboratorError(MarkedYAMLError):
    pass

def _err_extra_document(first_mark, second_mark):
    return ElaboratorError(
            "expected a single document in the stream", first_mark,
            "but found another document", second_mark)

def _err_undefined_alias(anchor, start_mark):
    return ElaboratorError(None, None, "found undefined alias %r" % anchor,
            start_mark)

def _err_duplicate_anchor(anchor, first_mark, second_mark):
    return ElaboratorError(
            "found duplicate anchor %r; first occurrence" % anchor,
            first_mark,
            "second occurrence",
            second_mark)


class ElaboratorUnexpectedEventTypeError(ElaboratorError):
    # Error specifically resulting from the failure of a node type check
    pass

def _err_unexpected_event_type(event_type, start_mark, expected_types=None):
    submessage = ""
    if expected_types is not None:
        try:
            types = [type for type in iter(expected_types)]
        except TypeError:
            # If a single type is given instead of a list
            types = [expected_types]

        count = len(types)
        listed_types = ", ".join(x.__name__ for x in types)

        if count == 1:
            submessage = " (expected %r)" % listed_types
        elif count > 1:
            submessage = " (expected one of %r)" % listed_types

    message = ("found unexpected event type %r" % event_type.__name__)
    message += submessage

    return ElaboratorUnexpectedEventTypeError(None, None, message, start_mark)


# ElaboratorSettings

_default_elaborator_settings_table = (
        ('parser', None),
        ('resolver', None),
        ('composing_fully', False),
        ('resolving_tags', True),
        ('with_extra_events', True),
        ('including_ends', None),
        ('single', False),
        ('flat', False),
        )

class ElaboratorSettings(namedtuple('ElaboratorSettings',
        [k for k, v in _default_elaborator_settings_table])):
    """
    Type representing options for the elaborator. This inherits from a
    ``namedtuple``; the default elaborator settings are in
    ``default_elaborator_settings`` and settings can be modified into a new
    object using the ``_replace()`` method (see docs for
    ``collections.namedtuple``).

    ``parser`` is a YAML parser (e.g. ``yaml.parser.Parser``) object.
    Typically, a ``yaml.Loader`` or similar is used. Any object that
    implements the methods ``peek_event()``, ``check_event()``, and
    ``get_event()`` in the same idiom may be used.

    ``resolver`` is a YAML resolver (e.g. ``yaml.resolver.BaseResolver``)
    object. Typically, this is left as ``None`` (default), causing ``parser``
    to also be used as the resolver (which makes sense if e.g. a
    ``yaml.Loader`` is used). Any object that implements the methods
    ``descend_resolver()``, ``ascend_resolver()``, and ``resolve()`` in the
    same idiom may be used. If ``parser`` does not implement this interface,
    then this cannot be left blank unless ``resolving_tags`` is false.

    If ``flat`` is true (default), the resulting generator yields
    each event one at a time. If false, it yields a sequence of generators,
    one per document (plus a separate generator for ``StreamStartEvent`` at
    the beginning and another for ``StreamEndEvent`` at the end, if ends are
    included), which themselves yield the events.

    If the ``including_ends`` setting is true, the ``StreamStartEvent`` and
    ``StreamEndEvent`` are included with the output. If the setting is false,
    they are omitted. If the setting is ``None`` (default), then the value of
    the ``flat`` setting is used (that is, ends included if flat but omitted
    if not flat).

    If ``composing_fully`` is true, a complete tree representation of the
    current document is composed in memory as events are handled. If false
    (default), a reduced tree representation is used which holds fewer nodes
    in memory while still ideally providing the resolver with enough
    information to resolve tags; this may theoretically make path-based tag
    resolution less accurate (test cases are needed).

    If ``resolving_tags`` is true (default), ``resolver`` is used to resolve
    tags, which are then used to rewrite the tags in the events themselves. If
    false, the event tags are left as-is.

    If ``with_extra_events`` is true (default), the original stream of events
    is augmented with additional events in ``yamlextevents.events`` which mark
    the beginning and end of every sequence element, mapping pair, mapping
    pair key, and mapping pair value. If false, no new events are added to the
    stream.

    If ``single`` is false (default), an arbitrary number of documents will be
    accepted before the end of the stream. If true, zero documents or one
    document will be accepted; if the start of a second document appears
    before the end of the stream, an error is raised.
    """
    pass

_default_elaborator_settings = ElaboratorSettings._make(
        v for k, v in _default_elaborator_settings_table)

ElaboratorSettings.default = _default_elaborator_settings


# Elaborator

class Elaborator(object):
    """
    Produces a modified stream of events from a YAML parser.
    """

    def __init__(self, settings=None):
        if settings is None:
            settings = _default_elaborator_settings

        parser = settings.parser
        resolver = settings.resolver

        self._events = parser

        if not self._events:
            raise TypeError("Setting 'parser' must be set")

        if not settings.resolving_tags:
            resolver = None
        elif resolver is None:
            # The caller may simply pass a Loader object.
            resolver = parser
        self._resolver = resolver

        self._settings = settings

        self._anchors = None

    def process(self):
        """
        Accepts an entire stream, yielding output according to the settings
        for this object.
        """
        including_ends = self._settings.including_ends
        if including_ends is None:
            including_ends = self._settings.flat

        single = self._settings.single

        document_event_generators = self._process_stream(including_ends, single)

        if self._settings.flat:
            # Flatten
            for document_event_generator in document_event_generators:
                for ee in document_event_generator:
                    yield ee
        else:
            for document_event_generator in document_event_generators:
                yield document_event_generator

    def _process_stream(self, including_ends, single):
        # Accept entire YAML event stream.
        # Output is always nonflat (all flattening occurs in process()).
        start_events = self._process_stream_start_event()
        if including_ends:
            yield start_events
        else:
            _drain(start_events)

        if single:
            # Accept 0 or 1 document.
            sink_document = _Sink()
            if self._has_more():
                yield self._accept_document(sink_document)
            document = sink_document.value

            # Reject non-StreamEndEvent as extra document.
            end_events = self._process_single_stream_end_event(document)
        else:
            # Accept any number of documents.
            while self._has_more():
                yield self._accept_document(None)

            end_events = self._process_stream_end_event()

        if including_ends:
            yield end_events
        else:
            _drain(end_events)



    # Compose-and-yield methods

    def _accept_document(self, sink_node):
        try:
            self._anchors = {}

            for ee in self._drop_next_event_if(DocumentStartEvent, True):
                yield ee

            for ee in self._accept_any_value(None, None, sink_node):
                yield ee

            for ee in self._drop_next_event_if(DocumentEndEvent, True):
                yield ee
        finally:
            self._anchors = None

    def _accept_concrete_value(self, parent, index, sink_node):
        # Accept a Scalar, Sequence, or Mapping
        anchor = self._event_peek().anchor
        self._validate_anchor(anchor)

        self._resolver_descend(parent, index)

        if self._event_peek_isa(ScalarEvent):
            events = self._accept_scalar(anchor, sink_node)
        elif self._event_peek_isa(SequenceStartEvent):
            events = self._accept_sequence(anchor, sink_node)
        elif self._event_peek_isa(MappingStartEvent):
            events = self._accept_mapping(anchor, sink_node)
        else:
            peeked_event = self._event_peek()
            expected_types = (ScalarEvent, SequenceStartEvent,
                    MappingStartEvent, AliasEvent)
            raise _err_unexpected_event_type(type(peeked_event),
                    peeked_event.start_mark, expected_types=expected_types)

        for ee in events: yield ee

        self._resolver_ascend()

    def _accept_any_value(self, parent, index, sink_node):
        # Accept an Alias, Scalar, Sequence, or Mapping.

        if self._event_peek_isa(AliasEvent):
            events = self._accept_alias(sink_node)
        else:
            events = self._accept_concrete_value(parent, index, sink_node)

        for ee in events: yield ee

    def _accept_alias(self, sink_referent):
        start_event = self._event_next()
        yield start_event
        # nb: no end_event here

        anchor = start_event.anchor
        if anchor not in self._anchors:
            raise _err_undefined_alias(anchor, start_event.start_mark)
        _put(sink_referent, self._anchors[anchor])

    def _accept_scalar(self, anchor, sink_node):
        start_event = self._event_next()
        # nb: no end_event here

        tag = self._resolve_tag(start_event.tag, ScalarNode,
                start_event.value, start_event.implicit)

        start_event.tag = tag
        yield start_event

        node = ScalarNode(tag, start_event.value, start_event.start_mark,
                start_event.end_mark, style=start_event.style)

        self._set_anchor(anchor, node)

        _put(sink_node, node)

    def _accept_sequence(self, anchor, sink_node):
        start_event = self._event_next()

        tag = self._resolve_tag(start_event.tag, SequenceNode, None,
                start_event.implicit)

        start_event.tag = tag
        yield start_event

        node = SequenceNode(tag, [], start_event.start_mark, None,
                flow_style=start_event.flow_style)

        self._set_anchor(anchor, node)

        index = 0
        while not self._event_peek_isa(SequenceEndEvent):
            if self._settings.with_extra_events:
                yield ElementStartEvent(index, self._event_peek().start_mark)

            sink_element = _Sink()

            for ee in self._accept_any_value(node, index, sink_element):
                yield ee

            if self._settings.composing_fully:
                node.value.append(sink_element.value)

            if self._settings.with_extra_events:
                yield ElementEndEvent(index, self._event_peek().start_mark)

            index += 1

        end_event = self._event_next()
        yield end_event

        node.end_mark = end_event.end_mark

        _put(sink_node, node)

    def _accept_mapping(self, anchor, sink_node):
        start_event = self._event_next()
        tag = self._resolve_tag(start_event.tag, MappingNode, None, start_event.implicit)

        start_event.tag = tag
        yield start_event

        node = MappingNode(tag, [], start_event.start_mark, None,
                flow_style=start_event.flow_style)

        self._set_anchor(anchor, node)

        while not self._event_peek_isa(MappingEndEvent):
            sink_key = _Sink()
            sink_value = _Sink()

            if self._settings.with_extra_events:
                mark = self._event_peek().start_mark
                yield PairStartEvent(mark)
                yield PairKeyStartEvent(mark)

            for ee in self._accept_any_value(node, None, sink_key): yield ee

            if self._settings.with_extra_events:
                mark = self._event_peek().start_mark
                yield PairKeyEndEvent(mark)
                yield PairValueStartEvent(mark)

            for ee in self._accept_any_value(node, sink_key.value,
                    sink_value): yield ee

            if self._settings.with_extra_events:
                mark = self._event_peek().start_mark
                yield PairValueEndEvent(mark)
                yield PairEndEvent(mark)

            if self._settings.composing_fully:
                node.value.append((sink_key.value, sink_value.value))

        end_event = self._event_next()
        yield end_event

        node.end_mark = end_event.end_mark

        _put(sink_node, node)

    # Support methods

    def _drop_next_event_if(self, event_type, required=False):
        if self._event_peek_isa(event_type):
            event = self._event_next()
            yield event
        elif required:
            peeked_event = self._event_peek()
            raise _err_unexpected_event_type(type(peeked_event),
                    peeked_event.start_mark, expected_types=event_type)

    def _drop_stream_start_event(self, required=False):
        return self._drop_next_event_if(StreamStartEvent, required)

    def _drop_stream_end_event(self, required=False):
        return self._drop_next_event_if(StreamEndEvent, required)

    def _process_stream_start_event(self):
        for ee in self._drop_stream_start_event(True): yield ee

    def _process_stream_end_event(self):
        for ee in self._drop_stream_end_event(True): yield ee

    def _process_single_stream_end_event(self, document):
        # Variation of _process_stream_end_event() that replaces the
        # unexpected event type error with an extra document error.
        try:
            for ee in self._process_stream_end_event(): yield ee
        except ElaboratorUnexpectedEventTypeError:
            # If consuming an end event fails, the next event is a non-end
            # event.
            peeked_event = self._event_peek()
            raise _err_extra_document(document.start_mark,
                    peeked_event.start_mark)

    def _has_more(self):
        return not self._event_peek_isa(StreamEndEvent)

    def _set_anchor(self, anchor, node):
        if anchor is not None:
            self._anchors[anchor] = node

    def _validate_anchor(self, anchor):
        if anchor is not None:
            if anchor in self._anchors:
                raise _err_duplicate_anchor(anchor,
                        self._anchors[anchor].start_mark, event.start_mark)

    def _resolve_tag(self, tag, kind, scalar_value, implicit):
        if self._settings.resolving_tags:
            if tag is None or tag == '!':
                tag = self._resolver_resolve(kind, scalar_value, implicit)
        return tag

    def _resolver_descend(self, parent, index):
        return self._resolver.descend_resolver(parent, index)

    def _resolver_ascend(self):
        return self._resolver.ascend_resolver()

    def _resolver_resolve(self, node_type, value, implicit):
        return self._resolver.resolve(node_type, value, implicit)

    def _event_peek_isa(self, event_type):
        return self._events.check_event(event_type)

    def _event_next(self):
        return self._events.get_event()

    def _event_peek(self):
        return self._events.peek_event()

