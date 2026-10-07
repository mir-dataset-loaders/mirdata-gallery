mirdata Dataset Gallery
=======================

Explore all supported datasets in ``mirdata``.



acousticbrainz_genre
--------------------


* **Annotations:** ``Genre``


**About this dataset:**
   
The AcousticBrainz Genre dataset includes genre and subgenre annotations from AllMusic, Discogs, Last.fm, and Tagtraum, along with music features, aimed at evaluating hierarchical multi-label genre classification systems.

* **License:** This dataset is composed of 4 subdatasets. Three of them are Creative Commons Attribution Non Commercial Share Alike 4.0 International and the other one is non-comercial. Details about which license correspond to each subdataset can be found in the following websites: * https://zenodo.org/record/2553414#.X_nxnOn7RUI * https://zenodo.org/record/2554044#.X_nw2en7RUI
* **Downloadable Remotes:** ``validation-01``, ``validation-89``, ``train-01``, ``train-23``, ``train-45``, ``train-67``, ``train-89``, ``train-ab``, ``train-cd``, ``train-ef``
* **YAML File:** :download:`acousticbrainz_genre.yaml<../cards/acousticbrainz_genre.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{bogdanov2019acousticbrainz,
        title={The AcousticBrainz genre dataset: Multi-source, multi-level, multi-label, and large-scale},
        author={Bogdanov, Dmitry and Porter, Alastair and Schreiber, Hendrik and Urbano, Juli{'a}n and Oramas, Sergio},
        booktitle={Proceedings of the 20th Conference of the International Society for Music Information Retrieval (ISMIR 2019): 2019 Nov 4-8; Delft, The Netherlands.[Canada]: ISMIR; 2019.},
        year={2019},
        organization={International Society for Music Information Retrieval (ISMIR)}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/acousticbrainz_genre.yaml
      :language: yaml

baf
---


* **Annotations:** ``EventDataExtended``


**About this dataset:**
   
The BAF dataset includes 2,000 reference tracks and 57 hours of TV broadcast queries for music monitoring, annotated for foreground and background track detection; the primary MIR task is audio fingerprinting.

* **License:** Given the different ownership of the elements of the dataset, the dataset is licensed under the following conditions: * User's access request * Research only, non-commercial purposes * No adaptations nor derivative works * Attribution to Epidemic Sound and the authors as it is indicated in the ”citation” section.
* **Downloadable Remotes:** *No direct download available*
* **YAML File:** :download:`baf.yaml<../cards/baf.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   BAF dataset is only available upon request. To download the audio request access in this link: https://doi.org/10.5281/zenodo.6868083. Then unzip the audio into the baf general dataset folder for the rest of annotations and files. Please include, in the justification field, your academic affiliation (if you have one) and a brief description of your research topics and why you would like to use this dataset.

   ::

       baf/
       ├── baf_datasheet.pdf
       ├── annotations.csv
       ├── changelog.md
       ├── cross_annotations.csv
       ├── queries_info.csv
       ├── queries
       │   ├── query_0001.wav
       │   ├── query_0002.wav
       │   ├── …
       │   └── query_3425.wav
       ├── queries_info.csv
       └── references
           ├── ref_0001.wav
           ├── ref_0002.wav
           ├── …
           └── ref_2000.wav

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{cortes2022BAF,
        author       = {Guillem Cortès and
                        Alex Ciurana and
                        Emilio Molina and
                        Marius Miron and
                        Owen Meyers and
                        Joren Six and
                        Xavier Serra},
        title        = {BAF: An audio fingerprinting dataset for broadcast monitoring},
        booktitle    = {Proceedings of the 23rd International Society for Music Information Retrieval Conference},
        year         = 2022,
        pages        = {908-916},
        publisher    = {ISMIR},
        address      = {Bengaluru, India},
        month        = dec,
        venue        = {Bengaluru, India},
        doi          = {10.5281/zenodo.7316812},
        url          = {https://doi.org/10.5281/zenodo.7372162}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/baf.yaml
      :language: yaml

ballroom
--------


* **Annotations:** ``BeatData``, ``TempoData``


**About this dataset:**
   
The Ballroom Rhythm Dataset includes beat and bar annotations for various ballroom dance styles, designed for tasks like beat tracking and rhythm analysis. Annotations are provided in `.beats` files, and the dataset supports research in tempo estimation and rhythm analysis for ballroom music.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``audio``, ``tempo``, ``beats``
* **YAML File:** :download:`ballroom.yaml<../cards/ballroom.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @ARTICLE{1678001,
          author={Gouyon, F. and Klapuri, A. and Dixon, S. and Alonso, M. and Tzanetakis, G. and Uhle, C. and Cano, P.},
          journal={IEEE Transactions on Audio, Speech, and Language Processing}, 
          title={An experimental comparison of audio tempo induction algorithms}, 
          year={2006},
          volume={14},
          number={5},
          pages={1832-1844},
          doi={10.1109/TSA.2005.858509}}

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/ballroom.yaml
      :language: yaml

beatles
-------


* **Annotations:** ``BeatData``, ``SectionData``, ``KeyData``, ``ChordData``


**About this dataset:**
   
The Beatles Dataset provides annotations for 179 songs including beat and metric positions, chords, key, and segmentation, enabling tasks like music segmentation and chord recognition.

* **License:** Unfortunately we couldn't find the license information for the Beatles dataset.
* **Downloadable Remotes:** ``annotations``
* **YAML File:** :download:`beatles.yaml<../cards/beatles.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the audio files of the Beatles dataset are not available

   ::

       for download. If you have the Beatles dataset, place the contents into
       a folder called Beatles with the following structure:
           > Beatles/
               > annotations/
               > audio/
       and copy the Beatles folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{mauch2009beatles,
          title={OMRAS2 metadata project 2009},
          author={Mauch, Matthias and Cannam, Chris and Davies, Matthew and Dixon, Simon and Harte,
          Christopher and Kolozali, Sefki and Tidhar, Dan and Sandler, Mark},
          booktitle={12th International Society for Music Information Retrieval Conference},
          year={2009},
          series = {ISMIR}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/beatles.yaml
      :language: yaml

beatport_key
------------


* **Annotations:** ``TempoData``, ``KeyData``


**About this dataset:**
   
The beatport_key dataset includes 1486 two-minute EDM audio excerpts annotated with key labels, comments, and confidence levels, primarily for evaluating key estimation algorithms in electronic dance music.

* **License:** Creative Commons Attribution Share Alike 4.0 International.
* **Downloadable Remotes:** ``keys``, ``metadata``, ``audio``
* **YAML File:** :download:`beatport_key.yaml<../cards/beatport_key.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @phdthesis {3897,
          title = {Tonality Estimation in Electronic Dance Music: A Computational and Musically Informed Examination},
          year = {2018},
          month = {03/2018},
          pages = {234},
          school = {Universitat Pompeu Fabra},
          address = {Barcelona},
          abstract = {This dissertation revolves around the task of computational key estimation in electronic dance music, upon which three interrelated operations are performed. First, I attempt to detect possible misconceptions within the task, which is typically accomplished with a tonal vocabulary overly centred in Western classical tonality, reduced to a binary major/minor model which might not accomodate popular music styles. Second, I present a study of tonal practises in electronic dance music, developed hand in hand with the curation of a corpus of over 2,000 audio excerpts, including various subgenres and degrees of complexity. Based on this corpus, I propose the creation of more open-ended key labels, accounting for other modal practises and ambivalent tonal configurations. Last, I describe my own key finding methods, adapting existing models to the musical idiosyncrasies and tonal distributions of electronic dance music, with new statistical key profiles derived from the newly created corpus.},
          keywords = {EDM, Electronic Dance Music, Key Estimation, mir, music information retrieval, tonality},
          url = {https://doi.org/10.5281/zenodo.1154586},
          author = {{'A}ngel Faraldo}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/beatport_key.yaml
      :language: yaml

billboard
---------


* **Annotations:** ``SectionData``, ``ChordData``


**About this dataset:**
   
The McGill Billboard dataset contains audio features and annotations for 890 Billboard chart slots, including chord progressions, artist names, and chart dates, primarily for chord analysis tasks.

* **License:** This data is released under a Creative Commons 0 license, effectively dedicating it to the public domain. More information about this dedication and your rights, please see the details here: http://creativecommons.org/publicdomain/zero/1.0/ and http://creativecommons.org/publicdomain/zero/1.0/legalcode.
* **Downloadable Remotes:** ``metadata``, ``annotation_salami``, ``annotation_lab``, ``annotation_mirex13``, ``annotation_chordino``
* **YAML File:** :download:`billboard.yaml<../cards/billboard.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{burgoyne_billboard,
      author = {Burgoyne, John Ashley and Wild, Jonathan and Fujinaga, Ichiro},
      year = {2011},
      title = {An {Expert} {Ground} {Truth} {Set} for {Audio} {Chord} {Recognition} and {Music} {Analysis}},
      booktitle={Proceedings of the 12th International Society for Music Information Retrieval Conference, ISMIR}
      }

      @phdthesis{phdthesis,
        author       = {Burgoyne, John Ashley}, 
        title        = {Stochastic {Processes} and {Database}-{Driven} {Musicology}},
        school       = {McGill University, Montréal, Québec},
        year         = 2012,
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/billboard.yaml
      :language: yaml

brid
----


* **Annotations:** ``BeatData``, ``TempoData``


**About this dataset:**
   
The BRID dataset includes 367 solo and multiple-instrument recordings of 10 Brazilian instruments across 5 rhythm classes, providing annotations for beat tracking and rhythmic pattern recognition. Primary tasks involve analyzing and understanding Brazilian musical rhythms.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``annotations``, ``audio``
* **YAML File:** :download:`brid.yaml<../cards/brid.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{Maia2018AND,
        title={A Novel Dataset of Brazilian Rhythmic Instruments and Some Experiments in Computational Rhythm Analysis},
        author={Lucas Maia and Pedro D. de Tomaz J{'u}nior and Magdalena Fuentes and Mart{'i}n Rocamora and Luiz W. P. Biscainho and Maur{'i}cio V. M. Costa and Sara Cohen},
        year={2018},
        url={https://api.semanticscholar.org/CorpusID:204762166}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/brid.yaml
      :language: yaml

candombe
--------


* **Annotations:** ``BeatData``


**About this dataset:**
   
The Candombe dataset includes over 2 hours of stereo audio from 35 performances, with annotations for beats and downbeats by expert, focusing on identifying rhythmic structures in traditional Candombe music.

* **License:** Creative Commons Attribution 4.0 International
* **Downloadable Remotes:** ``annotations``, ``audio``
* **YAML File:** :download:`candombe.yaml<../cards/candombe.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{Nunes2015,
          author = {Leonardo Nunes and Martín Rocamora and Luis Jure and Luiz W. P. Biscainho},
          title = {{Beat and Downbeat Tracking Based on Rhythmic Patterns Applied to the Uruguayan Candombe Drumming}},
          booktitle = {Proceedings of the 16th International Society for Music Information Retrieval Conference (ISMIR 2015)},
          month = {Oct.},
          address = {Málaga, Spain},
          pages = {264--270},
          year = {2015}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/candombe.yaml
      :language: yaml

cante100
--------


* **Annotations:** ``F0Data``, ``NoteData``


**About this dataset:**
   
cante100 includes 100 tracks with annotations on vocal sections, F0, and automatic note transcription; it supports tasks like style classification and vocal detection.

* **License:** The provided datasets are offered free of charge for internal non-commercial use. We do not grant any rights for redistribution or modification. All data collections were gathered by the COFLA team. COFLA 2015. All rights reserved.
* **Downloadable Remotes:** ``spectrogram``, ``melody``, ``notes``, ``metadata``, ``README``
* **YAML File:** :download:`cante100.yaml<../cards/cante100.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   This loader is designed to load the spectrum, as it is available for download.

   ::

           However, the loader supports audio as well. Unfortunately the audio files of the
           cante100 dataset are not available for free download, but upon request. However,
           you can request de audio in both links here:
           ==> http://www.cofla-project.com/?page_id=208
           ==> https://zenodo.org/record/1324183
           Then, locate the downloaded the cante100audio folder like this:
               > cante100/
                   > cante100_spectrum/
                   ... (rest of the annotation folders)
                   > cante100audio/
           Remember to locate the cante100 folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @dataset{nadine_kroher_2018_1322542,
        author       = {Nadine Kroher and
                        José Miguel Díaz-Báñez and
                        Joaquin Mora and
                        Emilia Gómez},
        title        = {cante100 Metadata},
        month        = jul,
        year         = 2018,
        publisher    = {Zenodo},
        version      = {1.0},
        doi          = {10.5281/zenodo.1322542},
        url          = {https://doi.org/10.5281/zenodo.1322542}
      },
      @dataset{nadine_kroher_2018_1324183,
        author       = {Nadine Kroher and
                        José Miguel Díaz-Báñez and
                        Joaquin Mora and
                        Emilia Gómez},
        title        = {cante100 Audio},
        month        = jul,
        year         = 2018,
        publisher    = {Zenodo},
        version      = {1.0},
        doi          = {10.5281/zenodo.1324183},
        url          = {https://doi.org/10.5281/zenodo.1324183}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/cante100.yaml
      :language: yaml

compmusic_carnatic_rhythm
-------------------------


* **Annotations:** ``BeatData``, ``Instrument``


**About this dataset:**
   
This dataset includes audio excerpts from Carnatic music, annotated with time-aligned markers indicating metrical positions in the taala cycle, and provides metadata such as taala type, offset, and cycle length. The primary MIR task is taala and beat tracking.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** *No direct download available*
* **YAML File:** :download:`compmusic_carnatic_rhythm.yaml<../cards/compmusic_carnatic_rhythm.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   The files of this dataset are shared under request. Please go to: https://zenodo.org/record/1264394 and request access, stating
       the research-related use you will give to the dataset. Once the access is granted (it may take, at most, one day or two), please download 
       the dataset with the provided Zenodo link and uncompress the two zip files: CMR_full_dataset_1.0.zip and CMR_subset_1.0.zip. You don't need 
       to re-arrange or change the folder structure of these two versions, the dataloader is designed to work with the provided file organization. 
       Therefore, simply uncompress and store the datasets to a desired location, and use such location to initialize the dataset as follows: 
    
       compmusic_carnatic_rhythm = mirdata.initialize("compmusic_carnatic_rhythm", data_home="/path/to/home/folder/of/dataset").

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{srinivasamurthy_2014,
        title={Particle Filters for Efficient Meter Tracking with Dynamic Bayesian Networks},
        author={Srinivasamurthy, A. and Holzapfel, A. and Cemgil, A. T. and Serra, X.},
        journal={In Proceedings of the 16th International Society for Music Information Retrieval Conference (ISMIR)},
        pages={197--203}
        year={2015}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/compmusic_carnatic_rhythm.yaml
      :language: yaml

compmusic_carnatic_varnam
-------------------------


* **Annotations:** ``SectionData``, ``KeyData``


**About this dataset:**
   
The dataset includes 28 solo Carnatic varnam recordings featuring 7 rāgas, with taala cycle annotations and machine-readable notations. It supports intonation analysis and audio-score alignment.

* **License:** Creative Commons Attribution Non Commercial No Derivatives 4.0 International
* **Downloadable Remotes:** ``all``
* **YAML File:** :download:`compmusic_carnatic_varnam.yaml<../cards/compmusic_carnatic_varnam.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @dataset{koduri_g_k_2014_1257118,
        author       = {Koduri, G. K. and
                        Ishwar, V. and
                        Serrà, J. and
                        Serra, X.},
        title        = {Carnatic Varnam Dataset},
        month        = feb,
        year         = 2014,
        publisher    = {Zenodo},
        version      = {1.0},
        doi          = {10.5281/zenodo.1257118},
        url          = {https://doi.org/10.5281/zenodo.1257118}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/compmusic_carnatic_varnam.yaml
      :language: yaml

compmusic_hindustani_rhythm
---------------------------


* **Annotations:** ``BeatData``, ``Instrument``


**About this dataset:**
   
This dataset includes two-minute stereo mp3 audio excerpts from Hindustani music, annotated with time-aligned markers indicating taal cycles, sam, and matras, along with metadata on tempo, artist, and raag. The primary MIR task is taal and beat tracking.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** *No direct download available*
* **YAML File:** :download:`compmusic_hindustani_rhythm.yaml<../cards/compmusic_hindustani_rhythm.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   The files of this dataset are shared under request. Please go to: https://zenodo.org/record/1264742 and request access, stating
       the research-related use you will give to the dataset. Once the access is granted (it may take, at most, one day or two), please download 
       the dataset with the provided Zenodo link and uncompress and store the datasets to a desired location, and use such location to initialize the 
       dataset as follows: compmusic_hindustani_rhythm = mirdata.initialize("compmusic_hindustani_rhythm", data_home="/path/to/home/folder/of/dataset").

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{Srinivasamurthy2016,
          author = {Srinivasamurthy, Ajay and Holzapfel, Andre and Cemgil, Ali and Serra, Xavier},
          year = {2016},
          month = {03},
          pages = {76-80},
          title = {A generalized Bayesian model for tracking long metrical cycles in acoustic music signals},
          doi = {10.1109/ICASSP.2016.7471640}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/compmusic_hindustani_rhythm.yaml
      :language: yaml

compmusic_iamms
---------------


* **Annotations:** ``F0Data``, ``SectionData``, ``KeyData``


**About this dataset:**
   
This dataset includes audio excerpts from Carnatic and Hindustani music with annotations for melodic sections, nyas events, and pitch/tonic features, aimed at developing methods for computing melodic similarity in Indian art music.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``all``
* **YAML File:** :download:`compmusic_iamms.yaml<../cards/compmusic_iamms.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{gulati2015improving,
        author    = {Sankalp Gulati and Joan Serr{\`a} and Xavier Serra},
        title     = {Improving melodic similarity in Indian art music using culture-specific melodic characteristics},
        booktitle = {Proceedings of the 16th International Society for Music Information Retrieval Conference (ISMIR)},
        pages     = {680--686},
        year      = {2015},
        address   = {Malaga, Spain}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/compmusic_iamms.yaml
      :language: yaml

compmusic_indian_tonic
----------------------


* **Annotations:** ``KeyData``


**About this dataset:**
   
This dataset includes audio excerpts of Indian Art Music, with annotations of tonic pitch and metadata for tonic identification, primarily for Carnatic and Hindustani music.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``remote_data``
* **YAML File:** :download:`compmusic_indian_tonic.yaml<../cards/compmusic_indian_tonic.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   The audio of this dataset is private, and it is only shared for research purposes. Please refer to:
       https://zenodo.org/record/7342372, request the audios clearly explaning why and how are you planning 
       to use it, and then simply move the "audio" folders to the respective center ID. An example here:
       take indian_art_music_tonic_1.0_audio/CM/audio and move it inside indian_art_music_tonic_1.0/CM, and so on.

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{Gulati2014,
          author = {Gulati, S. and Bellur, A. and Salamon, J. and Ranjani, H. G. and Ishwar, V. and Murthy, H. A. and Serra, X.},
          journal = {Journal of New Music Research},
          pages = {55--73},
          volume = {43},
          number = {01},
          title = {{Automatic Tonic Identification in Indian Art Music: Approaches and Evaluation}},
          year = {2014}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/compmusic_indian_tonic.yaml
      :language: yaml

compmusic_jingju_acappella
--------------------------


* **Annotations:** ``LyricData``


**About this dataset:**
   
This dataset includes a cappella Jingju singing recordings with annotations for phrases, syllables, and phonemes in both pinyin and X-SAMPA, aimed at tasks like boundary detection and alignment.

* **License:** audio files ending with upf or lon: Creative Commons Attribution Non-Commercial 4.0 International, audio files ending with qm: http://isophonics.org/SingingVoiceDataset
* **Downloadable Remotes:** ``annotation_txt``, ``catalogue_dan``, ``catalogue_laosheng``, ``wav``
* **YAML File:** :download:`compmusic_jingju_acappella.yaml<../cards/compmusic_jingju_acappella.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @dataset{rong_gong_2018_1323561,
        author       = {Rong Gong and
                        Rafael Caro Repetto and
                        Yile Yang and
                        Xavier Serra},
        title        = {Jingju a cappella singing dataset part1},
        month        = jul,
        year         = 2018,
        publisher    = {Zenodo},
        version      = 7,
        doi          = {10.5281/zenodo.1323561},
        url          = {https://doi.org/10.5281/zenodo.1323561}
      }
      @article{black2014automatic,
        title={Automatic identification of emotional cues in Chinese opera singing},
        author={Black, Dawn AA and Li, Ma and Tian, Mi},
        journal={ICMPC, Seoul, South Korea},
        year={2014}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/compmusic_jingju_acappella.yaml
      :language: yaml

compmusic_otmm_makam
--------------------


* **Annotations:** ``F0Data``, ``KeyData``


**About this dataset:**
   
This dataset includes 200 recordings from 20 common makams, each with a unique MBID, for makam recognition, featuring annotations on makam and tonic in JSON format, and provides pitch tracks of the predominant melodies for copyright reasons.

* **License:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License
* **Downloadable Remotes:** ``all``
* **YAML File:** :download:`compmusic_otmm_makam.yaml<../cards/compmusic_otmm_makam.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @software{sertan_senturk_2016_58413,
        author       = {Sertan Şentürk and
                        Altuğ Karakurt},
        title        = {{otmm_makam_recognition_dataset: Ottoman-Turkish
                         Makam Music Makam Recognition Dataset}},
        month        = jul,
        year         = 2016,
        publisher    = {Zenodo},
        version      = {dlfm2016},
        doi          = {10.5281/zenodo.58413},
        url          = {https://doi.org/10.5281/zenodo.58413}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/compmusic_otmm_makam.yaml
      :language: yaml

compmusic_raga
--------------


* **Annotations:** ``F0Data``, ``SectionData``, ``KeyData``


**About this dataset:**
   
The compmusic_raga dataset includes full-length audio recordings of Carnatic and Hindustani music with associated rāga labels, providing tonal features and segmentations for rāga recognition tasks.

* **License:** Creative Commons Attribution 4.0 International
* **Downloadable Remotes:** ``features``
* **YAML File:** :download:`compmusic_raga.yaml<../cards/compmusic_raga.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   While annotations and metadata are freely downloadable, the audio of this 
       dataset has restricted access. Please access: https://zenodo.org/record/7278511 and request 
       access to the audio, specifying your purpose. The audio will be shared for research purposes. 
       In such case, when access to the audio is granted, please organize the dataset as specified 
       in the ``directory_structure.txt`` file found when you download the features and metadata using
       the .download() method of this dataloader.

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{gulati_2016,
        author       = {Gulati, Sankalp and Serrà, Joan and Kaustuv Kani, Ganguli 
                          and Sentürk, Sertan and Serra, Xavier},
        title        = {{Time-delayed melody surfaces for raga recognition}},
        year         = 2016,
        pages        = 751--757,
        journal      = {In Proceedings of the 17th International Society for Music Information 
                          Retrieval Conference (ISMIR), New York, USA},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/compmusic_raga.yaml
      :language: yaml

cuidado
-------


* **Annotations:** ``BeatData``, ``TempoData``


**About this dataset:**
   
The Cuidado Rhythm Dataset includes beat and bar annotations for various ballroom dance styles like Waltz, Tango, and Samba, designed for tasks such as beat tracking and rhythm analysis in cuidado dance music. Annotations are provided in `.beats` files, reflecting the characteristic rhythms of each dance style.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** *No direct download available*
* **YAML File:** :download:`cuidado.yaml<../cards/cuidado.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the Cuidado dataset is not available for download.

   ::

       If you have the Cuidado dataset, place the contents into a folder called
       cuidado with the following structure:
           > C_1.0/
               > audio/
               > annotations/beats
               > annotations/tempo
       and copy the cuidado folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{1678001,
          author={Gouyon, F. and Klapuri, A. and Dixon, S. and Alonso, M. and Tzanetakis, G. and Uhle, C. and Cano, P.},
          journal={IEEE Transactions on Audio, Speech, and Language Processing}, 
          title={An experimental comparison of audio tempo induction algorithms}, 
          year={2006},
          volume={14},
          number={5},
          pages={1832-1844},
          doi={10.1109/TSA.2005.858509}}

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/cuidado.yaml
      :language: yaml

da_tacos
--------


* **Annotations:** ``Instrument``, ``KeyData``


**About this dataset:**
   
Da-TACOS includes 25,000 pre-extracted features and metadata for cover songs, focusing on cover song identification, with annotations like performance and work titles, artists, release years, and genres. Primary task is cover song identification.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International
* **Downloadable Remotes:** ``metadata``, ``benchmark_cens``, ``benchmark_crema``, ``benchmark_hpcp``, ``benchmark_key``, ``benchmark_madmom``, ``benchmark_mfcc``, ``coveranalysis_tags``, ``coveranalysis_cens``, ``coveranalysis_crema``, ``coveranalysis_hpcp``, ``coveranalysis_key``, ``coveranalysis_madmom``, ``coveranalysis_mfcc``
* **YAML File:** :download:`da_tacos.yaml<../cards/da_tacos.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{yesiler2019,
          author = "Furkan Yesiler and Chris Tralie and Albin Correya and Diego F. Silva and Philip Tovstogan and Emilia G{'{o}}mez and Xavier Serra",
          title = "{Da-TACOS}: A Dataset for Cover Song Identification and Understanding",
          booktitle = "Proc. of the 20th Int. Soc. for Music Information Retrieval Conf. (ISMIR)",
          year = "2019",
          pages = "327--334",
          address = "Delft, The Netherlands"
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/da_tacos.yaml
      :language: yaml

dagstuhl_choirset
-----------------


* **Annotations:** ``F0Data``, ``NoteData``


**About this dataset:**
   
Dagstuhl ChoirSet includes multitrack a cappella choral recordings with close-up (larynx, dynamic, headset) and room microphone tracks, along with piano accompaniment. Annotations provide individual singer tracks for MIR tasks such as source separation and pitch estimation.

* **License:** Creative Commons Attribution 4.0 International
* **Downloadable Remotes:** ``full_dataset``
* **YAML File:** :download:`dagstuhl_choirset.yaml<../cards/dagstuhl_choirset.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{RosenzweigCWSGM20_DCS_TISMIR,
          author    = {Sebastian Rosenzweig and Helena Cuesta and Christof Wei{\ss} and Frank Scherbaum and Emilia G{'o}mez and Meinard M{"u}ller},
          title     = {{D}agstuhl {ChoirSet}: {A} Multitrack Dataset for {MIR} Research on Choral Singing},
          journal   = {Transactions of the International Society for Music Information Retrieval ({TISMIR})},
          volume    = {3},
          number    = {1},
          year      = {2020},
          pages     = {98--110},
          publisher = {Ubiquity Press},
          doi       = {10.5334/tismir.48},
          url       = {http://doi.org/10.5334/tismir.48},
          url-demo  = {https://www.audiolabs-erlangen.de/resources/MIR/2020-DagstuhlChoirSet}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/dagstuhl_choirset.yaml
      :language: yaml

dali
----


* **Annotations:** ``NoteData``


**About this dataset:**
   
DALI includes 5358 audio files with time-aligned vocal melodies, lyrics at four granularities, and metadata like genre and language, for analyzing melody and lyrics in songs.

* **License:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
* **Downloadable Remotes:** ``metadata``
* **YAML File:** :download:`dali.yaml<../cards/dali.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   To download this dataset, visit:

   ::

       https://zenodo.org/record/2577915 and request access.
       Once downloaded, unzip the file DALI_v1.0.zip
       and place the result in:
       {}

       Use the function dali_code.get_audio you can find at:
       https://github.com/gabolsgabs/DALI for getting the audio
       and place them in "audio" folder with the following structure:
       > Dali
           > audio
           ...

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{Meseguer-Brocal_2018,
          Title = {DALI: a large Dataset of synchronized Audio, LyrIcs and notes, automatically created using teacher-student
           machine learning paradigm.},
          Author = {Meseguer-Brocal, Gabriel and Cohen-Hadria, Alice and Peeters, Geoffroy},
          Booktitle = {19th International Society for Music Information Retrieval Conference},
          Editor = {ISMIR}, Month = {September},
          Year = {2018}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/dali.yaml
      :language: yaml

egfxset
-------


* **Annotations:** ``NoteData``


**About this dataset:**
   
EGFxSet includes 8,970 5-second audio recordings of electric guitar tones processed through 12 real guitar effects, covering 138 notes across 5 pickup configurations. Annotations provide detailed effect settings and guitar parameters. The primary MIR task involves analyzing and classifying these audio samples based on their tonal and effect characteristics.

* **License:** Creative Commons Attribution 4.0 International
* **Downloadable Remotes:** ``bluesDriver``, ``chorus``, ``clean``, ``digitalDelay``, ``flanger``, ``hallReverb``, ``phaser``, ``plateReverb``, ``rat``, ``spring-Reverb``, ``sweepEcho``, ``tapeEcho``, ``tubeScreamer``, ``metadata``
* **YAML File:** :download:`egfxset.yaml<../cards/egfxset.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @techreport{pedroza2022egfxset,
            title={EGFxSet: Electric guitar tones processed through real effects of distortion, modulation, delay and reverb},
            author={Pedroza, Hegel and Meza, Gerardo and Roman, Iran},
            year={2022},
            institution={UNAM},
            booktitle={Extended Abstracts for the Late-Breaking Demo Session of the 23rd Int. Society for Music Information Retrieval Conf., Bengaluru, India, 2022.},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/egfxset.yaml
      :language: yaml

filosax
-------


* **Annotations:** ``NoteData``


**About this dataset:**
   
The Filosax dataset includes 48 multitrack jazz recordings with 8 audio stems and annotations for beats, chords, and sections. Note annotations are provided for each saxophone solo, supporting tasks like transcription and segmentation.

* **License:** The Filosax dataset contains copyright material and is shared with researchers under the following conditions: 1. Filosax may only be used by the individual signing below and by members of the research group or organisation of this individual. This permission is not transferable. 2. Filosax may be used only for non-commercial research purposes. 3. Filosax (or data enabling the its reproduction) may not be sold, leased, published or distributed to any third party without written permission from the Filosax administrator. 4. When research results obtained using Filosax are publicly released (in the form of reports, publications, or derivative software), clear indication of the use of Filosax shall be given, usually in the form of a citation of the following paper: D. Foster and S. Dixon (2021), Filosax: A Dataset of Annotated Jazz Saxophone Recordings. 22nd International Society for Music Information Retrieval Conference (ISMIR). 5. Queen Mary University of London shall not be held liable for any errors in the content of Filosax nor damage arising from the use of Filosax. 6. The Filosax administrator may update these conditions of use at any time.
* **Downloadable Remotes:** *No direct download available*
* **YAML File:** :download:`filosax.yaml<../cards/filosax.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   To download the dataset, first go to the Zenodo pages below to request access:

   (Full - 14.5GB)
   https://zenodo.org/record/5643843#.YYL7aS2l3UI

   (Lite - 558MB)
   https://zenodo.org/record/5643734#.YYLQ-i2l3UI

   Unzip the downloaded file to the folder /Users/<username>/mir_datasets/ (or wherever data_home has been assigned on initialization), and remove the version number from the folder:

   (Full)
   /Users/<username>/mir_datasets/Filosax

   (Lite)
   /Users/<username>/mir_datasets/Filosax_Lite

   This data is sufficient to use the dataset in the "_sax" (sax only) mode. To download the backing data, go to the Aebersold sites:

   (Full)
   https://www.jazzbooks.com/mm5/merchant.mvc?&Screen=WISH&Store_Code=JAJAZZ&WishList_ID=1679

   (Lite)
   https://www.jazzbooks.com/mm5/merchant.mvc?&Screen=WISH&Store_Code=JAJAZZ&WishList_ID=1678

   Put the files downloaded into the "/Aebersold" folder, and then run the appropriate script from inside the home folder:

   (Full)
   python Scripts/Compile_Backing.py -version full

   (Lite)
   python Scripts/Compile_Backing.py -version lite

   which populates the "/Backing" folder with edited files, which match the versions that were used in the recordings.

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{
        foster_filosax_2021,
        title={Filosax: A Dataset of Annotated Jazz Saxophone Recordings},
        author={Foster, Dave and Dixon, Simon},
        booktitle={International Society for Music Information Retrieval (ISMIR) Conference},
        year={2021}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/filosax.yaml
      :language: yaml

fma_keys
--------


* **Annotations:** ``KeyData``


**About this dataset:**
   
FMA Keys includes 5489 songs across 17 genres, providing song-level key and mode annotations; the primary task is key detection. Annotations cover FMA track IDs, Spotify URIs, and key/mode in both string and numerical formats.

* **License:** Creative Commons Attribution 4.0 International
* **Downloadable Remotes:** ``metadata``, ``tracks-000-019``, ``tracks-020-039``, ``tracks-040-049``, ``tracks-050-059``, ``tracks-060-069``, ``tracks-070-079``, ``tracks-080-089``, ``tracks-090-099``, ``tracks-100-109``, ``tracks-110-124``
* **YAML File:** :download:`fma_keys.yaml<../cards/fma_keys.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{
              wong_fma_keys,
              title = {FMAK: A Dataset of Key and Mode Annotations for the Free Music Archive},
              author = {Wong, Stella and Hernandez, Gandalf},
              booktitle = {24th International Society for Music Information Retrieval Conference (ISMIR)},
              year = {2023}
          }
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/fma_keys.yaml
      :language: yaml

four_way_tabla
--------------


* **Annotations:** ``BeatData``


**About this dataset:**
   
The Four-Way Tabla Dataset includes 236 audio samples of tabla solo with onset annotations for four stroke types, suitable for tasks like onset detection and stroke classification. Annotations are provided per stroke type in separate folders, and the dataset is split into training and testing subsets.

* **License:** Creative Commons Attribution 4.0 International License.
* **Downloadable Remotes:** ``remote_data``
* **YAML File:** :download:`four_way_tabla.yaml<../cards/four_way_tabla.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{RohitMA2021,
          author = {M.A, Rohit and Bhattacharjee, Amitrajit and Rao, Preeti},
          journal = {Proc. of the 22nd Int. Society for Music Information Retrieval Conf., Online, 2021},
          title = {{Four-way Classification of Tabla Strokes with Models Adapted from Automatic Drum Transcription}},
          year = {2021}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/four_way_tabla.yaml
      :language: yaml

freesound_one_shot_percussive_sounds
------------------------------------


* **Annotations:** *None*


**About this dataset:**
   
The dataset includes 10,254 one-shot percussive sounds from Freesound.org, annotated with tags and timbral features from two extractors, for the task of percussive sound analysis.

* **License:** The dataset is licensed under The Creative Commons Attribution Non Commercial Share Alike 4.0 International. Please check the specific license of each sound by running track.license
* **Downloadable Remotes:** ``audio``, ``analysis``, ``sound_info_analysis``, ``metadata``, ``readme``
* **YAML File:** :download:`freesound_one_shot_percussive_sounds.yaml<../cards/freesound_one_shot_percussive_sounds.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{ramires2020, 
          author = "Antonio Ramires and Pritish Chandna and Xavier Favory and Emilia Gómez and Xavier Serra",
          title = "Neural Percussive Synthesis Parametrerised by High-Level Timbral Features",
          booktitle = "Proc. of the IEEE Int. Conf. on Acoustics, Speech and Signal Processing (ICASSP)",
          year = "2020"
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/freesound_one_shot_percussive_sounds.yaml
      :language: yaml

giantsteps_key
--------------


* **Annotations:** ``TempoData``, ``KeyData``


**About this dataset:**
   
The giantsteps_key dataset includes 600 two-minute EDM excerpts annotated with single-key labels and 500 tracks with pitch-class set descriptions; it aims to evaluate key estimation algorithms in EDM.

* **License:** Creative Commons Attribution Share Alike 4.0 International.
* **Downloadable Remotes:** ``audio``, ``keys``, ``metadata``
* **YAML File:** :download:`giantsteps_key.yaml<../cards/giantsteps_key.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{knees2015two,
        title={Two data sets for tempo estimation and key detection in electronic dance music annotated from user corrections},
        author={Knees, Peter and Faraldo P{'e}rez, {'A}ngel and Boyer, Herrera and Vogl, Richard and B{"o}ck, Sebastian and H{"o}rschl{"a}ger, Florian and Le Goff, Mickael and others},
        booktitle={Proceedings of the 16th International Society for Music Information Retrieval Conference (ISMIR); 2015 Oct 26-30; M{'a}laga, Spain.[M{'a}laga]: International Society for Music Information Retrieval, 2015. p. 364-70.},
        year={2015},
        organization={International Society for Music Information Retrieval (ISMIR)}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/giantsteps_key.yaml
      :language: yaml

giantsteps_tempo
----------------


* **Annotations:** ``TempoData``


**About this dataset:**
   
The giantsteps_tempo dataset includes 664 2-minute audio previews of electronic dance music from Beatport, with annotations for tempo and genre provided through manual corrections, focusing on tempo estimation.

* **License:** Creative Commons Attribution Share Alike 4.0 International.
* **Downloadable Remotes:** ``annotations``
* **YAML File:** :download:`giantsteps_tempo.yaml<../cards/giantsteps_tempo.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the audio files of the Giant Steps Tempo dataset are not available

   ::

       for download. If you have the Giant Steps audio dataset, place the contents into
       a folder called GiantSteps_tempo with the following structure:
           > GiantSteps_tempo/
               > giantsteps-tempo-dataset-0b7d47ba8cae59d3535a02e3db69e2cf6d0af5bb/
               > audio/
       and copy the folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{knees2015two,
        title={Two data sets for tempo estimation and key detection in electronic dance music annotated from user corrections},
        author={Knees, Peter and Faraldo P{'e}rez, {'A}ngel and Boyer, Herrera and Vogl, Richard and B{"o}ck, Sebastian and H{"o}rschl{"a}ger, Florian and Le Goff, Mickael and others},
        booktitle={Proceedings of the 16th International Society for Music Information Retrieval Conference (ISMIR); 2015 Oct 26-30; M{'a}laga, Spain.[M{'a}laga]: International Society for Music Information Retrieval, 2015. p. 364-70.},
        year={2015},
        organization={International Society for Music Information Retrieval (ISMIR)},
      }
      @inproceedings{SchreiberM18a_Tempo_ISMIR,
        author={Hendrik Schreiber and Meinard M{"u}ller},
        title={A Crowdsourced Experiment for Tempo Estimation of Electronic Dance Music},
        booktitle={Proceedings of the International Conference on Music Information Retrieval ({ISMIR})},
        address={Paris, France},
        year={2018},
        url-pdf={http://www.tagtraum.com/download/2018_schreiber_tempo_giantsteps.pdf},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/giantsteps_tempo.yaml
      :language: yaml

good_sounds
-----------


* **Annotations:** ``F0Data``, ``Instrument``


**About this dataset:**
   
The Good-Sounds dataset includes monophonic recordings of 12 instruments, with "Good" and "Bad" sound classifications, where "Bad" is further divided into five sub-classes based on musical dimensions. The primary MIR task involves classifying sound quality.

* **License:** Creative Commons Attribution Share Alike 4.0 International.
* **Downloadable Remotes:** ``packs``, ``ratings``, ``sounds``, ``takes``, ``audios``
* **YAML File:** :download:`good_sounds.yaml<../cards/good_sounds.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{romani2015real,
        title={A Real-Time System for Measuring Sound Goodness in Instrumental Sounds},
        author={Romani Picas, Oriol and Parra Rodriguez, Hector and Dabiri, Dara and Tokuda, Hiroshi and Hariya, Wataru and Oishi, Koji and Serra, Xavier},
        booktitle={Audio Engineering Society Convention 138},
        year={2015},
        organization={Audio Engineering Society}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/good_sounds.yaml
      :language: yaml

groove_midi
-----------


* **Annotations:** ``BeatData``, ``EventData``, ``TempoData``, ``NoteData``


**About this dataset:**
   
The Groove MIDI Dataset includes 13.6 hours of aligned MIDI and synthesized audio of human-performed drumming, with annotations for genre, tempo, and drummer ID, primarily for groove and style analysis.

* **License:** Creative Commons Attribution 4.0 International (CC BY 4.0) License.
* **Downloadable Remotes:** ``all``
* **YAML File:** :download:`groove_midi.yaml<../cards/groove_midi.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{groove2019,
          Author = {Jon Gillick and Adam Roberts and Jesse Engel and Douglas Eck
                    and David Bamman},
          Title = {Learning to Groove with Inverse Sequence Transformations},
          Booktitle = {International Conference on Machine Learning (ICML)},
          Year = {2019},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/groove_midi.yaml
      :language: yaml

gtzan_genre
-----------


* **Annotations:** ``BeatData``, ``Genre``, ``TempoData``


**About this dataset:**
   
The GTZAN Genre Dataset includes 1000 30-second audio tracks (10 genres, 100 tracks each) in .wav format. Annotations provide genre labels for each track, primarily supporting genre classification tasks.

* **License:** Unfortunately we couldn't find the license information for the GTZAN_genre dataset.
* **Downloadable Remotes:** ``all``, ``mini``, ``tempo_beat_annotations``
* **YAML File:** :download:`gtzan_genre.yaml<../cards/gtzan_genre.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{tzanetakis2002gtzan,
        title={GTZAN genre collection},
        author={Tzanetakis, George and Cook, P},
        journal={Music Analysis, Retrieval and Synthesis for Audio Signals},
        year={2002}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/gtzan_genre.yaml
      :language: yaml

guitarset
---------


* **Annotations:** ``BeatData``, ``NoteData``, ``ChordData``, ``F0Data``, ``MultiF0Data``, ``KeyData``


**About this dataset:**
   
GuitarSet includes 360 30-second acoustic guitar excerpts across various styles, tempi, and progressions, with annotations for pitch, beats, tempo, and chords. The dataset supports tasks like pitch tracking, beat detection, and chord recognition.

* **License:** MIT License.
* **Downloadable Remotes:** ``annotations``, ``audio_hex_debleeded``, ``audio_hex_original``, ``audio_mic``, ``audio_mix``
* **YAML File:** :download:`guitarset.yaml<../cards/guitarset.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{xi2018guitarset,
      title={GuitarSet: A Dataset for Guitar Transcription},
      author={Xi, Qingyang and Bittner, Rachel M and Ye, Xuzhou and Pauwels, Johan and Bello, Juan P},
      booktitle={International Society of Music Information Retrieval (ISMIR)},
      year={2018}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/guitarset.yaml
      :language: yaml

hainsworth
----------


* **Annotations:** ``BeatData``, ``TempoData``


**About this dataset:**
   
The Hainsworth Dataset includes 222 one-minute musical excerpts across six genres, with annotations for beat and downbeat locations. It is primarily used for beat tracking and downbeat detection, offering a valuable resource for researchers and developers in MIR.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** *No direct download available*
* **YAML File:** :download:`hainsworth.yaml<../cards/hainsworth.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the Hainsworth dataset is not available for download.

   ::

       If you have the Hainsworth dataset, place the contents into a folder called
       hainsworth with the following structure:
           > H_1.0/
               > audio/
               > annotations/beats
               > annotations/tempo
       and copy the hainsworth folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{article,
      author = {Macleod, Malcolm and Hainsworth, Stephen},
      year = {2004},
      month = {11},
      pages = {},
      title = {Particle Filtering Applied to Musical Tempo Tracking},
      volume = {2004},
      journal = {EURASIP Journal on Advances in Signal Processing},
      doi = {10.1155/S1110865704408099}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/hainsworth.yaml
      :language: yaml

idmt_smt_audio_effects
----------------------


* **Annotations:** ``Instrument``, ``NoteData``


**About this dataset:**
   
This dataset includes 55,044 mono and stereo WAV files of electric guitar and bass notes with 11 types of audio effects, covering 30 hours of audio. Annotations provide details on effects, instruments, and settings, facilitating the task of detecting and classifying audio effects.

* **License:** Creative Commons BY-NC-ND 4.0. https://creativecommons.org/licenses/by-nc-nd/4.0/
* **Downloadable Remotes:** ``full_dataset``
* **YAML File:** :download:`idmt_smt_audio_effects.yaml<../cards/idmt_smt_audio_effects.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   IDMT-SMT-Audio-Effects Dataset is available at:

   ::

       https://www.idmt.fraunhofer.de/en/publications/datasets/audio_effects.html
       And Zenodo:
       https://zenodo.org/records/7544032
    
       Folder tree:
       data_home/
       ├── Bass monophon/
       │   ├── Lists
       │   └── Samples
       ├── Bass monophon2
       ├── Gitarre monophon/
       │   ├── Lists
       │   ├── Samples
       │   └── ReadMe.txt
       ├── Gitarre monophon2
       ├── Gitarre polyphon/
       │   ├── Lists
       │   └── Samples
       ├── Gitarre polyphon2
       ├── Gitarre_polyphon2.zip       # Duplicate of Gitarre polyphon2
       ├── IDMT-SMT-AUDIO-EFFECTS/     # Empty folder
       └── IDMT-SMT-Audio-Effects-Description.pdf

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @dataset{stein_michael_2023_7544032,
        author       = {Stein, Michael},
        title        = {IDMT-SMT-Audio-Effects Dataset},
        month        = jan,
        year         = 2023,
        publisher    = {Zenodo},
        version      = {1.0.0},
        doi          = {10.5281/zenodo.7544032},
        url          = {https://doi.org/10.5281/zenodo.7544032}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/idmt_smt_audio_effects.yaml
      :language: yaml

ikala
-----


* **Annotations:** ``F0Data``, ``Instrument``, ``NoteData``, ``LyricData``


**About this dataset:**
   
The iKala dataset includes 30-second excerpts from 206 songs with separated vocal and instrumental tracks, along with labeled pitch contours and lyrics for 252 excerpts, primarily for pitch tracking and lyric synchronization tasks.

* **License:** When it was distributed, Ikala used to have a custom license. Visit http://mac.citi.sinica.edu.tw/ikala/ for more details.
* **Downloadable Remotes:** ``metadata``, ``notes_pyin``
* **YAML File:** :download:`ikala.yaml<../cards/ikala.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately most of the iKala dataset is not available for download.

   ::

       If you have the iKala dataset, place the contents into a folder called
       iKala with the following structure:
           > iKala/
               > Lyrics/
               > PitchLabel/
               > Wavfile/
       and copy the iKala folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{chan2015vocal,
          title={Vocal activity informed singing voice separation with the iKala dataset},
          author={Chan, Tak-Shing and Yeh, Tzu-Chun and Fan, Zhe-Cheng and Chen, Hung-Wei and Su, Li and Yang, Yi-Hsuan and
          Jang, Roger},
          booktitle={2015 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)},
          pages={718--722},
          year={2015},
          organization={IEEE}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/ikala.yaml
      :language: yaml

irmas
-----


* **Annotations:** ``Instrument``


**About this dataset:**
   
IRMAS includes 9,579 musical audio excerpts of 3 seconds each, covering 11 instruments and two datasets with annotations for predominant instruments, drum presence, and musical genre. The primary MIR task is instrument recognition.

* **License:** Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License.
* **Downloadable Remotes:** ``training_data``, ``testing_data_1``, ``testing_data_2``, ``testing_data_3``
* **YAML File:** :download:`irmas.yaml<../cards/irmas.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @dataset{juan_j_bosch_2014_1290750,
        author       = {Juan J. Bosch and Ferdinand Fuhrmann and Perfecto Herrera},
        title        = {{IRMAS: a dataset for instrument recognition in musical audio signals}},
        month        = sep,
        year         = 2014,
        publisher    = {Zenodo},
        version      = {1.0},
        doi          = {10.5281/zenodo.1290750},
        url          = {https://doi.org/10.5281/zenodo.1290750}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/irmas.yaml
      :language: yaml

jtd
---


* **Annotations:** ``BeatData``, ``NoteData``, ``EventData``


**About this dataset:**
   
The Jazz Trio Database (JTD) includes 1,294 multitrack jazz performances, with annotations for beat and downbeat timestamps, MIDI transcriptions, and onset timestamps for unmixed audio tracks, primarily for jazz piano trio performances. The dataset supports tasks like onset detection, beat tracking, and automatic transcription.

* **License:** The MIT License (MIT) Copyright (c) 2023, Huw Cheston Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
* **Downloadable Remotes:** ``annotations``
* **YAML File:** :download:`jtd.yaml<../cards/jtd.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   To download the audio for files for JTD, visit: https://zenodo.org/records/13828030 and request access.

   After you've been granted access, press the "Download all" button on the Zenodo record.

   This will create a new file named files-archive (with no extension). Rename the file to files-archive.zip and extract 
   using any unzipping tool (7zip, WinRAR, the unarchiver) or the command line. This will give you a list of multi-part 
   zip files in the form [processed.zip.001, processed.zip.002, ...] and [raw.zip.001, raw.zip.002, ...]. 

   To extract these, use 7zip from the command line:

   ```
   7z x processed.zip.001
   7z x raw.zip.001
   ```

   Note that the default `unzip` command on Linux can't handle these files, so you'll need to use 7zip. You may also be 
   able to use a GUI tool like WinRAR, which was used to create the archive in the first place. 

   These commands will extract the audio to the current folder. You'll then need to move the results to {0}/processed and 
   {0}/raw, respectively, creating these folders if they don't already exist.

   Combined with the annotation files (which can be obtained by calling `.download()` on the `mirdata.Dataset` instance 
   you've just initialized), the end result should be a file structure that looks like:

   ```
   {0}
   ├─ raw
   │  ├─ barronk-allgodschildren-drummondrrileyb-1990-8b77c067.wav    # one to three audio files per performance
   │  ├─ ...
   ├─ processed
   │  ├─ barronk-allgodschildren-drummondrrileyb-1990-8b77c067_piano.wav     # always three audio files per performance
   │  ├─ barronk-allgodschildren-drummondrrileyb-1990-8b77c067_bass.wav
   │  ├─ barronk-allgodschildren-drummondrrileyb-1990-8b77c067_drums.wav
   │  ├─ ...
   ├─ annotations
   │  ├─ barronk-allgodschildren-drummondrrileyb-1990-8b77c067    # one folder per performance
   │  │  ├─ bass_onsets.csv
   │  │  ├─ beats.csv
   │  │  ├─ ...
   │  ├─ barronk-beautifullove-mrazgrileyb-2009-c87abfa6
   │  ├─ ...
   ```

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{jazz-trio-database
          title = {Jazz Trio Database: Automated Annotation of Jazz Piano Trio Recordings Processed Using Audio Source Separation},
          url = {https://doi.org/10.5334/tismir.186},
          doi = {10.5334/tismir.186},
          publisher = {Transactions of the International Society for Music Information Retrieval},
          author = {Cheston, Huw and Schlichting, Joshua L and Cross, Ian and Harrison, Peter M C},
          year = {2024},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/jtd.yaml
      :language: yaml

maestro
-------


* **Annotations:** ``NoteData``


**About this dataset:**
   
MAESTRO includes over 200 hours of high-quality piano performances with precise MIDI and audio synchronization, providing key strike velocities and piece-level annotations. The primary MIR task involves analyzing and aligning audio with MIDI notes.

* **License:** Creative Commons Attribution Non-Commercial Share-Alike 4.0 (CC BY-NC-SA 4.0).
* **Downloadable Remotes:** ``all``, ``midi``, ``metadata``
* **YAML File:** :download:`maestro.yaml<../cards/maestro.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{
        hawthorne2018enabling,
        title={Enabling Factorized Piano Music Modeling and Generation with the {MAESTRO} Dataset},
        author={Curtis Hawthorne and Andriy Stasyuk and Adam Roberts and Ian Simon and Cheng-Zhi Anna Huang and Sander Dieleman and Erich Elsen and Jesse Engel and Douglas Eck},
        booktitle={International Conference on Learning Representations},
        year={2019},
        url={https://openreview.net/forum?id=r1lYRjC9F7},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/maestro.yaml
      :language: yaml

mdb_stem_synth
--------------


* **Annotations:** ``F0Data``


**About this dataset:**
   
The MDB-stem-synth dataset includes 230 solo stems from various musical instruments and voices resynthesized for perfect pitch annotation, suitable for tasks like music transcription and analysis.

* **License:** Attribution-NonCommercial 4.0 International
* **Downloadable Remotes:** ``mdb_stem_synth``
* **YAML File:** :download:`mdb_stem_synth.yaml<../cards/mdb_stem_synth.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{salamon2017analysis,
        title={An analysis/synthesis framework for automatic f0 annotation of multitrack datasets},
        author={Salamon, Justin and Bittner, Rachel M and Bonada, Jordi and Bosch, Juan J and G{'o}mez Guti{'e}rrez, Emilia and Bello, Juan Pablo},
        booktitle={International Society for Music Information Retrieval Conference},
        year={2017},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/mdb_stem_synth.yaml
      :language: yaml

medley_solos_db
---------------


* **Annotations:** ``Instrument``


**About this dataset:**
   
The Medley-solos-DB dataset includes 3-second audio clips of solo instruments from MedleyDB and solosDB, covering eight instruments (clarinet, distorted electric guitar, female singer, flute, piano, tenor saxophone, trumpet, violin), for automatic musical instrument recognition.

* **License:** Creative Commons Attribution 4.0 International.
* **Downloadable Remotes:** ``annotations``, ``audio``
* **YAML File:** :download:`medley_solos_db.yaml<../cards/medley_solos_db.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{lostanlen2019ismir,
          title={Deep Convolutional Networks in the Pitch Spiral for Musical Instrument Recognition},
          author={Lostanlen, Vincent and Cella, Carmine Emanuele},
          booktitle={International Society of Music Information Retrieval (ISMIR)},
          year={2016}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/medley_solos_db.yaml
      :language: yaml

medleydb_melody
---------------


* **Annotations:** ``F0Data``, ``Instrument``, ``MultiF0Data``


**About this dataset:**
   
MedleyDB melody includes multitrack recordings with melody f0 annotations for 20 songs, aimed at melody extraction research.

* **License:** Creative Commons Attribution Non-Commercial Share-Alike 4.0 (CC BY-NC-SA 4.0).
* **Downloadable Remotes:** *No direct download available*
* **YAML File:** :download:`medleydb_melody.yaml<../cards/medleydb_melody.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   To download this dataset, visit:
       https://zenodo.org/record/2628782#.XKZdABNKh24
       and request access.

       Once downloaded, unzip the file MedleyDB-Melody.zip
       and copy the result to:
       {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{bittner2014medleydb,
          Author = {Bittner, Rachel M and Salamon, Justin and Tierney, Mike and Mauch, Matthias and Cannam, Chris and Bello, Juan P},
          Booktitle = {International Society of Music Information Retrieval (ISMIR)},
          Month = {October},
          Title = {Medley{DB}: A Multitrack Dataset for Annotation-Intensive {MIR} Research},
          Year = {2014}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/medleydb_melody.yaml
      :language: yaml

medleydb_pitch
--------------


* **Annotations:** ``F0Data``, ``Instrument``, ``NoteData``


**About this dataset:**
   
MedleyDB pitch includes f0-annotated, monophonic stems from multitrack recordings; annotations enable melody extraction and instrument recognition tasks.

* **License:** Creative Commons Attribution Non-Commercial Share-Alike 4.0 (CC BY-NC-SA 4.0).
* **Downloadable Remotes:** ``notes_pyin``
* **YAML File:** :download:`medleydb_pitch.yaml<../cards/medleydb_pitch.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   To download this dataset, visit:
       https://zenodo.org/record/2620624#.XKZc7hNKh24
       and request access.

       Once downloaded, unzip the file MedleyDB-Pitch.zip
       and copy the result to:
       {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{bittner2014medleydb,
          Author = {Bittner, Rachel M and Salamon, Justin and Tierney, Mike and Mauch, Matthias and Cannam, Chris and Bello, Juan P},
          Booktitle = {International Society of Music Information Retrieval (ISMIR)},
          Month = {October},
          Title = {Medley{DB}: A Multitrack Dataset for Annotation-Intensive {MIR} Research},
          Year = {2014}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/medleydb_pitch.yaml
      :language: yaml

mridangam_stroke
----------------


* **Annotations:** *None*


**About this dataset:**
   
The Mridangam Stroke dataset includes 6977 audio samples of 10 strokes across 6 tonics, recorded in a studio. Annotations are in filenames indicating stroke, tonic, and instance number, suitable for stroke recognition tasks.

* **License:** Creative Commons Attribution 3.0 Unported (CC BY 3.0) License.
* **Downloadable Remotes:** ``remote_data``
* **YAML File:** :download:`mridangam_stroke.yaml<../cards/mridangam_stroke.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{Anantapadmanabhan2013,
          author = {Anantapadmanabhan, Akshay and Bellur, Ashwin and Murthy, Hema A.},
          doi = {10.1109/ICASSP.2013.6637633},
          isbn = {9781479903566},
          issn = {15206149},
          journal = {ICASSP, IEEE International Conference on Acoustics, Speech and Signal Processing - Proceedings},
          keywords = {Hidden Markov models, Modal Analysis, Mridangam, Non-negative Matrix Factorization,
          automatic transcription},
          pages = {181--185},
          title = {{Modal analysis and transcription of strokes of the mridangam using non-negative matrix factorization}},
          year = {2013}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/mridangam_stroke.yaml
      :language: yaml

mtg_jamendo_autotagging_moodtheme
---------------------------------


* **Annotations:** *None*


**About this dataset:**
   
The dataset includes 18,486 full audio tracks from Jamendo with 195 mood/theme tags, suitable for emotion and theme recognition tasks in MIR, providing ground-truth tags for each track.

* **License:** Creative Commons Attribution NonCommercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``metadata``
* **YAML File:** :download:`mtg_jamendo_autotagging_moodtheme.yaml<../cards/mtg_jamendo_autotagging_moodtheme.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   The audio files can be downloaded following the path described in https://github.com/MTG/mtg-jamendo-dataset#downloading-the-data

   ::

    
       To download audio, unpack and validate all tar archives:
    
       .. code-block:: console

             mkdir /path/to/download
             python3 scripts/download/download.py --dataset autotagging_moodtheme --type audio /path/to/download --unpack --remove
    
       Later add the files to a folder into mir_datasets called audio/ with the following structure:
           > mtg_jamendo_autotagging_moodtheme/
               > audios/
                   > 00/
                   ...
                   > 99/

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @conference {bogdanov2019mtg,
          author = "Bogdanov, Dmitry and Won, Minz and Tovstogan, Philip and Porter, Alastair and Serra, Xavier",
          title = "The MTG-Jamendo Dataset for Automatic Music Tagging",
          booktitle = "Machine Learning for Music Discovery Workshop, International Conference on Machine Learning (ICML 2019)",
          year = "2019",
          address = "Long Beach, CA, United States",
          url = "http://hdl.handle.net/10230/42015"
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/mtg_jamendo_autotagging_moodtheme.yaml
      :language: yaml

openmic2018
-----------


* **Annotations:** ``Instrument``


**About this dataset:**
   
The OpenMIC-2018 dataset includes 20000 10-second excerpts from polyphonic music, annotated for 20 instrument categories; it provides raw audio, VGGish features, and partial annotations with confidence ratings, aimed at polyphonic music instrument classification.

* **License:** Creative Commons Attribution 4.0 International
* **Downloadable Remotes:** ``remote_data``
* **YAML File:** :download:`openmic2018.yaml<../cards/openmic2018.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{DBLP:conf/ismir/HumphreyDM18,
        author    = {Eric Humphrey and
                     Simon Durand and
                     Brian McFee},
        editor    = {Emilia G{'{o}}mez and
                     Xiao Hu and
                     Eric Humphrey and
                     Emmanouil Benetos},
        title     = {OpenMIC-2018: An Open Data-set for Multiple Instrument Recognition},
        booktitle = {Proceedings of the 19th International Society for Music Information
                     Retrieval Conference, {ISMIR} 2018, Paris, France, September 23-27,
                     2018},
        pages     = {438--444},
        year      = {2018},
        url       = {http://ismir2018.ircam.fr/doc/pdfs/248\_Paper.pdf},
        timestamp = {Thu, 12 Mar 2020 11:33:14 +0100},
        biburl    = {https://dblp.org/rec/conf/ismir/HumphreyDM18.bib},
        bibsource = {dblp computer science bibliography, https://dblp.org}
      },
      @dataset{humphrey_eric_j_2018_1432913,
        author       = {Humphrey, Eric J. and
                        Durand, Simon and
                        McFee, Brian},
        title        = {OpenMIC-2018},
        month        = sep,
        year         = 2018,
        publisher    = {Zenodo},
        version      = {v1.0.0},
        doi          = {10.5281/zenodo.1432913},
        url          = {https://doi.org/10.5281/zenodo.1432913}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/openmic2018.yaml
      :language: yaml

orchset
-------


* **Annotations:** ``F0Data``, ``Instrument``


**About this dataset:**
   
Orchset includes 64 symphonic music audio excerpts with annotated melodies, aimed at melody extraction tasks.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``all``
* **YAML File:** :download:`orchset.yaml<../cards/orchset.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{bosch2016evaluation,
          title={Evaluation and combination of pitch estimation methods for melody extraction in symphonic classical music},
          author={Bosch, Juan J and Marxer, Ricard and G{'o}mez, Emilia},
          journal={Journal of New Music Research},
          volume={45},
          number={2},
          pages={101--117},
          year={2016},
          publisher={Taylor \& Francis}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/orchset.yaml
      :language: yaml

phenicx_anechoic
----------------


* **Annotations:** ``NoteData``


**About this dataset:**
   
The PHENICX-Anechoic Dataset includes denoised anechoic recordings of symphonic music passages, with annotations for musical note onsets and offsets, suitable for tasks like score-informed source separation and multi-pitch estimation.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International
* **Downloadable Remotes:** ``all``
* **YAML File:** :download:`phenicx_anechoic.yaml<../cards/phenicx_anechoic.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{miron2016score,
        title={Score-informed source separation for multichannel orchestral recordings},
        author={Miron, Marius and Carabias-Orti, Julio J and Bosch, Juan J and G{'o}mez, Emilia and Janer, Jordi},
        journal={Journal of Electrical and Computer Engineering},
        volume={2016},
        year={2016},
        publisher={Hindawi}
      }
      @article{patynen2008anechoic,
        title={Anechoic recording system for symphony orchestra},
        author={P{"a}tynen, Jukka and Pulkki, Ville and Lokki, Tapio},
        journal={Acta Acustica united with Acustica},
        volume={94},
        number={6},
        pages={856--865},
        year={2008},
        publisher={S. Hirzel Verlag}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/phenicx_anechoic.yaml
      :language: yaml

queen
-----


* **Annotations:** ``SectionData``, ``KeyData``, ``ChordData``


**About this dataset:**
   
Queen Dataset includes chord, key, and segmentation annotations for 51 songs from Queen's greatest hits albums. The primary MIR task involves analyzing these annotations to improve chord and key detection accuracy.

* **License:** Unfortunately we couldn't find the license information for Queen dataset.
* **Downloadable Remotes:** ``annotations``
* **YAML File:** :download:`queen.yaml<../cards/queen.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the audio files of Queen dataset are not available

   ::

           for download. If you have Queen dataset, place the contents into
           a folder called Queen with the following structure:
               > Queen/
                   > annotations/
                   > audio/
           and copy Queen folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{mauch2009beatles,
          title={OMRAS2 metadata project 2009},
          author={Mauch, Matthias and Cannam, Chris and Davies, Matthew and Dixon, Simon and Harte,
          Christopher and Kolozali, Sefki and Tidhar, Dan and Sandler, Mark},
          booktitle={12th International Society for Music Information Retrieval Conference},
          year={2009},
          series = {ISMIR}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/queen.yaml
      :language: yaml

rwc_classical
-------------


* **Annotations:** ``BeatData``, ``SectionData``


**About this dataset:**
   
The RWC Classical Dataset includes 50 classical music pieces with annotations for beats, providing information for tasks such as rhythm analysis and beat tracking.

* **License:** From the dataset's owner webpage: 'Users who have submitted the Pledge and received authorization may freely use the database for research purposes without facing the usual copyright restrictions, but all of the copyrights and neighboring rights connected with this database belong to the National Institute of Advanced Industrial Science and Technology and are managed by the RWC Music Database Administrator. Persons or organizations that have not submitted a Pledge and that have not received authorization may not use the database.' See https://staff.aist.go.jp/m.goto/RWC-MDB/ for more details.
* **Downloadable Remotes:** ``annotations_beat``, ``annotations_sections``, ``metadata``
* **YAML File:** :download:`rwc_classical.yaml<../cards/rwc_classical.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the audio files of the RWC-Classical dataset are not available

   ::

       for download. If you have the RWC-Classical dataset, place the contents into a
       folder called RWC-Classical with the following structure:
           > RWC-Classical/
               > annotations/
               > audio/rwc-c-m0i with i in [1 .. 6]
               > metadata-master/
       and copy the RWC-Classical folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{goto2002rwc,
        title={RWC Music Database: Popular, Classical and Jazz Music Databases.},
        author={Goto, Masataka and Hashiguchi, Hiroki and Nishimura, Takuichi and Oka, Ryuichi},
        booktitle={3rd International Society for Music Information Retrieval Conference},
        year={2002},
        series={ISMIR},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/rwc_classical.yaml
      :language: yaml

rwc_jazz
--------


* **Annotations:** ``BeatData``, ``Instrument``, ``SectionData``


**About this dataset:**
   
The RWC Jazz Dataset includes 50 jazz pieces with instrumentation and style variations, along with fusion pieces combining jazz with other genres. Annotations provide information on piece structure and performance details for music information retrieval tasks.

* **License:** From the dataset's owner webpage: 'Users who have submitted the Pledge and received authorization may freely use the database for research purposes without facing the usual copyright restrictions, but all of the copyrights and neighboring rights connected with this database belong to the National Institute of Advanced Industrial Science and Technology and are managed by the RWC Music Database Administrator. Persons or organizations that have not submitted a Pledge and that have not received authorization may not use the database.' See https://staff.aist.go.jp/m.goto/RWC-MDB/ for more details.
* **Downloadable Remotes:** ``metadata``, ``annotations_beat``, ``annotations_sections``
* **YAML File:** :download:`rwc_jazz.yaml<../cards/rwc_jazz.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the audio files of the RWC-Jazz dataset are not available

   ::

       for download. If you have the RWC-Jazz dataset, place the contents into a
       folder called RWC-Jazz with the following structure:
           > RWC-Jazz/
               > annotations/
               > audio/rwc-j-m0i with i in [1 .. 4]
               > metadata-master/
       and copy the RWC-Jazz folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{goto2002rwc,
        title={RWC Music Database: Popular, Classical and Jazz Music Databases.},
        author={Goto, Masataka and Hashiguchi, Hiroki and Nishimura, Takuichi and Oka, Ryuichi},
        booktitle={3rd International Society for Music Information Retrieval Conference},
        year={2002},
        series={ISMIR},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/rwc_jazz.yaml
      :language: yaml

rwc_popular
-----------


* **Annotations:** ``BeatData``, ``ChordData``, ``TempoData``, ``EventData``, ``SectionData``, ``Instrument``


**About this dataset:**
   
The RWC Popular Dataset includes 100 songs—20 English-lyric and 80 Japanese-lyric popular music pieces from the 1980s and 1990s. Annotations provide metadata for music information retrieval tasks.

* **License:** From the dataset's owner webpage: 'Users who have submitted the Pledge and received authorization may freely use the database for research purposes without facing the usual copyright restrictions, but all of the copyrights and neighboring rights connected with this database belong to the National Institute of Advanced Industrial Science and Technology and are managed by the RWC Music Database Administrator. Persons or organizations that have not submitted a Pledge and that have not received authorization may not use the database.' See https://staff.aist.go.jp/m.goto/RWC-MDB/ for more details.
* **Downloadable Remotes:** ``metadata``, ``annotations_beat``, ``annotations_sections``, ``annotations_chords``, ``annotations_vocal_act``
* **YAML File:** :download:`rwc_popular.yaml<../cards/rwc_popular.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the audio files of the RWC-Popular dataset are not available

   ::

       for download. If you have the RWC-Popular dataset, place the contents into a
       folder called RWC-Popular with the following structure:
           > RWC-Popular/
               > annotations/
               > audio/rwc-p-m0i with i in [1 .. 7]
               > metadata-master/
       and copy the RWC-Popular folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{goto2002rwc,
        title={RWC Music Database: Popular, Classical and Jazz Music Databases.},
        author={Goto, Masataka and Hashiguchi, Hiroki and Nishimura, Takuichi and Oka, Ryuichi},
        booktitle={3rd International Society for Music Information Retrieval Conference},
        year={2002},
        series={ISMIR},
        note={Cite this if using audio, beat or section annotations},
      }
      @inproceedings{cho2011feature,
        title={A feature smoothing method for chord recognition using recurrence plots},
        author={Cho, Taemin and Bello, Juan P},
        booktitle={12th International Society for Music Information Retrieval Conference},
        year={2011},
        series={ISMIR},
        note={Cite this if using chord annotations},
      }
      @inproceedings{mauch2011timbre,
        title={Timbre and Melody Features for the Recognition of Vocal Activity and Instrumental Solos in Polyphonic Music.},
        author={Mauch, Matthias and Fujihara, Hiromasa and Yoshii, Kazuyoshi and Goto, Masataka},
        booktitle={ISMIR},
        year={2011},
        series={ISMIR},
        note={Cite this if using vocal-instrumental activity annotations},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/rwc_popular.yaml
      :language: yaml

salami
------


* **Annotations:** ``SectionData``


**About this dataset:**
   
The SALAMI dataset includes structural annotations for over 1300 unique tracks, focusing on musical structure; the primary MIR task involves analyzing these annotations for music segmentation and structure recognition.

* **License:** This data is released under a Creative Commons 0 license, effectively dedicating it to the public domain. More information about this dedication and your rights, please see the details here: http://creativecommons.org/publicdomain/zero/1.0/ and http://creativecommons.org/publicdomain/zero/1.0/legalcode.
* **Downloadable Remotes:** ``annotations``
* **YAML File:** :download:`salami.yaml<../cards/salami.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the audio files of the Salami dataset are not available

   ::

       for download. If you have the Salami dataset, place the contents into a
       folder called Salami with the following structure:
           > Salami/
               > salami-data-public-hierarchy-corrections/
               > audio/
       and copy the Salami folder to {}

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{smith2011salami,
          title={Design and creation of a large-scale database of structural annotations.},
          author={Smith, Jordan Bennett Louis and Burgoyne, John Ashley and
                Fujinaga, Ichiro and De Roure, David and Downie, J Stephen},
          booktitle={12th International Society for Music Information Retrieval Conference},
          year={2011},
          series = {ISMIR},
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/salami.yaml
      :language: yaml

saraga_carnatic
---------------


* **Annotations:** ``LyricData``, ``F0Data``, ``TempoData``, ``SectionData``, ``KeyData``


**About this dataset:**
   
The saraga_carnatic dataset includes 249 Carnatic music tracks with time-aligned melody, rhythm, and structural annotations, along with automatically extracted pitch and tonic features. Annotations cover sections, tempos, rhythmic cycles, and phrase transcriptions using solfège symbols.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``all``
* **YAML File:** :download:`saraga_carnatic.yaml<../cards/saraga_carnatic.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @dataset{bozkurt_b_2018_4301737,
        author       = {Bozkurt, B. and
                        Srinivasamurthy, A. and
                        Gulati, S. and
                        Serra, X.},
        title        = {Saraga: research datasets of Indian Art Music},
        month        = may,
        year         = 2018,
        publisher    = {Zenodo},
        version      = {1.5},
        doi          = {10.5281/zenodo.4301737},
        url          = {https://doi.org/10.5281/zenodo.4301737}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/saraga_carnatic.yaml
      :language: yaml

saraga_hindustani
-----------------


* **Annotations:** ``LyricData``, ``F0Data``, ``TempoData``, ``SectionData``, ``KeyData``


**About this dataset:**
   
This dataset includes 108 Hindustani music tracks with time-aligned melody, rhythm, and structural annotations, along with automatically extracted pitch and tonic features. Annotations cover sections, tempos, sama (rhythmic cycles), and phrase transcriptions using solfège symbols.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``all``
* **YAML File:** :download:`saraga_hindustani.yaml<../cards/saraga_hindustani.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @dataset{bozkurt_b_2018_4301737,
        author       = {Bozkurt, B. and
                        Srinivasamurthy, A. and
                        Gulati, S. and
                        Serra, X.},
        title        = {Saraga: research datasets of Indian Art Music},
        month        = may,
        year         = 2018,
        publisher    = {Zenodo},
        version      = {1.5},
        doi          = {10.5281/zenodo.4301737},
        url          = {https://doi.org/10.5281/zenodo.4301737}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/saraga_hindustani.yaml
      :language: yaml

scms
----


* **Annotations:** ``EventData``, ``F0Data``, ``KeyData``


**About this dataset:**
   
This dataset includes 2460 Carnatic Music tracks with time-aligned vocal melodies and synthesized pitch tracks, aimed for pitch extraction research. Annotations provide ground truth for vocal pitch extraction in Indian Art Music recordings.

* **License:** Creative Commons Attribution Non-Commercial Share-Alike 4.0 (CC BY-NC-SA 4.0).
* **Downloadable Remotes:** ``scms``
* **YAML File:** :download:`scms.yaml<../cards/scms.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{Plaja-Roglans-2023,
        author = {Plaja-Roglans, Gen{'\i}s and Nuttall, Thomas and Pearson, Lara and Serra, Xavier and Miron, Marius},
        doi = {10.5334/tismir.137},
        journal = {Transactions of the International Society for Music Information Retrieval},
        keyword = {en_US},
        month = {Jun},
        title = {Repertoire-Specific Vocal Pitch Data Generation for Improved Melodic Analysis of Carnatic Music},
        year = {2023}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/scms.yaml
      :language: yaml

slakh
-----


* **Annotations:** ``Instrument``, ``MultiF0Data``, ``NoteData``


**About this dataset:**
   
The slakh dataset includes 2100 multi-track audio samples and aligned MIDI for music source separation and transcription, synthesized from 187 instrument patches. Annotations provide individual MIDI tracks and mixed audio for 145 hours of music.

* **License:** Creative Commons Attribution 4.0 International
* **Downloadable Remotes:** ``2100-redux``, ``baby``
* **YAML File:** :download:`slakh.yaml<../cards/slakh.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{manilow2019cutting,
        title={Cutting Music Source Separation Some {Slakh}: A Dataset to Study the Impact of Training Data Quality and Quantity},
        author={Manilow, Ethan and Wichern, Gordon and Seetharaman, Prem and Le Roux, Jonathan},
        booktitle={Proc. IEEE Workshop on Applications of Signal Processing to Audio and Acoustics (WASPAA)},
        year={2019},
        organization={IEEE}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/slakh.yaml
      :language: yaml

tinysol
-------


* **Annotations:** ``F0Data``, ``Instrument``


**About this dataset:**
   
TinySOL includes 2913 single-note samples from 14 instruments, suitable for MIR tasks like instrument recognition. Annotations provide a balanced 5-fold split for evaluation.

* **License:** Creative Commons Attribution 4.0 International Public License.
* **Downloadable Remotes:** ``audio``, ``annotations``
* **YAML File:** :download:`tinysol.yaml<../cards/tinysol.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @inproceedings{cella2020preprint,
        author={Cella, Carmine Emanuele and Ghisi, Daniele and Lostanlen, Vincent and
        Lévy, Fabien and Fineberg, Joshua and Maresz, Yan},
        title={{OrchideaSOL}: {A} dataset of extended
        instrumental techniques for computer-aided orchestration},
        bootktitle={Under review},
        year={2020}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/tinysol.yaml
      :language: yaml

tonality_classicaldb
--------------------


* **Annotations:** ``KeyData``


**About this dataset:**
   
The Tonality classicalDB Dataset includes 881 classical music pieces with single-key annotations, primarily for evaluating key estimation algorithms. Audio is private but metadata and spectral features are provided.

* **License:** Creative Commons Attribution Non Commercial Share Alike 4.0 International.
* **Downloadable Remotes:** ``keys``, ``musicbrainz_metadata``, ``HPCPs``, ``spectrums``
* **YAML File:** :download:`tonality_classicaldb.yaml<../cards/tonality_classicaldb.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   Unfortunately the audio files of the Tonality classicalDB dataset are not available

   ::

       for download. If you have the tonality classicalDB audio dataset, place the contents into
       a folder called classicaldb with the following structure:
           > classicaldb/
               > audio/
               > keys/
               > spectrums/
               > HPCPs/
               > musicbrainz_metadata/
       and copy the folder to {} directory

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @article{gomez2006tonal,
        title={Tonal description of music audio signals},
        author={G{'o}mez, Emilia},
        journal={Department of Information and Communication Technologies},
        year={2006}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/tonality_classicaldb.yaml
      :language: yaml

tonas
-----


* **Annotations:** ``F0Data``, ``NoteData``


**About this dataset:**
   
The TONAS dataset includes 72 monophonic a cappella sung excerpts (16 Deblas, 36 Martinete 1, 20 Martinete 2), each about 30 seconds long, with annotations of notes, F0, and energy values, suitable for style classification and similarity tasks.

* **License:** The TONAS dataset is offered free of charge for internal non-commercial use only. You can not redistribute it nor modify it. Dataset by COFLA team. Copyright © 2012 COFLA project, Universidad de Sevilla. Distribution rights granted to Music Technology Group, Universitat Pompeu Fabra. All Rights Reserved.
* **Downloadable Remotes:** *No direct download available*
* **YAML File:** :download:`tonas.yaml<../cards/tonas.yaml>`


.. admonition:: Download Instructions
   :class: dropdown
   

   PLEASE READ CAREFULLY ALL THE INFORMATION SO YOU DON'T MISS ANY STEP:

   ::

           Unfortunately, the TONAS dataset is not available to be shared openly. However,
           you can request access to the dataset in the following link, providing a brief
           explanation of what your are going to use the dataset for:
           ==> https://zenodo.org/record/1290722
           Then, unzip the dataset, change the dataset name to: "tonas" (with lowercase),
           and locate it to {}. If you unzip it into a different path, please remember to set the 
           right data_home when initializing the dataset.

.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      Music material:
      @inproceedings{tonas_music,
          author = {Mora, Joaquin and Gómez, Francisco and Gómez, Emilia
                    and Borrego, Francisco Javier and Díaz-Báñez, José},
          year = {2010},
          month = {01},
          pages = {351-356},
          title = {Characterization and Similarity in A Cappella Flamenco Cantes.}
      }

      Transcriptions:
      @inproceedings{tonas_annotations,
          author = {E. {Gómez} and J. {Bonada}},
          journal = {Computer Music Journal},
          title = {Towards Computer-Assisted Flamenco Transcription: An Experimental 
                 Comparison of Automatic Transcription Algorithms as Applied to A 
                 Cappella Singing},
          year = {2013},
          volume = {37},
          number = {2},
          pages = {73-90},
          doi = {10.1162/COMJ_a_00180}}

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/tonas.yaml
      :language: yaml

vocadito
--------


* **Annotations:** ``F0Data``, ``LyricData``, ``NoteData``


**About this dataset:**
   
vocadito includes 40 solo, monophonic singing excerpts in 7 languages; annotations provide frame-level f0, note annotations, lyrics, and language identification. Primary MIR task involves pitch and melody analysis.

* **License:** Creative Commons Attribution 4.0 International
* **Downloadable Remotes:** ``zenodo``
* **YAML File:** :download:`vocadito.yaml<../cards/vocadito.yaml>`


.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

      @techreport{bittner2021vocadito,
            title={vocadito: A dataset of solo vocals with $f_0$, note, and lyric annotations}, 
            author={Rachel M. Bittner and Katherine Pasalo and Juan José Bosch and Gabriel Meseguer-Brocal and David Rubinstein},
            year={2021},
            institution={Spotify},
            number={2110.05580},
            note={https://arxiv.org/abs/2110.05580}
      }

.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../cards/vocadito.yaml
      :language: yaml
