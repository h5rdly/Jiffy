# coding: utf-8                          #seems to be useless
from __future__ import print_function    #for testing

import os, sys
from time import time, ctime, sleep
from collections import namedtuple

try:
    #Better subprocess for python2
    from subprocess32 import Popen, PIPE  
except:
    from subprocess import Popen, PIPE

try:
    import _thread as thread
    from queue import Queue
except:
    import thread
    from Queue import Queue
    
#Scanning the filesystem		
try:
    from os import scandir        #on Python 3.5+    
except:
    try:
        from scandir import scandir
    except:
        #If opting to add and implement shitpa listdir as a last resort
        pass

#Setting up the dbm to be used
try:
    #Python 2
    import anydbm as dbm   #With some luck we get bsddb/dbhash
except:
    #Python 3
    if 'win' not in sys.platform:
        import dbm   #We can make do with gdbm/ndbm
    else:
        #Python 3 on Windows, trying to avoid dumbdbm
        try:
            import semidbm as dbm
        except:
            import dbm  #All the whiz
finally:
    #For checking which built-in dbm backend is in use 
    try:
        from dbm import whichdb
    except:
         from whichdb import whichdb   
        
#GUI - optional Kivy GUI, original (backfall) Tkinter GUI 
KIVY_GUI=False  #modify when testing/ready to use kivy

if KIVY_GUI:
    try:              
        from kivy.app import App
        from kivy.lang import Builder
        from kivy.uix.widget import Widget
        
        #from kivy.core.window import Window, WindowBase
        from kivy.properties import ObjectProperty
        from kivy.clock import Clock
        from kivy.config import Config  #to start maximized
        
        from kivy.properties import BooleanProperty
        from kivy.uix.behaviors import FocusBehavior
        
        from kivy.uix.label import Label

        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput

        from kivy.uix.recycleview import RecycleView
        from kivy.uix.recycleview.views import RecycleDataViewBehavior
        from kivy.uix.recycleview.layout import LayoutSelectionBehavior
        from kivy.uix.recycleboxlayout import RecycleBoxLayout
    except:
        KIVY_GUI=False
    else:
        #This import on itself pops a kivy window, as does importing Window 
        from kivy.core import window   

else:
    # Eventually, I would like to allow switching between the GUI's, with varying
    # features on each one
    try:              
        from tkinter import Entry, StringVar, Message, Frame, PhotoImage, mainloop, INSERT    
        from tkinter.ttk import Treeview, Style
        from tkinter.font import Font 
    except:
        from Tkinter import Entry, StringVar, Message, Frame, PhotoImage, mainloop, INSERT
        from ttk import Treeview, Style
        from tkFont import Font

#NTFS snooping, getting admin on Windows, DPI workarounds, Filetype icons
from ctypes import *

ENC='utf-8'
DB, CONF='Jiffy_DB  ', 'Jiffy_Config'

##--Testing related-------------------------------------------------------------

class Checks():
    
    testing=1          
    
    #Modify to 1 after 'else' to activate check
    
    #--DriveIndex / GUI
    recursion_stats=   0 if not testing else 1     
    findex_syncing=    0 if not testing else 1
    is_dpi_scale=      0 if not testing else 0
    is_query_passed=   0 if not testing else 0  # what did the search thread recieve
    is_result_batch=   0 if not testing else 0  # results put on queue by search thread
    is_query_sent=     0 if not testing else 0  # was query sent by tk gui
    query_db_send=     0 if not testing else 0  # what was sent to the thread by db_send
    is_batch_recieved= 0 if not testing else 0  # is result batch recieved by tk gui  
    is_result_parsed=  0 if not testing else 1  # 
    is_tk_get_name =   0 if not testing else 1
    
    #--UpdateViaUsn
    is_entries_from_fsutil=   0 if not testing else 1     
    findex_syncing=           0 if not testing else 0
    full_path_parsing=        0 if not testing else 0
    did_generate_entries=     0 if not testing else 0
    
if Checks.testing:
    import pdir, fire
    from pympler.asizeof import asizeof

    def size(object):
        '''getting dictionary sizes in Mb'''
    
        return asizeof(object)/1024/1024
        
##--Some helper functions-------------------------------------------------------

def FloatPrecision(num, precision):
    '''If i opt for losing excess precision of floats in advance'''

    floater=int((num-int(num))*(10**precision))/(10**precision+0.0)
    return int(num)+floater        


#-------------------------------------------------------------------------------  
##--Classes---------------Classes for my precious-------------------------------
#-------------------------------------------------------------------------------
''' Platform():     plat, split_token
                    start_func(), scale_display(), get_updates()- not implemented
                     
    Drives():       drives
    
    _UpdateViaUsn(): Drive.drives, Drive.ntfs_drives, start_usns
                    create_journals(), _get_next_max_usn(), get_changed()
                    
    DriveIndex():   db, conf, drives, findex, query_queue, result_queue
                    generate_db(), is_db_generated(), query_db(), get_result_batch()
                    
    SearchBox(Frame): Tkinter GUI
    
    KivySearchBox(BoxLayout): Kivy GUI                    
'''                       
                       
