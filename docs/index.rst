Home
====

.. The front page. "Home" names the browser tab; home.css hides it, the hero
   below is the visible heading.

.. toctree::
   :hidden:

   guide
   gallery

.. raw:: html

   <div class="landing-hero">
     <h1 class="landing-title">Mirdata Gallery</h1>
     <p>Every dataset mirdata can load, in one place: what it contains, how big it is, and how to start using it.</p>
     <div class="landing-buttons">
       <a class="landing-button" href="gallery.html">Browse the Gallery →</a>
       <a class="landing-button secondary" href="https://github.com/mir-dataset-loaders/mirdata">Mirdata GitHub</a>
     </div>
   </div>

How to use the Gallery
----------------------
Welcome! The Mirdata Gallery helps you get to know a dataset before you download anything. There's nothing to install and no account to create, and nothing you click here changes any data, so please explore as much as you like.

**Not sure where to start?** Click ``ChordData`` under Annotation types, choose and open any dataset you want. Then ⌘/Ctrl-click the next one to see the two together.

.. note::

   The Gallery doesn't support `Section`, `Event`, and `Tempo` annotations yet, or anything that comes from metadata, such as `instrument` and `genre`. We'll be adding them soon, so keep an eye out!

Find datasets
~~~~~~~~~~~~~

Start with whatever you already know. If you have a dataset in mind, type part of its name in the search box. The search also looks through annotation types and tasks, so "chord" works too.

If you're looking for a kind of data, the filters on the left can help. Click a filter to turn it on, and click it again to turn it off. **Show all** opens the rest.

- **Annotation types** tell you what annotation type is included in the dataset, such as ``BeatData`` for beats, ``ChordData`` for chords or ``NoteData`` for notes.
- **Tasks** tell you what the data is useful for, such as Beat Tracking or Chord Recognition.
- **Licenses** gives you a dataset with the selected licenses.

Each group has its own switch. **AND** keeps only the datasets with everything you picked, and **OR** keeps those with at least one. The default for Annotation types is AND; tasks and licenses is OR.

"Showing x of y" tells you how many are left. If you've narrowed things too far, **Clear filters** takes you back to the start.

Look through the list
~~~~~~~~~~~~~~~~~~~~~

Your matches appear in the list, with their annotation types, number of tracks and license.

The colored dots show what annotation types a dataset holds, with one dot per annotation type. The colors come in families: orange for rhythm, green for harmony, blue for pitch, indigo for structure, red for lyrics and yellow for events. Hover over the dots to see their names, or tap them on a touch screen.

- **Sort by** orders the list by name or by number of tracks.
- The two buttons beside it switch between list and icon views, and your browser remembers your choice.

Click any dataset to open it in the panel beside the list. If you'd like more room for either one, drag the bar between them, and double-click it to reset. On a small screen, the panel sits below the list instead.


Found a dataset? The `Guide <guide.html>`_ explains how to read it and its charts, and how to compare datasets.

Using Mirdata
-------------

.. container:: landing-quickstart

   .. container:: landing-quickstart-text

      mirdata is a Python library that downloads, validates and loads music
      datasets through one common interface.

      .. code-block:: bash

         pip install mirdata

      See the `mirdata documentation <https://mirdata.readthedocs.io>`_.

   .. container:: landing-quickstart-code

      .. code-block:: python

         import mirdata

         dataset = mirdata.initialize("rwc_popular")
         dataset.download()
         track = dataset.choice_track()
         track.beats

