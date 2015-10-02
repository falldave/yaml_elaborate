
from __future__ import (absolute_import, division,
                                print_function, unicode_literals)
from builtins import *


"""

Saxifier
========

The idea of this module is to convert the event stream from either a PyYAML
parser or a ``yaml_elaborate`` filter directly and (for the most part)
losslessly into a stream of SAX events. This should make it possible to
perform useful processing on a YAML document using XML-based tools, in
particular XPath and XSLT processors, and to embed the structure, rather than
just the raw text, of a YAML document into a larger XML document.

Namespaces
----------

The output makes use of three XML namespaces:

-   The unnamed/default namespace:
    -   *Essential attributes* are the attributes listed as *Essential Event
        Attributes* in the LibYAML documentation. They express specific
        information provided by the parser.
        -   Note that the ``plain-implicit`` and ``quoted-implicit``
            attributes on scalars are omitted from the essential attributes.
            A single ``implicit`` attribute is substituted which contains the
            value of ``plain-implicit``, if the ``style`` is ``plain``, or
            ``quoted-implicit`` otherwise.
-   The ``ess`` namespace, whose ``xmlns`` name is
    ``https://github.com/falldave/yaml_elaborate/saxifier/0.0/essential``:
    -   *Essential elements* are the elements based on events defined by
        PyYAML/LibYAML. They express specific structural information that is
        necessary for determining the meaning of the document.
-   The ``sty`` namespace, whose ``xmlns`` name is
    ``https://github.com/falldave/yaml_elaborate/saxifier/0.0/stylistic``.
    -   *Stylistic attributes* are the attributes listed as *Stylistic Event
        Attributes* in the LibYAML documentation. They express parsing
        information about the input and information
        that may be useful for purposes of presentation, but they do not
        impact the meaning of the data in the document itself and can
        typically be ignored and discarded.
    -   *Ancillary elements* are the elements based on the new events defined
        by ``yaml_elaborate``. These new events serve only to make explicit
        certain structural information that could be reckoned without them.
        A document with ancillary elements is semantically identical to a
        document that has had all ancillary elements repeatedly replaced
        directly by their contents until no ancillary elements remain.

Elements and attributes
-----------------------

These elements and attributes are defined:

-   Any elements may have these attributes:
    -   ``sty:start-source``: The name of the file or stream where this
        element began.
    -   ``sty:start-line``: The 1-based line number where this element began.
    -   ``sty:start-column``: The 1-based column number where this element
        began.
    -   ``sty:end-source``: The name of the file or stream where this element
        ended.
    -   ``sty:end-line``: The 1-based line number where this element ended.
    -   ``sty:end-column``: The 1-based column number where this element
        ended.
-   Essential elements: These are the elements based on events defined in
    PyYAML/LibYAML. They express specific information provided by the parser.
    -   ``ess:stream``
        -   ``sty:encoding``: The document encoding of the input.
    -   ``ess:document``
        -   ``sty:version``: The version specified in the ``%YAML`` directive
            of the input.
        -   ``sty:tags``: The tags specified in the ``%TAG`` directive of the
            input.
    -   Value elements
        -   ``ess:alias``: Indicates the anchor of another value element that
            should be inserted in this element's stead.
            -   ``anchor``: The anchor being dereferenced.
        -   ``ess:scalar``: A non-aggregate value. The content of this element
            is the scalar value with any quoting already removed.
            -   ``anchor``: The anchor whose referent is this scalar.
            -   ``tag``: The tag for this scalar.
            -   ``sty:plain-implicit``: ``true`` if omitting the tag would not
                affect this value when presented in plain style; ``false``
                otherwise.
            -   ``sty:quoted-implicit``: ``true`` if omitting the tag would not
                affect this value when presented in any non-plain style;
                ``false`` otherwise.
            -   ``sty:style``: The style in which the value was presented.
                Possible values are ``plain``, ``single-quoted``,
                ``double-quoted``, ``literal``, and ``folded``. Omission of
                this attribute means the same as ``plain``.
        -   ``ess:sequence``: A linear sequence. If the ancillary elements are
            enabled, contains zero or more ``sty:element``. Otherwise,
            contains zero or more value elements.
            -   ``anchor``: The anchor whose referent is this sequence.
            -   ``tag``: The tag for this sequence.
            -   ``implicit``: ``true`` if omitting the tag would not affect
                the value of this sequence, ``false`` otherwise.
            -   ``sty:style``: The style of this sequence, either ``block`` or
                ``flow``.
        -   ``ess:mapping``: A set of key-value pairs. If the ancillary
            elements are enabled, contains zero or more ``sty:pair``.
            Otherwise, contains an even number of value elements in which the
            first, third, fifth, etc. value element is a pair's key element
            and the value element immediately following the pair's key element
            is the pair's value element.
            -   ``anchor``: The anchor whose referent is this sequence.
            -   ``tag``: The tag for this sequence.
            -   ``implicit``: ``true`` if omitting the tag would not affect
                the value of this sequence, ``false`` otherwise.
            -   ``sty:style``: The style of this sequence, either ``block`` or
                ``flow``.
-   Ancillary elements: These are the elements based on events defined in
    ``yaml_elaborate``. They express information redundantly with that of the
    essential elements, but may make addressing particular items easier when
    using XPath.
    -   ``sty:element``: An element of a sequence. Contains exactly one value
        element, which is the element's value.
        -   ``sty:index``: The zero-based index of this element within the
            sequence.
    -   ``sty:pair``: A pair within a mapping. Contains exactly a
        ``sty:pair-key`` followed by a ``sty:pair-value``.
    -   ``sty:pair-key``: The key of a pair. Contains exactly one value
        element, which is the pair's key.
    -   ``sty:pair-value``: The value of a pair. Contains exactly one value
        element, which is the pair's value.


"""