class _UpdateViaUsn():
    '''On Windows systems with NTFS drives/partitions, it is possible to get
    info on changes to the filesystem from the USN journal. Admin privilege is
    required.
    
    Current implementation uses the fsutil tool that comes with Windows, as I
    didn't want to tinker with the API calls quite yet.
    '''

    def __init__(self, start_usns=None, ntfs_drives=None):
        self.Drives=Drives()
        self.ntfs_drives=ntfs_drives if ntfs_drives else self.Drives.ntfs_drives
        
        self.start_usns=start_usns if start_usns else 0   
    
    
    def create_journals(self, max_size, delta):
        '''create usn journals to track changes for chosen drives if such don't
        already exist'''
        
        for drive in self.ntfs_drives:
            #check if a journal exists, else:
            
            Popen(('fsutil', 'usn', 'createjournal', max_size, delta, drive), stdout=PIPE).communicate()[0]
        
        #experiment
    

    def get_next_max_usn(self, drive):
        '''On windows/ntfs this is 'next usn' - the usn index to latest change made. 
        Also returns max_usn since enumdata requires an upper boundary. Not needed
        when using readjournal.
        fsutil usn queryjournal result: 
        
        Usn Journal ID   : 0x01d2a26e17dbc5e8
        First Usn        : 0x0000000000000000
        Next Usn         : 0x0000000000acddf0     <--- index #2
        Lowest Valid Usn : 0x0000000000000000
        Max Usn          : 0x7fffffffffff0000     <--- index #4
        .
        .                                      '''
        
        if 'win' in sys.platform and drive == '/':
            ''' using '/' on windows works for scandir but not for fsutil'''
            drive='c:'
        else:
            # Removing trailing slashes
            drive=drive.split(':')[0]+':'  
        
        journal_specs=Popen(('fsutil', 'usn', 'queryjournal', drive), stdout=PIPE).communicate()[0].split('\r\n')
        next_usn=journal_specs[2].split(': ')[1]
        max_usn=journal_specs[4].split(': ')[1]
        
        return next_usn, max_usn         #int(next_usn, 16), int(max_usn, 16)
        
    
    def get_changed(self, usn_dict):  #needs to be in a thread or add wrapper
        '''Return a set of full paths to files/folders that were added, altered
        or deleted, and another set of renamed items. This includes pre-renamed names and names to deleted entries.
        Retrieved via fsutil's usn readjournal and file queryfilenamebyid
        '''
        
        #self.drive_usns=self._get_usn_range()
        self.renamed=set()                   #not in use
        self.new_modified_deleted=set()
        #for moved enrties, fsutil does not supply and old location record
        self.scan_and_remove=set()    
                                       
        for drive in usn_dict:
            #current, max=self.drive_usns[drive].split() #retrieveing usn range as strings
            #startusn='startusn='+str(current)
            startusn=str(usn_dict[drive])
            print (drive, startusn)
            #getting max_usn separately for easier switching/cooperation with readjournal
            nextusn, maxusn= self.get_next_max_usn(drive)
            usn_entries=Popen(('fsutil', 'usn', 'enumdata', 1, startusn, maxusn, drive), stdout=PIPE).communicate()[0]
            #usn_entries=Popen(('fsutil', 'usn', 'readjournal', drive, 'startusn='+startusn), stdout=PIPE).communicate()[0]
            usn_entries=usn_entries.split('\r\n\r\n')
            if Checks.did_generate_entries:
                print(usn_entries)
            usn_entries.pop()           #last one is an empty string
            
            #------------------------------------------------------------------
            #--Previous version using readjournal, not compatible with unupdated 
            # Win 7 machines----------------------------------------------------
            
            #readjournal returns the following format:
            '''
            USN Journal ID    : 0x01d2a26e17dbc5e8
            First USN         : 0
            Next USN          : 11116672
            Start USN         : 11116416
            Min major version : Supported=2, requested=2
            Max major version : Supported=4, requested=4

            Usn               : 11116416
            File name         : aa8
            File name length  : 6
            Reason            : 0x00001000: Rename: old name
            Time stamp        : 16-May-17 08:12:49
            File attributes   : 0x00000010: Directory
            File ID           : 000000000000000000020000000013a1
            Parent file ID    : 00000000000000000005000000000005
            Source info       : 0x00000000: *NONE*
            Security ID       : 0
            Major version     : 3
            Minor version     : 0
            Record length     : 88
            .
            .
            '''
            
            # Getting ID of the last change from readjournal's first entry. Will
            # be the next start_usn
            '''
            'USN Journal ID    ',
             ' 0x01d2a26e17dbc5e8',
             'First USN         ',
             ' 0',
             'Next USN          ',
             ' 11116672',
             'Start USN         ',
             ' 11116416','''
            
            #last_usn=usn_entries[0].replace('\r\n', ':').split(':')[5]
            #print('last usn: ', last_usn) 
            
            #with split('\r\n')  currently used
            '''['Usn               : 11325792',
            'File name         : aa',              ---> index #1
            'File name length  : 4',
            'Reason            : 0x00001000: Rename: old name',  --->index #3
            'Time stamp        : 23-May-17 07:47:07',
            'File attributes   : 0x00000010: Directory',
            'File ID           : 000000000000000000020000000013a1', -->index #6
            'Parent file ID    : 00000000000000000005000000000005',
            'Source info       : 0x00000000: *NONE*',
            'Security ID       : 0',
            'Major version     : 3',
            'Minor version     : 0',
            'Record length     : 80']   '''
                
            #-------------------------------------------------------------------
            #--Using enumdata in new version, no "reason" field so checking for
            # renames is on us--------------------------------------------------
            
            for entry in usn_entries:
            
                entry_fields=entry.split('\r\n')
                #An entry after .split('\r\n')
                '''['File Ref#       : 0x00000000000000000004000000001f57', <--index #0
                'ParentFile Ref# : 0x00000000000000000035000000002138',
                'Usn             : 0x0000000000ae99a8',
                'SecurityId      : 0x00000000',
                'Reason          : 0x00000000',
                'Name (044)      : doc.doc']'''
                 
                #Extracting ID from a listing such as above 
                file_id=entry_fields[0].split(' : ')[1]  
                
                '''Used by readjournal, currently not in use
                file_id='0x'+entry_fields[6].split(' : ')[1]
                reason=int(entry_fields[3].split(': ')[1], 16)'''
                    
                try:
                    full_path=Popen(('fsutil', 'file', 'queryfilenamebyid', drive, file_id), stdout=PIPE).communicate()[0]
                except:
                    # Some events retrieved by fsutil's enumdata weren't file 
                    # related.
                    print('poo')
                    pass
                else:
                    '''  "A random link name to this file is \\?\E:\aa\bobo"
                    note no trailing slashes on folder names '''
                    
                    #This gets us the full path
                    full_path=full_path.replace('?\\', '\r\n').split('\r\n')[1]
                    if Checks.full_path_parsing:
                        print (full_path)
                    
                    ''' separating entries to renamed and non renamed,old named
                    entries should be removed and new named folders rescanned.'''
                    
                    ''' Used by readjournal, not committed, to be removed in a future commit
                    REN_OLD=0x00001000      #'Rename: old name'
                    REN_NEW=0x00002000      #'Rename: new name'
                    DEL_CLOSE=0x80000200    #'File delete | Close'
                    
                    if reason ==  REN_OLD:
                        # Those entries hold no longer existing names
                        old_name=entry_items[1].split(' : ')[1]
                        path, new_name=full_path.rsplit('\\', 1)
                        if not old_name == new_name:  #moving in same partition is almost same as renaming as far as usn
                            # if they are the same, this was a same drive moving
                            # can't get old path from fsutil for moving actions
                            full_path=path+'\\'+old_name
                            self.renamed.add(full_path)
                    else:
                        self.new_modified_deleted.add(full_path)'''
                    
            self.new_modified_deleted.add(full_path)
            if Checks.is_entries_from_fsutil:
                print ('entries generated for', drive) 
        
        ##Note
        '''Until I find a better way, every item is a suspect of being a moved
        item- need to compare keys to all items, stat() any findings and remove non existing.'''
        
        #update config with last_usn
        return self.new_modified_deleted, self.renamed #empty for current method      #new_altered_removed


