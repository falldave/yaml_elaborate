``yaml_elaborate``: An alternative event stream output for PyYAML
=================================================================

Synopsis
--------

::

    import yaml_elaborate

    import sys
    input_stream = sys.stdin

    # Default: A generator of documents, each a generator of events
    for document_events in yaml_elaborate.process_stream(input_stream):
        some_begin_document_function()
        for event in document_events:
            some_event_handler(event)
        some_end_document_function()

    # How to run almost exactly like yaml.parse()
    for event in yaml_elaborate.process_stream(input_stream,
            flat=True, # use just one generator instead of grouping each
                       # document into its own generator
            composing_fully=False, # don't construct fully formed internal
                                   # representation
            resolving_tags=False, # don't run resolver; each event's tag is
                                  # exactly as produced by the parser
            with_extra_events=False, # don't produce additional events for
                                     # start/end of sequence elements, mapping
                                     # pairs, mapping pair keys, and mapping
                                     # pair values
            including_ends=True, # include ElementStartEvent/ElementEndEvent
            single=False, # Don't reject due to multiple documents
            ):
        some_event_handler(event)

Description
-----------

This library builds on the functionality of PyYAML (around 3.11), and is
inspired by ``yaml.parse(stream)``, which is a generator that yields a
sequence of parse events, but with some tag-resolving functionality
borrowed from ``yaml.compose[_all](stream)`` and some additional events
that may be of interest to those creating novel alternative
serializations for YAML.

The primary method
``yaml_elaborate.process_stream(stream, Loader?, **options)`` loads a
YAML document using a PyYAML-based loader and produces a generator that
yields events (or generators that themselves yield events) according to
these options:

-  ``composing_fully`` (default ``False``): If set, the document
   structure formed internally while parsing is fully detailed, meaning
   an in-memory structure of the entire document (similar to the result
   of ``yaml.compose[_all]()``) is built; the memory usage for
   tremendously large documents may be problematic (a large stream of
   small documents, however, is not impacted). If clear, workarounds are
   applied to limit the in-memory structure as closely as possible to
   only the item currently being parsed and its ancestors (and possibly
   anchored nodes).

   - This internal representation exists to allow the resolver to :
       perform path-based resolution. Presently (as of PyYAML 3.11), the
       paths used for resolution are narrowly enough defined that the
       limited structure works more or less exactly as well as the full
       structure. If they become advanced enough to, for example, query
       siblings (and if anyone actually uses that functionality), the
       limitations may need to be disabled.

-  ``flat`` (default ``False``): If set, the processor yields events
   directly rather than grouping them into documents. If it is clear,
   the processor instead yields one generator per document which itself
   yields the events for that document.
-  ``including_ends`` (default ``None``): If set, ``ElementStartEvent``
   and ``ElementEndEvent`` are included in the output. If clear, they
   are omitted. If ``None``, they are included if ``flat`` is set but
   omitted otherwise.

   - If ``including_ends`` is set and ``flat`` is clear, two additional
       : generators are yielded in addition to the generators for each
       document: before the first document's generator, a generator is
       produced that yields only the ``ElementStartEvent``, and after
       the last document's generator, a generator is produced that will
       yield only the ``ElementEndEvent``.

-  ``resolving_tags`` (default ``True``): If set, the resolver's rules
   are applied to rewrite the tags that appear in ``ScalarEvent``,
   ``SequenceStartEvent``, and ``MappingStartEvent``. If clear, the
   resolver is disabled and the tags already on the events are left
   alone.
-  ``single`` (default ``False``): If set, a stream is accepted if it
   contains at most one document; if the beginning of a second document
   is read then an error is raised. If clear, the method will accept an
   arbitrary number of documents.
-  ``with_extra_events`` (default ``True``): If set, several additional
   events defined in ``yaml_elaborate.events`` are inserted into the
   output to mark the starts and ends of sequence elements, mapping
   pairs, mapping pair keys, and mapping pair values. If clear, these
   events are not added.

   -  Each of these events indicates a zero-width event; each has a
      ``start_mark`` and an ``end_mark`` that are identical, set by the
      ``mark`` parameter of the constructor.
   -  The events are:

      -  ``yaml_elaborate.events.ElementStartEvent(index)``: Occurs
         immediately before the element value. ``index`` is 0-based from
         the start of the sequence as parsed.
      -  ``yaml_elaborate.events.ElementEndEvent(index)``: Occurs
         immediately after the element value. ``index`` is 0-based from
         the start of the sequence as parsed.
      -  ``yaml_elaborate.events.PairStartEvent()``: Occurs immediately
         before the pair's ``PairKeyStartEvent``.
      -  ``yaml_elaborate.events.PairEndEvent()``: Occurs immediately
         after the pair's ``PairValueEndEvent``.
      -  ``yaml_elaborate.events.PairKeyStartEvent()``: Occurs
         immediately before the pair's key value.
      -  ``yaml_elaborate.events.PairKeyEndEvent()``: Occurs immediately
         after the pair's key value.
      -  ``yaml_elaborate.events.PairValueStartEvent()``: Occurs
         immediately after the pair's ``PairKeyEndEvent`` and before the
         pair's value.
      -  ``yaml_elaborate.events.PairValueEndEvent()``: Occurs
         immediately after the pair's value.

License
-------

Written in 2015 by `David McFall <mailto:dvmcfall@gmail.com>`__

To the extent possible under law, the author(s) have dedicated all
copyright and related and neighboring rights to this software to the
public domain worldwide. This software is distributed without any
warranty.

You should have received a copy of the CC0 Public Domain Dedication
along with this software. If not, see
` <http://creativecommons.org/publicdomain/zero/1.0/>`__.
