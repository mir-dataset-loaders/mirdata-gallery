Home
====

.. The front page. "Home" names the browser tab; home.css hides it, the hero
   below is the visible heading.

.. toctree::
   :hidden:

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

.. raw:: html

   <div class="landing-steps">
     <div class="landing-step">
       <span class="landing-step-number">1</span>
       <h3>Find</h3>
       <p>Narrow the list down to the datasets you need.</p>
       <ul>
         <li>Search by name.</li>
         <li>Filter by annotation type (beats, chords, notes…), by task and by license.</li>
         <li><b>AND</b> needs every picked filter, <b>OR</b> any of them; <b>Clear filters</b> resets.</li>
       </ul>
     </div>
     <div class="landing-step">
       <span class="landing-step-number">2</span>
       <h3>Browse</h3>
       <p>See every match at once and pick one to look at.</p>
       <ul>
         <li>Sort by name or by number of tracks.</li>
         <li>Show a list or icons; the coloured dots are each dataset's annotation types.</li>
         <li>Click a dataset to open its panel.</li>
       </ul>
     </div>
     <div class="landing-step">
       <span class="landing-step-number">3</span>
       <h3>Read</h3>
       <p>Know what a dataset holds before you download it.</p>
       <ul>
         <li>Overview of dataset: tracks, sample rate, duration, license.</li>
         <li>Charts of the audio and annotations; hover a bar for its value.</li>
         <li>Click an annotation type to focus on its charts (⌘/Ctrl-click for several); <b>⤢</b> shows them larger.</li>
         <li>The BibTeX citation and the code to load it.</li>
       </ul>
     </div>
     <div class="landing-step">
       <span class="landing-step-number">4</span>
       <h3>Compare</h3>
       <p>Put several datasets together in one panel.</p>
       <ul>
         <li>Switch on <b>Combine</b> (or ⌘/Ctrl-click), then click datasets.</li>
         <li>Their facts add up; their charts stack, one colour per dataset.</li>
         <li>Click a name to focus on that dataset; <b>×</b> removes it.</li>
       </ul>
     </div>
   </div>

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