class Platform():
    '''platform specific trinkets'''
        
    def __init__(self, platform=sys.platform):
        self.plat=platform
        self.split_token= '\\' if 'win' in self.plat else '/'
        self.Update=_UpdateViaUsn if 'win' in self.plat else None #Windows auto-update
        
    def start_func(self):
        '''Returns a platform based method to handle double-clicks/Enter presses
        for opening files with their default app, or opening folders in the 
        default file tool. '''

        if 'win' in self.plat:
            func=os.startfile     #An API call also an option
        else:   
            #Linux, FreeBSD, OpenBSD, MacOSX
            open_command='open' if 'darwin' in self.plat else 'xdg-open'   #os.name=='posix'
            
            func=lambda filepath: Popen((open_command, filepath))
                
        return func    
    
    def scale_display(self):
        '''Take care of display related issues. On Windows - anounce the app
        as DPI aware'''
    
        if 'win' in sys.platform:
            try:
                #try for DPI awareness  
                windll.shcore.SetProcessDpiAwareness(1) 
                if Checks.is_dpi_scale:
                    print('great DPI success')
                #windll.shcore.GetDpiForMonitor()
            except:
                #well, shit.
                if Checks.is_dpi_scale:
                    print ('no dpi scaling')
                else: 
                    pass 
    
    def get_updates(self, start=None, end=None):
        '''use internal platform specific function aggregates to return
        a set of modified entries'''
        
        #save last update time/usn ranges in a config dbm, here or in caller?
        pass


class Drives():
    '''To hold any drive related information'''
    
    def __init__(self):
        self.drive_list=self._get_drives()
        if 'win' in sys.platform:
            self.ntfs_drives=self._get_ntfs_drives_win()
            
    def _get_drives(self):
        '''Generate a list of drives for the database function. On linux - 
        just '/'.  On Windows, '/' and 'C:/' represent the same drive, but
        trying to walk 'C:/' only traversed very few specific dirs in my attempts  
        '''
    
        self.exists=os.path.exists  #sp with some useful function that gets removable drive info as well?
        self.drives=[u'/']        
        if 'win' in sys.platform:
            self.drives.extend((chr(a)+ u':\\' for a in range(ord('A'), ord('Z')) if self.exists(chr(a)+':')))
            
            #Removing redundant 'C:' on Windows
            try:
                self.drives.remove(u'C:\\')  
            except ValueError:            
                pass                   
       
        return self.drives   
    
    def _get_ntfs_drives_win(self):
        '''Return list of ntfs drives using fsutil fsinfo's volumeinfo. 
        Result after slpit('\r\n'):
        
        ['Volume Name : Le Shwa',
         'Volume Serial Number : 0xd4d56c89',
         'Max Component Length : 255',
         'File System Name : NTFS',     --> index #3 --> split(':') --> index #1 
         'Is ReadWrite',....       ]'''
        
        ntfs_drives=[]
        win_drive_list=(chr(a)+ u':' for a in range(ord('A'), ord('Z')) if self.exists(chr(a)+':'))
        for drive in self.drives:
            volume_info=Popen(('fsutil', 'fsinfo', 'volumeInfo', drive), stdout=PIPE).communicate()[0]
            file_system=volume_info.split('\r\n')[3].split(' : ')[1]
            if file_system=='NTFS':
                ntfs_drives.append(drive)
            
        return ntfs_drives