__all__ = ['Saxifier']

import re
from collections import namedtuple
from xml.sax.xmlreader import AttributesNSImpl

_EventTypeInfo = namedtuple('_EventTypeInfo', ['node_name', 'node_event',
    'is_essential', 'object_properties', 'essential_attributes'])

_event_types_seq = (
    _EventTypeInfo('stream', 'start', True,
        frozenset(('encoding', 'start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('stream', 'end', True,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('document', 'start', True,
        frozenset(('explicit', 'version', 'tags', 'start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('document', 'end', True,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('sequence', 'start', True,
        frozenset(('anchor', 'tag', 'implicit', 'flow_style', 'start_mark',
            'end_mark')),
        frozenset(('anchor', 'tag', 'implicit'))
        ),
    _EventTypeInfo('sequence', 'end', True,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('mapping', 'start', True,
        frozenset(('anchor', 'tag', 'implicit', 'flow_style', 'start_mark',
            'end_mark')),
        frozenset(('anchor', 'tag', 'implicit'))
        ),
    _EventTypeInfo('mapping', 'end', True,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('alias', 'found', True,
        frozenset(('anchor', 'start_mark', 'end_mark')),
        frozenset(('anchor',))
        ),
    _EventTypeInfo('scalar', 'found', True,
        frozenset(('anchor', 'tag', 'implicit', 'value', 'style',
            'start_mark', 'end_mark')),
        frozenset(('anchor', 'tag', 'implicit'))
        ),
    _EventTypeInfo('element', 'start', False,
        frozenset(('index', 'start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('element', 'end', False,
        frozenset(('index', 'start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('pair', 'start', False,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('pair', 'end', False,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('pair-key', 'start', False,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('pair-key', 'end', False,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('pair-value', 'start', False,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    _EventTypeInfo('pair-value', 'end', False,
        frozenset(('start_mark', 'end_mark')),
        frozenset(())
        ),
    )

_event_types = dict(
        ((info.node_name, info.node_event), info)
        for info in _event_types_seq
        )

_essential_prefix = 'ess'
_stylistic_prefix = 'sty'

_essential_nsname = (
    'https://github.com/falldave/yaml_elaborate/saxifier/0.0/essential')
_stylistic_nsname = (
    'https://github.com/falldave/yaml_elaborate/saxifier/0.0/stylistic')


_scalar_style_names = {
        None: "plain",
        "": "plain",
        "'": "single-quoted",
        '"': "double-quoted",
        "|": "literal",
        ">": "folded",
        }

class Saxifier(object):
    def __init__(self, events, handler, partial=False,
            include_stylistic_attributes=False,
            include_ancillary_elements=True,
            essential_prefix=None,
            stylistic_prefix=None,
            hide_implicit_if_true=False):

        self._events = events
        self._handler = handler
        self._partial = partial
        self._include_stylistic_attributes = include_stylistic_attributes
        self._include_ancillary_elements = include_ancillary_elements
        self._hide_implicit_if_true = hide_implicit_if_true

        if stylistic_prefix is None:
            stylistic_prefix = 'sty'

        if essential_prefix == stylistic_prefix:
            raise ValueError(
                'Essential and stylistic prefixes cannot be identical')

        # nsname, prefix, use with elements, use with attributes
        attr_none_def = (None, None, False, True)
        elem_ess_def = (_essential_nsname, essential_prefix, True, False)
        all_sty_def = (_stylistic_nsname, stylistic_prefix, True, True)

        namespace_table = [attr_none_def, elem_ess_def]

        if (self._include_ancillary_elements or
                self._include_stylistic_attributes):
            namespace_table.append(all_sty_def)


        self._nsname_prefix_all = dict()
        self._nsname_prefix_for_elements = dict()
        self._nsname_prefix_for_attributes = dict()
        nsnames_to_register = []
        
        for nsname, prefix, for_elements, for_attributes in namespace_table:
            if nsname is not None:
                nsnames_to_register.append(nsname)
            self._nsname_prefix_all[nsname] = prefix
            if for_elements:
                self._nsname_prefix_for_elements[nsname] = prefix
            if for_attributes:
                self._nsname_prefix_for_attributes[nsname] = prefix

        self._nsnames_to_register = tuple(nsnames_to_register)

    def run(self):
        if not self._partial:
            self._handler.startDocument()

        for nsname in self._nsnames_to_register:
            prefix = self._nsname_prefix_all[nsname]
            self._handler.startPrefixMapping(prefix, nsname)

        for event in self._events:
            event_type_name = type(event).__name__
            info = self._event_type_info(event_type_name)
            self._each_event(event, event_type_name, info)

        for nsname in reversed(self._nsnames_to_register):
            prefix = self._nsname_prefix_all[nsname]
            self._handler.startPrefixMapping(prefix, nsname)

        if not self._partial:
            self._handler.endDocument()

    def _get_xml_element_nsname(self, is_essential):
        return _essential_nsname if is_essential else _stylistic_nsname

    def _get_xml_attr_nsname(self, is_essential):
        return None if is_essential else _stylistic_nsname

    def _each_event(self, event, event_type_name, info):
        # node_name, node_event, is_essential, object_properties,
        # essential_attributes
        node_name = info.node_name

        # Skip ancillary elements if disabled
        if not (self._include_ancillary_elements or info.is_essential):
            return

        event_nsname = self._get_xml_element_nsname(info.is_essential)

        p = self._fetch_properties(event, *(info.object_properties))

        if node_name in ['element', 'pair', 'pair-key', 'pair-value']:
            # We know that the synthetic element, pair, pair-key, and
            # pair-value start/end marks are redundant with other easily
            # available information. We'll elide it here.
            p.pop('start_mark')
            p.pop('end_mark')
        else:
            # Flatten start_mark and end_mark
            self._convert_mark(p, 'start')
            self._convert_mark(p, 'end')

        # Rework flow_style
        self._convert_flow_style(p)

        is_plain_scalar = False

        if node_name == 'scalar':
            # Human-readable name for scalar style
            try:
                orig = p['style']
                p['style'] = _scalar_style_names.get(orig, None)
                if p['style'] is None or p['style'] == 'plain':
                    is_plain_scalar = True
            except KeyError:
                pass

        # Flatten two-part implicit
        self._convert_two_part_implicit(p, is_plain_scalar)

        # Normalize names and stringify values
        ad = self._prep_unqualified_attributes_dict(p)

        # Annotate property keys with prefixes
        qp = dict()
        for key, value in ad.viewitems():
            is_attr_essential = key in info.essential_attributes

            # Skip stylistic attributes if disabled
            if not (self._include_stylistic_attributes or is_attr_essential):
                continue

            # Skip implicit="true" if hiding implicit="true"
            if (self._hide_implicit_if_true
                    and (key, value) == ('implicit', 'true')):
                continue

            attr_nsname = self._get_xml_attr_nsname(is_attr_essential)
            qp[attr_nsname, key] = value
        
        if node_name == 'scalar':
            text = str(p.pop('value'))
            self._simple_element(event_nsname, node_name, text, qp)
        elif node_name == 'alias':
            self._empty_element(event_nsname, node_name, qp)
        else:
            if info.node_event == 'start':
                self._start_element(event_nsname, node_name, qp)
            else:
                self._end_element(event_nsname, node_name)


    def _fetch_properties(self, obj, *property_names):
        # Using a set of names of meaningful properties, create a dict from
        # the values of those properties on an object. If some property is not
        # present, no key is added to the dict.
        result = dict()

        for name in property_names:
            try:
                result[name] = getattr(obj, name)
            except AttributeError:
                pass

        return result

    def _convert_two_part_implicit(self, p, is_plain_scalar):
        try:
            (implicit_if_plain, implicit_if_not_plain) = p['implicit']
            implicit = (
                    implicit_if_plain
                    if is_plain_scalar
                    else implicit_if_not_plain)

            p['implicit'] = implicit
            p['plain-implicit'] = implicit_if_plain
            p['quoted-implicit'] = implicit_if_not_plain
        except KeyError:
            # no 'implicit' present
            pass
        except TypeError:
            # 'implicit' is present but isn't a 2-element iterable
            pass

    def _convert_flow_style(self, p):
        # flow_style -> style="flow"
        # not flow_style -> style="block"
        try:
            flow_style = p.pop('flow_style')
            p['style'] = 'flow' if flow_style else 'block'
        except KeyError:
            pass

    def _convert_mark(self, p, prefix):
        # Replace an x_mark entry with x_source, x_line, and x_column entries.
        mark_key = prefix + '_mark'
        try:
            mark = p.pop(mark_key)
        except KeyError:
            pass

        if mark:
            p[prefix + '-source'] = mark.name
            p[prefix + '-line'] = mark.line + 1
            p[prefix + '-column'] = mark.column + 1

    def _combine_dicts(self, *sources, **additional_items):
        result = dict()

        all = sources + (additional_items,)

        for d in all:
            result.update(d)

        return result

    def _dashify_iteritems_keys(self, items):
        for k, v in items:
            yield (self._xml_like_from_camel(k), v)

    def _dashify_keys(self, d):
        return dict(self._dashify_iteritems_keys(d.viewitems()))

    def _stringify_iteritems_values(self, items):
        for k, v in items:
            if v is None:
                continue
            elif v is True or v is False:
                # JSON-like booleans
                v = str(v).lower()
            else:
                v = str(v)
            yield (k, v)

    def _stringify_values(self, d):
        return dict(self._stringify_iteritems_values(d.viewitems()))

    def _prep_unqualified_attributes_dict(self, *attr_dicts, **attr_kwargs):
        d = self._combine_dicts(*attr_dicts, **attr_kwargs)
        d = self._dashify_keys(d)
        d = self._stringify_values(d)
        return d

    # In the context of SAX with namespace support,
    # ``nsname`` means what's usually called the namespace URI
    # ``name`` means (nsname, local_name)
    # ``qname`` means "someprefix:somename" or "someunprefixedname"
    # ``local_name`` means the part of ``qname`` with the prefix and ':'
    #     removed

    def _make_qname(self, prefix, local_name):
        if prefix is None:
            return local_name
        else:
            return prefix + ':' + local_name

    def _get_element_qname(self, nsname, local_name):
        prefix = self._nsname_prefix_for_elements[nsname]
        return self._make_qname(prefix, local_name)

    def _get_attribute_qname(self, nsname, local_name):
        prefix = self._nsname_prefix_for_attributes[nsname]
        return self._make_qname(prefix, local_name)

    def _prep_attributes(self, qualified_attributes_dict=None):
        if qualified_attributes_dict is None:
            qualified_attributes_dict = dict()

        name_to_value = dict()
        name_to_qname = dict()

        for name, value in qualified_attributes_dict.viewitems():
            if value is None:
                continue

            (nsname, local_name) = name
            qname = self._get_attribute_qname(nsname, local_name)

            name_to_value[name] = value
            name_to_qname[name] = qname

        return AttributesNSImpl(name_to_value, name_to_qname)

    def _start_element(self, nsname, local_name,
            qualified_attributes_dict=None):
        name = (nsname, local_name)
        qname = self._get_element_qname(nsname, local_name)
        attrs = self._prep_attributes(qualified_attributes_dict)

        self._handler.startElementNS(name, qname, attrs)

    def _end_element(self, nsname, local_name):
        name = (nsname, local_name)
        qname = self._get_element_qname(nsname, local_name)
        self._handler.endElementNS(name, qname)

    def _simple_element(self, nsname, local_name, text,
            qualified_attributes_dict=None):
        self._start_element(nsname, local_name, qualified_attributes_dict)

        if text is not None:
            self._handler.characters(text)

        self._end_element(nsname, local_name)

    def _empty_element(self, nsname, local_name,
            qualified_attributes_dict=None):
        self._simple_element(nsname, local_name, None,
                qualified_attributes_dict)

    # Ideally [A-Z] would be [[:upper:]] or \p{Lu} instead (Python re appears
    # to support neither POSIX classes nor Unicode properties), but since all
    # current event names are ASCII-only anyway, this will do.
    _uppercase_pattern = re.compile(r'([A-Z]+)')

    # Once again, ideally [^A-Za-z0-9] would be [^[:alnum:]] or
    # [^\p{L&}\p{Nd}].
    _interword_pattern = re.compile(r'[^A-Za-z0-9]+')

    _trimming_pattern = re.compile(r'^-|-$')

    def _xml_like_from_camel(self, camel_name):
        """
        Turns a CamelCase name like (e.g. "FooBarBaz") into an XML-like name
        (e.g. "foo-bar-baz").
        """
        s = camel_name
        s = self._uppercase_pattern.sub(r' \1', s)
        s = self._interword_pattern.sub('-', s)
        s = self._trimming_pattern.sub('', s)
        return s.lower()


    _event_type_info_pattern = re.compile(r'^(.*?)(Start|End|)Event$')

    def _event_type_info(self, camel_name):
        # Extract meaningful parts of class name
        # (e.g. "StreamStartEvent" -> "stream", "start") then look them up in
        # the event types table. The CamelCasing is adjusted to hyphenated
        # lower-case (e.g. "PairKeyStartEvent" -> "pair-key", "start").
        node_name = None
        node_event = None

        match = self._event_type_info_pattern.search(camel_name)
        if match:
            node_name = self._xml_like_from_camel(match.group(1))
            node_event = match.group(2).lower()
            if node_event == '':
                node_event = 'found'
        else:
            node_name = self._xml_like_from_camel(camel_name)
        
        key = (node_name, node_event)

        try:
            return _event_types[key]
        except KeyError:
            raise ValueError("%r is not a known event" % camel_name)

