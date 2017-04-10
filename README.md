# Jiffy
## Search, and ye shall be answered


Jiffy caches information about files and folders on your hard disk to allow fast lookups. My attempt to figure out the fastest cross-platform search tool Python can provide.


### Requirements: 
- scandir is currently required on Python < 3.5 (Part of the standard library as of 3.5):
`pip install scandir`

- Python 3 ditched hashdb, so, on Windows, it only supports dumbdbm. dumbdbm sucks, so Jiffy tries to use a better Python based key-value storage on Py3/Win - the very nice [semidbm](https://github.com/jamesls/semidbm/tree/master/semidbm):
`pip install semidbm`


### Tested on: 
Windows 8.1/ 10, Linux Mint 18.1 Under: Python 2.7/3.5


### Other Platforms:
Jiffy uses generic standard library Python functions for almost all its operations (except opening a file with its default app). I suspect/hope it runs almost anywhere Python can be installed. Feedback is welcome.


### Usage:
-	Hit F5 to generate the database for the first time. Update it with F5.
-	Type in words, parts of words, extensions etc. separated by spaces for lookups.
-	Double click on press Enter after choosing the desired file to open it.
-	You can adjust the font size with Ctrl + +/- , or Ctrl + scrollwheel.
-	Alt-F4 to exit.

### Windows Demo:
![](https://github.com/h5rdly/Jiffy/blob/master/WinDemo.gif)

### To do:
-	Filetype icons on the various platforms. 
-	Unicode support (check)
-	Use the USN journal for updates on Windows/NTFS
-	Faster dictionary lookups 
-	The BIG feature
-	Add a slicker GUI with Kivy, tkinter as a backfall
-	Check LMDB as an alternative storage.
-	Figure out how to mark out lines on Github
     

### Call for action:
-	Lookups take a few seconds for sparse results, I would like them to have real time speed. Feel free to pitch in or offer any assistance.
-	Ideas for speeding up the database creation, preferably in a cross-platfrom way, are quite welcome. 