class DriveIndex():
    '''functions for GUI use:
    
    - generate_db() - pop a thread for generating a new file index as a dictionary
    - update_locations(locations)- pop a thread for rescanning an updating specific
      directories
    - (file_index, unsearched_dirs) is_db_generated() - return True if new index is ready
    - get_changes() - update findex with entries recieved by the platform 
                       specific update service via Update()
                        
    - query_db(query) - pass a query to the search thread, empty current results
                      from result queue
    - *results* get_result_batch() - Retruns a batch(es?) of results if available 
    '''
     
    def __init__(self, db=DB, conf=CONF):
        
        self.Drives=Drives()
        self.Plat=Platform()
        self.split_token=self.Plat.split_token
        self.drives=self.Drives.drives
        if 'win' in sys.platform:
            self.ntfs_drives=self.Drives.ntfs_drives
            self.Update=self.Plat.Update()
        
        self.db=db
        self.conf=conf
        
        self.findex=dbm.open(self.db, 'c')
        self.config=dbm.open(self.conf, 'c')
        
        #NTS Let the GUI work it out
        '''if not self.config:
            #No config file, generating a default one
            self._default_config=dict.fromkeys(self.ntfs_drives)
            for key in self._default_config:
                key=key.encode(ENC)
                self.config[key]=self._default_config[key]
            self.config.sync()'''
            
        #To interact with _make_search()
        self.query_queue, self.result_queue= Queue(), Queue()
        
        thread.start_new_thread(self._make_search, ())
        '''
        if self.findex and self.config and self.ntfs_drives: #change to a thread
            for drive in self.ntfs_drives:
                try:
                    update_checkpoint=self.Update.get_next_max_usn(drive)[0]
                    modified, renamed = self.Update.get_changed(self.config[drive]):
                 except:
                    print('error updating or corrupt config file')
                 else:
                    self.sync_changes(modified, renamed)
                    self.config[location]=update_checkpoint'''
                    
                    
        stat=os.stat
        
   
    def _pretty_size_date(self, size, date):
        '''Return formatted size and date strings'''
            
        Gb_Tb_PRECISION=2    
        
        #Size
        for size_unit in u'BKMGT':
            if size < 1024:
                break
            size/=1024.      
        
        if size_unit == u'G' or size_unit == u'T':
           #cut excess precision
           size=FloatPrecision(size, Gb_Tb_PRECISION) 
        else:  
            #M, K, B
            size=int(size) if size-int(size)<0.5 else int(size+1)
                    
        fsize= str(size)+' '+ size_unit + u''
        
        #Date
        '''ctime style: 'Mon Oct 26 16:33:26 2015'   
        desired style: '26-Oct-15|16:33' '''  
        
        try:
            # + works (~x10) faster than join() in my timeits
            fdate= date[2] + u'-' + date[1] + u'-' + date[4][2:] + u' | ' + date[3][:-3] +u'' #change to %
        except:
            # In case st_mtime returned a negative timestamp due to a rare  
            # (I hope) oddity on Windows/Python3.5 (None passed)
            fdate='Error getting date'
        
        return fsize, fdate
    
    
    def _size_from_key(self, key):
       '''Getting size of a deleted entry from its string representation in the 
       index. Keys are of type: 
       'C:\fileath\filename * 24 M * [date]' -->split('*') --> index #1
       '''
       
       location_in_key=1  
       power={'B': 0, 'K': 1, 'M': 2, 'G': 3, 'T': 4} 
       
       # *24 M* --> size=24, units='M'
       size, units=key.decode(ENC).split(u'*')[location_in_key].split()
       
       long_size=1024**power[units] * long(size)
       
       return long_size
    
    
    def _get_inode_via_scandir(self, filepath):
        '''stat() on python<3.3 returns empty st_ino, in which case we scandir
        the parent folder, as scandir does provide inodes'''
        
        parent_dir, name=filepath.rsplit(self.split_token, 1)
        parent_contents=scandir(parent_dir)
        for item in parent_contents:
            if item.name==name:
                return item.inode()
        #return [item for item in parent_contents if item.name==name].pop()
    

    def _recursive_create_dict(self, locations=None):  
        '''Recursive implementation of generating the file dictionary. A stack 
        based implementation is in stash.py. I tried to avoid function fragmentation
        for the speedup, so this one is a bit longer'''
        
        self.fdict={}
        self.fdict['**']=''     # "Null key" referral, currently not in use
        self.unsearched=[]
        self.is_generated=False
        if not locations:
            self.locations=self.drives
            self.brand_new=True
        else:
            self.locations=locations
            self.brand_new=False
        
        self.generation_time=time()  # for testing / displaying
        
        def recursive_add(top):   
            '''Cheese - recursively scan a folder or drive("location"), 
            updating the dictionary and returning the total size of the  location'''
            
            #Prepping dir contents
            try:
                contents=scandir(top)  #scandir the path
            except OSError:
                self.unsearched.append(top)
                return 0      # no size for you. 
            
            #Getting 'C:\' back as the prefix on Windows
            if 'win' in sys.platform and top[0]==u'/':
                #Get the boys back home
                top=u'C:\\'+top[1:]     
            
            #Will be calculated recursively
            top_size=0    
            
            #Iterating over dir contents
            for scandir_item in contents:
                if scandir_item.is_symlink():    
                    #symlinks make recursion sad
                    continue                     #add symlink treatment later
                    
                try:
                    date=ctime(scandir_item.stat().st_mtime).split() 
                except:
                    #On Python 3.5, Win8.1, had an issue with a negative time on 
                    #st_mtime. Substituted for an error notification when parsed
                    date=None 
                    
                if not scandir_item.is_dir():
                    #File specific treatment
                    fname='F'+ '*' + scandir_item.name
                    size=scandir_item.stat().st_size
                else:     
                    if not scandir_item.is_symlink():   #remove one of the checks 
                        size=recursive_add(scandir_item.path)  #Aww shit!   
                    
                    fname='D'+ '*' + '[' + scandir_item.name + ']'
                    
                # Saving inodes to be able to find and remove old versions of
                # renamed/moved entries
                try:
                    finode=str(scandir_item.inode())
                except:
                    #error on windows SystemData folder with scandir/py2.7
                    finode='0'
                finally:
                    # Attaching inodes increases db size significantly, but 
                    # using fsutil i cannot track old paths of moved files,  
                    # will implement a compressed dbm in the future 
                    fname=finode + '*' + fname
                    
                top_size+= size
                       
                fsize, fdate=self._pretty_size_date(size, date)
                fpath=top + u''
                
                #worked faster than join() in my attempts
                key=fname + '*' +fsize + '*' +fdate + u''
                value= fpath
                if key in self.fdict:
                    '''contingency in case two  same named same sized files 
                    were modified in the same minute'''      
                    #self.key=self.fname + '[1]' + ' * ' +self.fsize + ' * ' +self.fdate + u''
                    pass
                self.fdict[key.encode(ENC)]=value.encode(ENC)  
            
            return top_size    
            
        #Taking up the scan
        for location in self.locations: 
            '''Recursing all drives/locations'''
            
            if location in self.drives:
                if 'win' in sys.platform and location in self.ntfs_drives + ['/']: #remove duplicity with 'c:' / '/'
                    ''' On windows, save drive's "next usn" to the config file 
                    before scanning. This will be this drive's starting point of 
                    the next auto-update'''
                    self.config[location.encode(ENC)]=self.Update.get_next_max_usn(location)[0]
                    pass
                    
            self.gtime=time()
            recursive_add(location)
            
            if Checks.recursion_stats:
                self.gtime=time()-self.gtime
                print ("Done recursing on location ", location)
                print("Time: ", self.gtime)
    
        # _make_search() thread will close itself upon recieveng True for
        # database syncing
         
        self.query_queue.put(True)
        
        #Deleting relevant parts of the dbm
        if self.brand_new:
            #All drives were rescanned, empty the dbm
            try:
                # some dbms don't have a clear() method. fu** me, right?
                self.findex.close()
                self.findex=dbm.open(self.db, 'n')
            except:
                # dumbdbm does not clear out the dbm when reopening with 'n' 
                self.findex.clear()
        else:
            #Remove items internal to the location list from dbm  #boatshow
            to_delete=(key for key in self.findex for location in locations if location in self.findex[key])   
            map(lambda key: self.findex.pop(key), to_delete)
            
            #
            '''for key in self.findex:
                for location in self.locations:
                    if location in self.findex[key]:
                        #delete entries whose path contains location
                        del dict[key]'''
                 
        #Persisting the new index
        if whichdb(self.db)==('dbhash'):
            '''For dumbdbm, this jams the app, as does manual updating. 
            It's not dumb, it's simply not worthy'''
            self.findex.update(self.fdict)
        else: 
            for key in self.fdict:
                self.findex[key]=self.fdict[key]
        if Checks.findex_syncing:
            print ('findex is updated')
        
        #Save new database
        self.findex.sync()
        if Checks.findex_syncing:
            print ('findex synced')
                
        #We can now resume searching
        thread.start_new_thread(self._make_search, ())
        
        #Inform of completion 
        self.is_generated=True
        
        #Cleaning up
        self.fdict.clear()
        self.fdict=None        
        
        self.generation_time=time()-self.generation_time
        if Checks.recursion_stats:        
            print (self.generation_time)
        
        
    def _make_search(self):
        '''Attempt at circumventing StopIteration(), did not see speed advantage'''
        
        self.results_per_batch=50
        
        if whichdb(self.db) in {'dbm.gnu', 'gdbm', 'dbm.ndbm', 'dbm'}:
            '''iteration is  not implemented for gdbm and (n)dbm, forced to
            pop the keys out in advance for "for key in fdict:" ''' 
            self.keys=self.findex.keys()
        
        #Extracting keys to a set, make this optional as the new "scorch mode"
        if 'win' in sys.platform:  #NTS Did not see speed improvement in Linux
            try:
                self.keys=frozenset(self.findex)
            except:
                self.keys=frozenset(self.findex.keys())
            
        self.search_list=None 
        self.separator='*'.encode(ENC)   #Python 3, yaaay

        while True: 
            self.query=None
            while not self.query_queue.empty():        
                #more items may get in (or not?) while condition is checked
                self.query=self.query_queue.get()
                
            try:    
                self.search_list=self.query.lower().encode(ENC).split()
                if Checks.is_query_passed:
                    print ('is_query_passed: ', self.search_list)
            except:
                if self.query:
                    # True is passed when a new database has been generated
                    # A new instance of _make_search will be opened
                    break
                    
                else:
                    #No new queries
                    sleep(0.1)
                    continue
            else:
                self.is_new_query=True
            
            self.result_batch=[] 
            name_pos=2      # inode * fof * name * size * date
            for key in self.keys: 
                filename=key.split(self.separator)[name_pos].lower()
                '''_all=all
                if _all(token in filename for token in search_list):
                        result_batch.append(key)'''
                #Add key if matching    
                for token in self.search_list:
                    if not token in filename:
                        break
                #If loop hasn't ended abruptly
                else:
                    '''Added existence check via stat() after adding USN auto 
                    updates, as I am yet to figure out how to get old paths of 
                    moved files/folders. Alternatively, every suspicious file
                    or folder nemae can be looked up and stat()ed on updating 
                    '''
                    '''fof=key.split(self.separator)[0]
                    #'[', ']' take 1 byte unicode representation
                    real_name=filename[1:-1] if 'D' in fof else filename
                    does_exist=self.findex[key] + self.split_token.encode(ENC) + filename
                    
                    try:
                        os.stat(does_exist.decode(ENC))
                    except:
                        print ('stat failed on ', does_exist)
                        #print(key.decode(ENC))
                        #A dead key
                        #del self.findex[key]'''
                        
                    #add 'else:' if all good. check with a move/rename when autoupdate
                    #is up
                     
                    self.result_batch.append(key)
                
                #Time to send off a batch?    
                if len(self.result_batch)>=self.results_per_batch: 
                    self.result_queue.put((self.result_batch, self.is_new_query))
                    if Checks.is_result_batch: 
                        print(self.result_batch, len(self.result_batch))
                        print('is_result_batch: results on queue')
                    self.result_batch=[]
                    #print (len(self.result_batch))
                    self.is_new_query=False
                    sleep(0.1)
                    if not self.query_queue.empty(): 
                        break
         
            #If the for loop ended naturally, with some batch<50        
            self.result_queue.put((self.result_batch, self.is_new_query))    
        
    def _sync_changes(self, modified, renamed):
        '''* find if an older key with the same inode exists:
        - if so and names are same - remove. 
        - if so, names are not same and folder- remove entry and all entries 
        where this folder is in the path. scandir new folder for updated entries
        if so, names not same and file - remove entry
        
        * if a file - get '''
       
        self.dir_size_counter={}
        isdir=os.path.isdir
        
        def remove_entry(key, path, entry=None): #does not consider size of non deleted (modified) item
            ''' Removing an entry from the index, propagating the size change
            to all parent directory tree. Insert updated entry if available'''
            
            #Pulls out size as ['24', 'M'] and returns a Long value
            deleted_size=self._size_from_key(key)  
            while path and path not in self.drives:
                try:
                    #Assuming massive deleting will involve many files per folder
                    self.dir_size_counter[path]-=deleted_size
                except:
                    self.dir_size_counter[path]=-deleted_size
                
                path=path.rsplit(self.split_token, 1)[0]
                
            #Removing entry from index
            del self.findex[key]
            
        for entry in modified:        #renamed_deleted
            # Extracting filename and path to parent dir from the full path
            path, name=entry.rsplit(self.split_token, 1)
            #name=entry.split(SPLIT_TOKEN)[-1]
            if isdir(enrty):  
                #False for no longer existing entries as well as non folders
                name='['+name+']'
            name=name.encode(ENC)
            path=path.encode(ENC)    
            #path=entry[:-len(name)].encode(ENC)
            
            separator='*'.encode(ENC)
            
            try:
                entry_stats=stat(entry)
            except:
                '''Unable to retrieve stats for file or folder, presumably due to it
                being deleted or moved: WindowsError,
                no inode, searching for exact match to remove entry and update
                parent dir size'''
                for key in self.findex: #should do this for all entries
                    if name==key.split(separator)[2] and path==self.findex[key]: #inode, fof, name, size, date
                        #Saving size to update parent folder's size value
                        
                        deleted_size=self._size_from_key(key)  #Pulls out size as ['24', 'M']
                        try:
                            #Assuming massive deleting will involve many files per folder
                            dir_size_counter[path]-=deleted_size
                        except:
                            dir_size_counter[path]=-deleted_size
                        finally:
                            #Removing entry from index
                            del self.findex[key]
                
                '''if name in deleted_entries:
                    deleted_entries[name].append(path)
                else:
                    deleted_entries[name]=[path]'''
            
            else:
                #We have entry_stats, this is an existing(modified) file or folder 
                size, date, inode=entry_stats.st_size, entry_stats.st_mtime, entry_stats.st_ino
                size, date=self._pretty_size_date(size, date) 
                inode=inode if inode else self._get_inode_via_scandir(entry)  
                inode=str(inode).encode(ENC)
                for key in self.findex: 
                    if inode==key.split(separator)[0]:     #inode, fof, name, size, date
                         if name==key.split(separator)[2]: 
                            '''Name and inode are the same, this was a simple 
                            modification as far as the file index'''
                           
                           
                            
                         else:   
                            '''Name and inode are not the same, file/folder was 
                            renamed or moved in the same drive'''
                            
                            
                
                if isdir(enrty):    
                    #check if action was renaming
                    pass
         
    
    def _get_changes(self):
    
        '''for drive in self.ntfs_drives:
            try:
                modified, renamed = self.Update.get_changed(self.config[drive]):
             except:
                print('error updating or corrupt config file')
             else:
                self._sync_changes(modified, renamed)  '''
        pass
    
    
    def generate_db(self):
        '''Pop a thread on _recursive_create_dict with a queue for the 
        resulting db'''
          
        thread.start_new_thread(self._recursive_create_dict, ())
        
        
    def update_locations(self, locations):
        '''Rescan specific folders and update self.findex. Does not update
        the folder entry itself, only what's inside'''
        
        thread.start_new_thread(self._recursive_create_dict, (locations))
        
        
    def is_db_generated(self):
        '''To be called by GUI periodically after calling generate_db()'''
        
        try:
            self.is_generated #is this relevant when _recursive() is in a different thread?
        except:
            #In case is_db_generated() is called before generate_db()
            pass
        else:
            if self.is_generated:
                self.is_generated=False
                
                return True
            
        # deprecated method using a queue, we be classy now
        '''if not self.dbgen_queue.empty():
            return self.dbgen_queue.get()
        else:
            return None'''
        
        
    def query_db(self, query):
        '''Pass a new query from the GUI and empty result list'''
        
        self.query_queue.put(query)
        if Checks.query_db_send:
            print ('query_db_send: ', query)
        while not self.result_queue.empty():  #should I?
            #Empty previous results 
            self.result_queue.get()
            
        
    def get_result_batch(self):
        '''Send the GUI a batch of results if available '''
        
        self.results=[]
        while not self.result_queue.empty():
            self.results.append(self.result_queue.get())
        
        return self.results  #can return only last result, sfsg, see if issues
        
        
    def get_changes(self):
        thread.start_new_thread(self._get_changes, ())
        
