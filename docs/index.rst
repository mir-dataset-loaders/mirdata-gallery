About
=====

.. The front page. "About" names the browser tab; about.css hides it, the
   buttons below come first.

.. toctree::
   :hidden:

   gallery


Mirdata Gallery
----------------------
Welcome! The Mirdata Gallery helps you get to know a dataset before you download anything. There's nothing to install and no account to create, and nothing you click here changes any data, so please explore as much as you like.


.. raw:: html

   <div class="landing-buttons">
     <a class="landing-button" href="gallery.html">Browse the Gallery →</a>
     <a class="landing-button secondary" href="https://github.com/mir-dataset-loaders/mirdata">Mirdata GitHub</a>
   </div>


**Not sure where to start?** Click ``ChordData`` under Annotation types, choose and open any dataset you want. Then ⌘/Ctrl-click the next one to see the two together.

.. note::

   The Gallery doesn't support `Section`, `Event`, and `Tempo` annotations yet, or anything that comes from metadata, such as `instrument` and `genre`. We'll be adding them soon, so keep an eye out!

How to use the Gallery
----------------------

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


Get to know a dataset
~~~~~~~~~~~~~~~~~~~~~

The panel describes one dataset, from top to bottom:

- **Overview:** what the dataset is, in a few sentences.
- **At a glance:** the number of tracks, sample rate, total duration, license and tasks. A "—" just means we don't know that value yet.
- **Annotation types:** click one to see only its charts, or ⌘/Ctrl-click to choose several. Click it again to bring everything back.
- **Statistics:** charts of the audio and annotations, explained in the next section. The **⤢** button opens them larger, and **×**, Esc or a click outside closes them.
- **BibTeX Citation:** open this to get the dataset's reference. If you use the data, please cite it. The people who made it will appreciate it.
- **Try it with mirdata:** code you can copy. It picks a random track and lists the annotations it offers, with the type of each beside it. You'll need to download the dataset first, and the `mirdata documentation <https://mirdata.readthedocs.io>`_ shows you how.

Read the charts
~~~~~~~~~~~~~~~

Each chart summarises the whole dataset rather than a single track. Hover over any bar, dot or cell for its exact numbers, or tap it on a touch screen.

Under each title, a small line says where the chart comes from. For example, ``beats · BeatData`` means ``track.beats``, which holds ``BeatData``.

Charts with text labels show the 10 most common, and the rest join an "(other)" bar. Hover over it to see what's inside. Long labels are shortened under the bar and written in full on hover.

You may also see a note above the charts:

- **"Computed from 80 of 100 tracks"** means some files weren't available, so the charts use the rest.
- **"No statistics yet"** or **"Nothing to plot yet"** means the charts for this dataset aren't ready yet.

Here's what each chart shows, grouped by annotation type:

Audio
^^^^^

- **Track duration:** how long the tracks are. Each track counts once, even if a dataset has several audio files per track. Their lengths aren't added together.
- **Sample rate:** how many tracks have each audio sample rate.

BeatData
^^^^^^^^

- **Tempo:** how fast the music is, in beats per minute, worked out from the beats. For each track, we measure the gaps between neighboring beats, take the median gap, and calculate 60 ÷ gap. If the dataset also has ``TempoData``, you'll see that chart instead.
- **Tempo changes:** each dot is a track. Its median tempo runs along the bottom, and how much it changes from start to end runs up the side. Dots on the pale band stay within 5%, dots above it speed up and dots below it slow down. Hover over each area to count them. Darker areas are where dots pile up.
- **Meter:** how many beats each bar has. 3/4 and 3/8 both count as 3.
- **Meter changes:** how many times that number changes within a track, with 5 or more grouped together.

TempoData
^^^^^^^^^

- *※ TempoData is currently not supported*

ChordData
^^^^^^^^^

- **Chords:** a circle of fifths, reading clockwise from C at the top. Each slice is a root note and each ring is a chord quality. Darker cells occur more often and blank cells not at all. Labels without a root, such as N for "no chord", sit in the middle.

KeyData
^^^^^^^

- **Keys:** the same circle of fifths, with one ring per key mode.

NoteData
^^^^^^^^

- **Note pitch:** which notes are played, in MIDI note numbers or Hz, depending on the dataset.

F0Data
^^^^^^

- **Pitch (F0):** how often each frequency appears, in Hz, leaving out moments with no pitch.

MultiF0Data
^^^^^^^^^^^

- **Pitches (multi-F0):** the same idea, for music where several pitches sound together.
- **Notes at once:** how many pitches sound at the same moment.

SectionData
^^^^^^^^^^^
- *※ SectionData is currently not supported*

LyricData
^^^^^^^^^

- **Lyric unit:** how the lyrics are aligned, such as by word or by line.
- **Lyrics per track:** how many lyrics each track has.

EventData
^^^^^^^^^
- *※ EventData is currently not supported*

Compare datasets
~~~~~~~~~~~~~~~~

Want to see several datasets together? Switch on **Combine** above the list, or ⌘/Ctrl-click a dataset. The dataset you were looking at joins first, and then each click adds or removes one.

- **At a glance:** tracks and total duration add up, and sample rates and tasks are gathered together. If only some datasets know a value, you'll see "(2 of 3 datasets)" beside it. Licenses aren't combined, so please check each dataset's own.
- **Statistics:** charts of the same annotation type are merged, with one color per dataset. The name chips above them work as the legend, and hovering shows each dataset's count. A line like ``2 of 3 · BeatData`` tells you how many datasets are in that chart.
- **Focus:** click a name to see only that dataset's part, and click it again to see them all. **×** removes a dataset. Clicking an annotation type and **⤢** work here too.
- **Choices:** if a dataset has several annotations of one type, as Billboard does for chords, **⇄ sources** lets you choose which one it adds. The others get their own charts.
- **Separate charts:** charts that can't be merged, such as ones in different units, stay separate, with the dataset's name on each.
- **Hidden datasets:** if a filter hides a dataset you chose, "Hidden by the filters" tells you, and it returns when you clear the filter.

Switch Combine off whenever you like to return to the last dataset you clicked. This clears your combination, so you'll start fresh next time.


That's the whole tour. Enjoy exploring the datasets!

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

