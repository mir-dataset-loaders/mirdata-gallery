Guide
=====

`Home <index.html>`_ shows you how to find a dataset. This page helps with everything that comes after.

Get to know a dataset
---------------------

The panel describes one dataset, from top to bottom:

- **Overview:** what the dataset is, in a few sentences.
- **At a glance:** the number of tracks, sample rate, total duration, license and tasks. A "—" just means we don't know that value yet.
- **Annotation types:** click one to see only its charts, or ⌘/Ctrl-click to choose several. Click it again to bring everything back.
- **Statistics:** charts of the audio and annotations, explained in the next section. The **⤢** button opens them larger, and **×**, Esc or a click outside closes them.
- **BibTeX Citation:** open this to get the dataset's reference. If you use the data, please cite it. The people who made it will appreciate it.
- **Try it with mirdata:** code you can copy. It picks a random track and lists the annotations it offers, with the type of each beside it. You'll need to download the dataset first, and the `mirdata documentation <https://mirdata.readthedocs.io>`_ shows you how.

Read the charts
---------------

Each chart summarises the whole dataset rather than a single track. Hover over any bar, dot or cell for its exact numbers, or tap it on a touch screen.

Under each title, a small line says where the chart comes from. For example, ``beats · BeatData`` means ``track.beats``, which holds ``BeatData``.

Charts with text labels show the 10 most common, and the rest join an "(other)" bar. Hover over it to see what's inside. Long labels are shortened under the bar and written in full on hover.

You may also see a note above the charts:

- **"Computed from 80 of 100 tracks"** means some files weren't available, so the charts use the rest.
- **"No statistics yet"** or **"Nothing to plot yet"** means the charts for this dataset aren't ready yet.

Here's what each chart shows, grouped by annotation type:

Audio
~~~~~

- **Track duration:** how long the tracks are. Currently, we are only showing the duration of each tracks. Some datasets contains multiple audio files per tracks, but those are not aggregated. 
- **Sample rate:** how many tracks have each audio sample rate.

BeatData
~~~~~~~~

- **Tempo:** how fast the music is, in beats per minute, worked out from the beats. For each trck, we measure the gaps between neighboring beats, take the median gap, and calculate 60 ÷ gap. If the dataset also has ``TempoData``, you'll see that chart instead.
- **Tempo changes:** each dot is a track. Its median tempo runs along the bottom, and how much it changes from start to end runs up the side. Dots on the pale band stay within 5%, dots above it speed up and dots below it slow down. Hover over each area to count them. Darker areas are where dots pile up.
- **Meter:** how many beats each bar has. 3/4 and 3/8 both count as 3.
- **Meter changes:** how many times that number changes within a track, with 5 or more grouped together.

TempoData
~~~~~~~~~

- **Tempo:** how fast the music is, in beats per minute, from the dataset's own tempo annotations.

ChordData
~~~~~~~~~

- **Chords:** a circle of fifths, reading clockwise from C at the top. Each slice is a root note and each ring is a chord quality. Darker cells occur more often and blank cells not at all. Labels without a root, such as N for "no chord", sit in the middle.

KeyData
~~~~~~~

- **Keys:** the same circle of fifths, with one ring per key mode.

NoteData
~~~~~~~~

- **Note pitch:** which notes are played, in MIDI note numbers or Hz, depending on the dataset.

F0Data
~~~~~~

- **Pitch (F0):** how often each frequency appears, in Hz, leaving out moments with no pitch.

MultiF0Data
~~~~~~~~~~~

- **Pitches (multi-F0):** the same idea, for music where several pitches sound together.
- **Notes at once:** how many pitches sound at the same moment.

SectionData
~~~~~~~~~~~

- **Section labels:** what the parts of a piece are called, such as verse or chorus.
- **Section length:** how long those sections last.

LyricData
~~~~~~~~~

- **Lyric unit:** how the lyrics are aligned, such as by word or by line.
- **Lyrics per track:** how many lyrics each track has.

EventData
~~~~~~~~~

- **Events:** how often each event label appears.

Compare datasets
----------------

Want to see several datasets together? Switch on **Combine** above the list, or ⌘/Ctrl-click a dataset. The dataset you were looking at joins first, and then each click adds or removes one.

- **At a glance:** tracks and total duration add up, and sample rates and tasks are gathered together. If only some datasets know a value, you'll see "(2 of 3 datasets)" beside it. Licenses aren't combined, so please check each dataset's own.
- **Statistics:** charts of the same annotation type are merged, with one colour per dataset. The name chips above them work as the legend, and hovering shows each dataset's count. A line like ``2 of 3 · BeatData`` tells you how many datasets are in that chart.
- **Focus:** click a name to see only that dataset's part, and click it again to see them all. **×** removes a dataset. Clicking an annotation type and **⤢** work here too.
- **Choices:** if a dataset has several annotations of one type, as Billboard does for chords, **⇄ sources** lets you choose which one it adds. The others get their own charts.
- **Separate charts:** charts that can't be merged, such as ones in different units, stay separate, with the dataset's name on each.
- **Hidden datasets:** if a filter hides a dataset you chose, "Hidden by the filters" tells you, and it returns when you clear the filter.

Switch Combine off whenever you like to return to the last dataset you clicked. This clears your combination, so you'll start fresh next time.


That's the whole tour. Enjoy exploring the datasets!
