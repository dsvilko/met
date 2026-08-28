# GOAL

Build a beautiful webpage (pure javascript) to serve as a 
gallery of a large collection of meteorite macro photos.

These photos are currently arranged in a hierarhical folder
structure according to meteorite types and sub-types 
(hierarchy multiple levels deep), starting at ./Photos 
ending up with folders named after individual meteorites
(with some info) containing one or more photos (jpg, jpeg) 
and an info.txt, a text file with a short description of
that particular meteorite. 

The webpage will need to pull all the required data either
from a simple filelist (file.list) or you could build a 
helper script that would generate more convenient 
manifest.json that perhaps not only contains the list of
all the files (photos) but also the text of the info.txt 
files for individual meteorites. This would be useful with
description text search.

## GALLERY NAVIGATION

I would like to have an option to switch between 3 different
display modes:

1. Hierarchy mode
In this mode the only thing that is shown are the next 
sub-categories down. As a thumbnail for each of these
subcategories a slow slideshow of random photos of meteorites 
contained in that sub-category should be shown (maybe a
new photos every 5s). These should be cropped to a square 
format and shown with a text label matching the next
category down (folder name). Of course, when you drill down
far enough, sub-categories will turn into individual
meteorite folders. Still keeping the same logic
as before, the thumbnail shown is a random slideshow of 
all the photos inside of that final folder.  Finally 
opening the final individual meteorite folder should show
all the images inside that folder - no labels this time but
above the photo-grid, the description of that meteorite 
should be shown (info.txt) below the clearly written
meteorite name (name of the folder).

2. Collapsed mode
In this mode, all the individual meteorite folders are 
shown matching the current category and all below it.
This time maybe only randomly select a single image from
the meteorite folders as a representative thumbnail (no
slideshow as a large number of images can already be
shown). Clicking on any of those folders should, equavalent
to previous mode, show all the photos within.

3. Individual photos mode
In this mode ALL the individual photos that match the
current category and all sub-categories below it should
be shown. Text label should be from the name of the meteorite
(the name of the final folder containing that image).

There should be some guardrails preventing showing 
too many items at once (set the limit to 100 for now). 
Split them into pages if >100 items would need to be
shown.

### Slideshow

There should be a slideshow button that starts a fullscreen
random slideshow from among the currently filtered 
meteorite photos. That means that if the current selected
category is Chondrites/OC, slideshow shows randomly
ordered photos among those meteorites. 


### Sorting

In all three modes user should also be able to switch
between 3 sorting modes:
1. By category (sorted alphabetically using the full path)
2. By name (sorted alphabetically using only the final 
folder name)
3. Randomly.

### Search

A separate name search and full description text search
providing list similar to Collapsed mode of all the
matching meteorites.

## GRAPHICAL DESIGN

Simple, modern, prefering dark background as almost all
meteorites are photographed on black background.
Maybe use PhotoSwipe library and I prefer crossfade transitions.
Title on top: Domjan Svilković Meteorite Collection

### INFO TEXT

Welcome to the photo album of my meteorite collection. For any inquiries, I can be contacted at dsvilko@gmail.com. Please note that due to a large demand, I can no longer help identify stones you have found and suspect might be a meteorite. There are dedicated websites as well as excellent Facebook groups that can help you to ID your rock.

ABOUT ME:
I'm a physics teacher, meteorite collector and macro photographer from Zagreb, Croatia. Due to my very limited budget, most of my meteorite collection is in a form of micro fragments and small slices but it covers a huge range of different meteoritic material. I've started collecting in 2019 and my collection currently contains samples of over 200 different meteorites, making it the most varied meteorite collection in Croatia. The collection is also often used for STEM outreach, especially to school kids. I would especially like to thank all the generous meteorite dealers and my "meteoritic" friends that have over these last few years helped grow my collection. Needless to say that without such help, my collection would be nowhere near this extensive.

PHOTO LICENCING:
All of these macro photos are copyrighted by me. If you want to use my photos, please contact me at dsvilko@gmail.com. In general, if it's purely for educational/outreach, non-commercial use, I'll probably grant free use of my photos. If it's for commercial use, we will work something out.

## A SAMPLE OF THE FOLDER/FILE STRUCTURE
```
Photos/
Photos/Achondrites/
Photos/Achondrites/Lunar/
Photos/Achondrites/Lunar/ferroan anorthosite
Photos/Achondrites/Lunar/ferroan anorthosite/Gadamis 003 (Lunar ferroan anorthosite) - 81mg
Photos/Achondrites/Lunar/ferroan anorthosite/Gadamis 003 (Lunar ferroan anorthosite) - 81mg/[Group 0]-2022-04-04-19.11.25-ZS-DMap_2022-04-04-19.13.10-ZS-DMap-4 images-01.jpeg
Photos/Achondrites/Lunar/ferroan anorthosite/Gadamis 003 (Lunar ferroan anorthosite) - 81mg/info.txt
Photos/Achondrites/Lunar/ferroan anorthosite/Gadamis 003 (Lunar ferroan anorthosite) - 81mg/image-147.jpeg
Photos/Achondrites/Lunar/ferroan anorthosite/Gadamis 003 (Lunar ferroan anorthosite) - 81mg/[Group 0]-2022-04-11-16.51.15-ZS-DMap_2022-04-11-16.52.07-ZS-DMap-2 images-02.jpeg
Photos/Achondrites/Lunar/melt breccia
Photos/Achondrites/Lunar/melt breccia/Adrar 013 (Lunar melt breccia - anorthositic norite-gabbro) - 0.366g
Photos/Achondrites/Lunar/melt breccia/Adrar 013 (Lunar melt breccia - anorthositic norite-gabbro) - 0.366g/[Group 0]-2024-05-30-16.10.25-ZS-DMap_2024-05-30-16.17.28-ZS-DMap-12 images.jpg
Photos/Achondrites/Lunar/melt breccia/Adrar 013 (Lunar melt breccia - anorthositic norite-gabbro) - 0.366g/2024-06-01-16.32.50-ZS-DMap (1).jpg
Photos/Achondrites/Lunar/melt breccia/Adrar 013 (Lunar melt breccia - anorthositic norite-gabbro) - 0.366g/2024-06-01-16.31.56-ZS-retouched.jpg
Photos/Achondrites/Lunar/melt breccia/Adrar 013 (Lunar melt breccia - anorthositic norite-gabbro) - 0.366g/info.txt
```

