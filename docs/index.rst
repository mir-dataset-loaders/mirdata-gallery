Home
====

.. The front page. "Home" names the browser tab; custom.css hides it, the hero
   below is the visible heading. The sections after the hero are placeholder
   text to replace.

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

What's in the Gallery
---------------------

One panel per dataset: an overview, the facts at a glance (tracks, sample
rate, duration, license), statistics of the audio and the annotations as
small charts, the citation, and the code to load it.

Using Mirdata
-------------

mirdata is a Python library that downloads, validates and loads music
datasets through one common interface.

.. code-block:: bash

   pip install mirdata

See the `mirdata documentation <https://mirdata.readthedocs.io>`_.