#------------Not in use---------------------------------------------------------
class HelperFunctions():           
     #Decided not to bundle them up, not in use
    '''some assisting functions'''    
   
    @staticmethod
    def float_precision(num, precision):
        '''if i opt for losing excess precision of floats in advance'''

        floater=int((num-int(num))*(10**precision))/(10**precision+0.0)
        return int(num)+floater
#-/--------Not in use-----------------------------------------------------------


#-------------------------------------------------------------------------------
##--Tkinter GUI-----------------------------------------------------------------     
#-------------------------------------------------------------------------------        
class SearchBox(Frame):
    '''A Treeview widget on top, Entry on bottom, interacting with a DriveIndex
    instance '''
   
    def __init__(self, parent=None, db=DB, conf=CONF):
        Frame.__init__(self, parent)
        #self.Checks=Checks()
        self.index=DriveIndex(db, conf)
        self.Plat=Platform()
        self.split_token=self.Plat.split_token
        #will hold the query to be processed
        self.query=None 
        
        self.start= self.Plat.start_func()  #platform dependent double-click response
            
        self.results=iter(())   #initiating query results as an empty generator
        self.total_width=self.winfo_screenwidth() #to adjust column widths relative to screen size
        
        #keystroke indicator
        self.counter=0
        
        ##--Graphics, StringVar-------------------------------------------------
        #-----------------------------------------------------------------------
        #--Search Results panel at top
        self.panel=Treeview(columns=('Path', 'Size', 'Date'))
        self.panel.pack(expand=True, fill='both')
        self.panel.heading('#0', text='Name')
        self.panel.heading(0, text='Path')
        self.panel.heading(1, text='Size')
        self.panel.heading(2, text='Date Modified')
        
        #--Starting geometry of the search panel
        try:   #start maximized
            self.panel.master.attributes('-zoomed', 1)
        except:
            self.panel.master.state('zoomed') 
         
        self.panel_width=self.panel.winfo_width()
        #Name - 2/5-----Path - 2/5-----Size -1/25-----Date -4/25
        # '#0' is the 'Name' column          
        self.panel.column('#0', width=int(self.total_width*0.4))      
        self.panel.column('Path', width=int(self.total_width*0.4))
        self.panel.column('Size', width=int(self.total_width*0.06))
        self.panel.column('Date', width=int(self.total_width*0.14))
        
        #--Panel font, style
        self.font=Font(family='Helvetica', size=11)
        '''TkDefaultFont - {'family': 'Segoe UI',  'overstrike': 0, 'size': 9, 
                       'slant': 'roman', 'underline': 0, 'weight': normal'}'''       
        self.style=Style()
        
        #linespace - adjust the row height to the font, doesn't happen on its own in tkinter
        self.style.configure('SearchBox.Treeview', font=self.font, rowheight=self.font.metrics('linespace'))     
        self.panel.config(style='SearchBox.Treeview')
        
        #alternating background colors
        self.panel.tag_configure('color1', background='gray85') #, foreground='white')
        self.panel.tag_configure('color2', background='gray90') #, foreground='white')       
        #'dark sea green', 'wheat3', 'black'
             
        #--App title and icon, currently transparent
        self.panel.master.title('Jiffy')
        self.icon=PhotoImage(height=16, width=16)
        self.icon.blank()  #transparent icon, works on all but Py35/Win
        
        #loading the transparent icon. black on Py35/Win
        try:
            self.master.wm_iconphoto('True', self.icon)
        except:    
            #For some reason this jammed Python 3.5 with Tk 8.6 on Windows
            self.tk.call('wm', 'iconphoto', self.master._w, self.icon)
        
        #--A string variable to monitor input to the Entry box
        self.entry_var=StringVar()
        #self.entry_var.set('Type to search. [F5 - Refresh Database]. [F12 - Scorch Mode]') 
        # [Ctrl-O - Options]. [Ctrl-I - Info]  
        self.entry_var.trace('w', self.update_query)        
         
        #--Entry line on the bottom
        self.entry_box=Entry(textvariable=self.entry_var)
        #keep it as a single line on all window sizes  
        self.entry_box.pack(side='bottom', fill='x')     
        
        
        ##-Widget Bindings------------------------------------------------------
        #-----------------------------------------------------------------------
        #self.master.bind('<Ctrl-Z>', self.quit)  #alternative to Alt-F4
        self.master.bind('<Control-equal>', self.scaleup)
        self.master.bind('<Control-Button-4>', self.scaleup)   
        self.master.bind('<Control-minus>', self.scaledown)
        self.master.bind('<Control-Button-5>', self.scaledown)
        self.master.bind('<Control-MouseWheel>', self.scale_mouse)
        
        self.panel.bind('<Double-1>', self.doubleclick)
        self.panel.bind('<Return>', self.doubleclick)
        
        #Allow scrolling and typing without switching focus       
        self.entry_box.bind('<MouseWheel>', self.scroll_from_entry)
        self.entry_box.bind('<Button-4>', self.scroll_from_entry)
        self.entry_box.bind('<Button-5>', self.scroll_from_entry) 
        
        self.master.bind('<F5>', self.make_database)
        #self.master.bind('<F12>', self.scorch_mode)
        
        ##-Starting setup-------------------------------------------------------
        #-----------------------------------------------------------------------
        #Starting up with entry box active     
        self.entry_box.focus_set()  
        
        #Generating a starting message based on existence of a database
        if not self.index.findex:  # change to a FileIndex api call (_findex)
            self.panel.insert('', 'end', text='No cache database found', values=('Hit F5 to generate database',))
        else:
            self.panel.insert('', 'end', text='Type to search.   [F5 - Refresh Database]', values=('[Ctrl - +/-/MouseWheel - Adjust font size]',)) 
        # [Ctrl-O - Options]. [Ctrl-I - Info] 
            #self.panel.insert('', 'end', text='Scorch Mode is faster but uses more memory', values=('Loads the entire database into RAM',))
            
        self.update_searchbox()
        # search thread initiated via class
        
    #---------------------------------------------------------------------------
    ##GUI functionality---------------------------------------------------------
    #---------------------------------------------------------------------------   
    
    def scroll_from_entry(self, event): 
        '''Scroll results without deactivating entry box, called from entry_box'''
    
        self.panel.yview_scroll(1, 'units')
        
    def scaleup(self, event):
        '''The Treeview widget won't auto-adjust the row height, 
        so requires manual resetting upon font changing'''
        self.font['size']+=1
        self.style.configure('SearchBox.Treeview', rowheight=self.font.metrics('linespace')+1)
    
    def scaledown(self, event):
        self.font['size']-=1
        self.style.configure('SearchBox.Treeview', rowheight=self.font.metrics('linespace')+1)  
        
    def scale_mouse(self, event):
       self.scaleup(event) if event.delta>0 else self.scaledown(event) 
       
    def doubleclick(self, event):
        '''Invoke default app on double-click or Enter'''
           
        #Get file/folder name that was doule-clicked on
        selection=self.panel.item(self.panel.focus())
        filename=selection['text']
        if 'D' in selection['tags']:
            #remove square brackets indicating folders 
            filename=filename[1:-1]
            
        #Generate full path and invoke 
        full_path=selection['values'][0] + self.split_token + filename
        self.start(full_path)
    
    def quit(self, event):
        '''Currently Alt-F4 exits program, in case I want to add more shortcuts.
        Also add thread closing management here'''
    
        self.master.destroy()
    
    #---------------------------------------------------------------------------
    '''Cheese: 
    make_database()->is_sb_generated() - generate file index
    
    update_searchbox() - add new results to GUI
    
    update_query() - pass a query to the search thread
    '''
       
    def make_database(self, event):
        '''Using a thread to generate the dictionary to prevent GUI freezing'''
        
        #* dbm might not be thread safe - best might be to restart TMakeSearch
        self.gtime=time()  # for testing
        self.entry_var.set('Updating Database')
        self.entry_box.icursor('end')
        
        self.index.generate_db()
        
        #Wait for the dictionary to be generated
        self.is_db_generated()      
   
    def is_db_generated(self): 
        '''Update database if available or sleep and try again'''
    
        if self.index.is_db_generated():
            #A new fileindex was generated
            
            self.gtime=time()-self.gtime
            #to read about {}.format              #also, a label may be simpler
            self.entry_var.set('Database generation time- '+ str(self.gtime) + 's. Type to search. [F5 - Refresh Database]')
            
            self.entry_box.icursor(0)
         
            self.panel.delete(*self.panel.get_children())
            self.panel.insert('', 0, text='Scorch Mode is faster but uses more memory', values=('Loads database into RAM',))
           
            self.counter=0
                
        else:
            self.after(100, self.is_db_generated) 
      
    def update_searchbox(self):
        '''Update GUI with new result batches '''
        
        self.even=True
        #for splitting size and date from the keys  
        self.separator=' * '.encode(ENC)
        
        qresult=self.index.get_result_batch() #empty list if no results
        
        try:
            self.results, self.is_new=qresult[-1]
        except:
            if Checks.is_batch_recieved:
                print ('is_batch_recieved: no new results') 
            else:
                pass  #no new results
        else:
            if Checks.is_batch_recieved:
                print ('is_batch_recieved:', self.results)
            
            #if self.panel.get_children()!=(): 
            #results for a newer query, erase old results 
            if self.is_new:
                self.panel.delete(*self.panel.get_children())
            
            for key in self.results:
                try:
                    inode, fof, name, size, date=key.decode(ENC).split(u'*') #self.separator
                    #name, size, date=key.split(self.separator)
                    if Checks.is_tk_get_name:
                        print(name)
                except:
                    if Checks.is_result_parsed:
                        print ('parsing issue with', key)
                else:
                    #Getting path from the index
                    try:
                        path=self.index.findex[key].decode(ENC)  
                    except:
                        '''Avoiding a deadlock when dbm is closed and reopened
                        after update'''
                        break
                    else:
                        #adding existence check, see if causes lagging'''
                        real_name=name[1:-1] if 'D' in fof else name
                        does_exist=path + self.split_token + real_name
                        try:
                            os.stat(does_exist)
                        except:
                            print ('stat failed on ', does_exist)
                            #print(key.decode())
                            #A dead key
                            #del self.findex[key]
                            
                        color='color1' if self.even else 'color2'
                        self.even=not self.even
                        self.panel.insert('', 'end', text=name, values=(path, size, date), tags=(color, fof))                 
        self.after(60, self.update_searchbox) 
    
    def update_query(self, x=None, y=None, z=None):
        '''Invoked by StringVar().trace() method, which passes 3 arguments that 
        are honorably ditched '''
        
        #Cleaning up for 1st keystroke or after a message in the Entry box
        if not self.counter:   
           '''Entry box needs to be cleaned, the new char put in and the cursor
           placed after it'''
           #get&set the 1st search char. user may've changed cursor location b4 typing 
           self.entry_var.set(self.entry_var.get()[self.entry_box.index(INSERT)-1]) 
           #move cursor after the first char
           self.entry_box.icursor(1)
                       
        #Counter goes up either way
        self.counter+=1
        self.query=self.entry_var.get()  
        #self.query_queue.put(self.query)
        self.index.query_db(self.query)
        if Checks.is_query_sent:
            print ('is_query_sent: ', self.query)
            #print (self.counter)    
            
if KIVY_GUI:
    '''I started experimenting with a new Kivy GUI. Currently very basic and 
    disabled by default, feel free to check it out by setting KIVY_GUI=True in the 
    imports section. '''
    #-------------------------------------------------------------------------------
    ##--Kivy GUI--------------------------------------------------------------------     
    #-------------------------------------------------------------------------------
    Builder.load_string('''
    #<LinkedLabel@Label>:
        
    <KivySearchBox>:
        orientation:'vertical'
        RecycleView:
            id: result_view
            viewclass: 'Label'
            RecycleBoxLayout:
                orientation: 'vertical'             # up-down view/add
                default_size: None, dp(56)          # spacing between labels
                default_size_hint: 1, None          # center labels
                size_hint_y: None                   # start at top of screen instead of bottom
                height: self.minimum_height               
                
        TextInput:
            id: entry_box
            text: 'momo'
            font_size: 12
            multiline: False
            size_hint: 1, 0.04  
            on_text: root.query=self.text; root.index.query_db(root.query);        
    ''')

    class KivySearchBox(BoxLayout):
        ''' '''
        
        def __init__(self, db=DB, conf=CONF, **shnargs):
            super(KivySearchBox, self).__init__(**shnargs)
            #Widget.__init__(self, **shnargs)
            
            self.index=DriveIndex(db, conf)
            self.Plat=Platform()
            self.start= self.Plat.start_func()
            
            self.query=''
            #self.ids.result_view.data=[{'text': 'oh boy'}]
            #self.data=ObjectProperty(None)
            
            self._keyboard=window.Window.request_keyboard(self._other_kb_function, self)
            self._keyboard.bind(on_key_down=self._keyboard_events)
            
            separator='*'.encode(ENC)
            
            if not self.index.findex:  # change to a FileIndex api call (_findex)
                self.ids.result_view.data.append({'text': 'No cache database found. ' + 'Hit F5 to generate database'})
            else:
                self.ids.result_view.data.append({'text': 'Type to search.   [F5 - Refresh Database]'})
            
            #a=WindowBase()
            #WindowBase.maximize(a)
            #window.Window.maximized=True
            
        def _keyboard_events(self, keyboard, keycode, text, modifiers):
            if keycode[1]=='f5':
                self.ids.result_view.data=[{'text': 'Updating Database'}]
                self.index.generate_db()
                self.is_db_generated()
                
        def _other_kb_function(self):
            pass
                
        def is_db_generated(self):
            if self.index.is_db_generated:
                self.ids.result_view.data.append({'text': 'Type to search.   [F5 - Refresh Database]' + '[Ctrl - +/-/MouseWheel - Adjust font size]'})
            else:
                print('popo')
                Clock.schedule_once(self.is_db_generated, 0.1)
        
        def get_result_batch(self, dt):
            '''Search queries are updated and sent via TextInput's on_text. 
            Here we check if any results are available, to be scheduled periodically'''
            
            result_batch=self.index.get_result_batch() #empty list if no results
            try:
                results, is_new=result_batch[-1]
            except:
                if Checks.is_batch_recieved:
                    print ('is_batch_recieved: no new results') 
                else:
                    pass  #no new results
            else:
                if Checks.is_batch_recieved:
                    print ('is_batch_recieved:', results)
                
                
                if is_new:
                    #Results for a newer query, erase old results 
                    self.ids.result_view.data=[]
                    #del self.data[:]
                
                result_dicts=[{'text': key.decode(ENC).lsplit('*', 1)[1].replace('*', ' ')} for key in results]
                #result_dicts=[{'text': key.decode(ENC).replace('*', ' ')} for key in results]
                self.ids.result_view.data.extend(result_dicts)
        
        
    class Jiffy(App):   #optionally move to main()
        
        def build(self):
        
            search_box=KivySearchBox()
            Clock.schedule_interval(search_box.get_result_batch, 0.1) 
            
            return search_box

                   
#-------------------------------------------------------------------------------        
##--Initializing---------------Initializing-------------------------------------
#-------------------------------------------------------------------------------

def allrightythen():
    '''Setup display if needed/available, load GUI'''
    
    plat=Platform()
    #plat.scale_display()
    
    if KIVY_GUI:
        #Not working when scaling is on. use kivy's own dpi management?
        Config.set('graphics', 'window_state', 'maximized') 
        Config.write()
        Jiffy().run()
    else:
        plat.scale_display()
        sb=SearchBox()
        sb.pack()
    
        mainloop()


if __name__=='__main__':
    allrightythen()    