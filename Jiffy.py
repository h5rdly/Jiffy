# -*- encoding='utf-8' -*-

##Imports-------------------Imports--------------------------------
#Compatibility
from __future__ import print_function  #for testing

#move to a config filedown the line
DB='Jiffy_DB'

#Basics
import os                #path, startfile, name     
import sys               #platform, executable, version
from time import time, ctime, sleep
from collections import namedtuple 

#Concurrency
try:
    import _thread as thread
    from queue import Queue
except:
    import thread
    from Queue import Queue
#import multiprocessing as mp      #faster dictionary lookups?

#Opening files with defalt app:
try:   
    import subprocess32 as sp  #better subprocess for python2
except:
    import subprocess as sp
   
#Persistence / storage related
#from whichdb import whichdb
#import ldbm as dbm

try:
    import anydbm as dbm   #Python 2, with some luck we get bsddb/dbhash
except:
    if not 'win' in sys.platform:
        import dbm 
    else:
        #Python 3 on Windows, trying to avoid dumbdbm
        try:
            import semidbm as dbm
            #import lmdb as dbm
        except:
            import dbm 
finally:
    #for checking which built-in dbm backend is in use 
    try:
        from dbm import whichdb
    except:
         from whichdb import whichdb      
       
#NTFS snooping, getting admin on Windows, DPI workarounds, Filetype icons
from ctypes import *             

#GUI
try: 
    from tkinter import *          #Entry, StringVar, Message
    from tkinter.ttk import Treeview, Style
    from tkinter.font import Font 
except:
    from Tkinter import *
    from ttk import Treeview, Style
    from tkFont import Font
    
#Scanning the filesystem		
try:
    from os import scandir        #on Python 3.5+    
except:
    try:
        from scandir import scandir
    except:
        #Add option to use shitpa listdir as a last resort
        pass
    else:
        from scandir import walk        #for speed comparisons
else:    
    from os import walk                 #for speed comparisons     
  
##Imports for Testing/Aux Functions---------------------------------------------
test_names=('is_query_sent', 'is_query_passed', 'is_search_list_generated', 'is_result_batch', 
'is_batch_recieved', 'is_result_parsed', 'dict_creation_status', 'per_dir_recursion', 
'ctime_issue_windows_py35', 'is_dpi_scale', 'recursion_stats')

Testnames=namedtuple('Testnames', test_names)

Testing=1 

if not Testing:
    Tests=Testnames(*(0 for _ in test_names))
    
else:  
    from pympler.asizeof import asizeof
    import pdir as dir
    import fire, better_exceptions
    try:
        from importlib import reload
    except:
        #seems to exist on 2.7 even though undocumented
        from imp import reload 
    
    Tests=Testnames
    
    Tests.is_dpi_scale=1
    Tests.is_query_sent=0
    Tests.is_query_passed=0
    Tests.is_batch_recieved=0
    Tests.is_result_batch=0
    Tests.is_result_parsed=0

    Tests.dict_creation_status=1
    Tests.per_dir_recursion=0
    Tests.recursion_stats=0
    Tests.ctime_issue_windows_py35=1
     
    def size(object):
        '''getting dictionary sizes in Mb'''
        
        return asizeof(object)/1024/1024
    
##Constants and checks---------------------------------------------
#VER=sys.version_info
VER=sys.version.split()[0]
IS_PY27= VER>='2.7' and VER<'3.0'
Gb_Tb_PRECISION=2
SPLIT_TOKEN='\\' if 'win' in sys.platform else '/'
SCORCH=False            
ENCODING='utf-8'

##Logic/Algo--------------------Logic/Algo--------------------------
'''In use:  
            [drives] GetDrives() - return drive list to iterate over

            func() StartFunc() - return a platform specific function to call 
                                 the default filetype app on doubleclick
                                 
            queue.put((dbm, [unsearched])) RecursiveCreateDict(drives, dbqueue=None) - 
                recurse all drives and make a dictionary where values are paths, 
                keys contain names, sizes and dates
            
            queue.put(([result_batch], bool is_new)) TMakeSearch(fdict, squeue=None, rqueue=None) - 
                get queries via a queue, search and return results in batches
                 via another queue
            
            float FloatPrecision(num, precision) - get back floats with a specific
                                                   amount of precision  
            '''

def FloatPrecision(num, precision):
    '''if i opt for losing excess precision of floats in advance'''

    floater=int((num-int(num))*(10**precision))/(10**precision+0.0)
    return int(num)+floater

def GetDrives(): 
    '''Generate a list of drives for the database function. On linux - just '/' '''
    
    exists=os.path.exists
    drives=[u'/']        
    if 'win' in sys.platform:
        drives.extend((chr(a)+ u':\\' for a in range(ord('A'), ord('Z')) if exists(chr(a)+':')))
        try:
            drives.remove(u'C:\\')  # '/' and 'C:/' represent the same drive, but '/' allows full traversal
        except ValueError:         #  Trying to walk 'C:/' only traversed (very few) specific directories
            pass                   #  in my attempts
    return drives    

def StartFunc():
    '''Platform based response to double-click/Enter'''

    if 'win' in sys.platform:
        func=os.startfile     #an API call also an option
    else:   
        #Linux, FreeBSD, OpenBSD, MacOSX
        open_command='open' if 'darwin' in sys.platform else 'xdg-open'   #os.name=='posix'
        func=lambda filepath: sp.Popen((open_command, filepath))
            
    return func    

def RecursiveCreateDict(drives, queue=None, dbm=None):
    '''Recursive implementation of generating the file dictionary, currently in use
    A stack based implementation is in stash.py. I tried to avoid function calls
    for the speedup,so this one is a bit longer'''
    
    fdict={}
    fdict['**']=''     # "Null key" referral, currently not in use
    unsearched=[]
    
    def RecursiveAdd(top):      
        
        #Helper function to set up the size and date strings in desired format
        def pretty_size_date(size, date):
            '''Return formatted size and date strings'''
            
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
            #A alternatively this can be extracted later 
            
            try:
                # + works (~x10) faster than join() in my timeits
                fdate= date[2] + u'-' + date[1] + u'-' + date[4][2:] + u' | ' + date[3][:-3] +u''
            except:
                #In case st_mtime returned a negative timestamp (None passed)
                fdate='Error getting date'
            
            return fsize, fdate
        
        #Prepping dir contents
        try:
            contents=scandir(top)  #scandir the path
        except OSError:
            unsearched.append(top)
            return 0 
        
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
                #On Python 3.5, Win8.1, had an issue with a negative time on st_mtime
                #Substituted for an error notification when parsed
                date=None 
                
                if Tests.ctime_issue_windows_py35:
                    print (fpath + fname, scandir_item.stat().st_mtime)
                           
            fname=scandir_item.name + u''
            
            if not scandir_item.is_dir():
                #File specific treatment
                size=scandir_item.stat().st_size
            else:     
                #Folder specific treatment
                fname='['+fname+']'
                if not scandir_item.is_symlink():      #remove one of the checks 
                    size=RecursiveAdd(scandir_item.path)  #Aww shit! 
                    
            top_size+= size
                   
            fsize, fdate=pretty_size_date(size, date)
            fpath=top + u''
            
            key=fname + ' * ' +fsize + ' * ' +fdate + u''
            value= fpath
            if key in fdict:
                '''contingency in case two  same named same sized files 
                were modified in the same minute'''      
                key=fname + '[1]' + ' * ' +fsize + ' * ' +fdate + u''
                
            fdict[key.encode(ENCODING)]=value.encode(ENCODING)  
          
        return top_size    
        
        '''  
        so far:
                      
         def RecursiveAdd(top):  
        
            for scandir_item in contents:
            
                if not scandir_item.is_dir():
                    
                else:
                    #Folder specific treatment
                    RecursiveAdd()
                    
            return top_size
       '''     
   
        if Tests.per_dir_recursion:
            print ("Done recursing on:", top) 
   
        
    def ThreadedWalk():
        '''Threaded variant using Threading, worked slower for me, ditched'''
    
        threads=[]    
        for drive in drives:
            drive_thread=Thread(target=RecursiveAdd, args=(drive,))
            drive_thread.start()
            threads.append(drive_thread)    
        for drive_thread in threads: 
            drive_thread.join()
    
            
    for drive in drives:
        '''Recursing on all drives'''
        
        gtime=time()
        RecursiveAdd(drive)
        
        if Tests.recursion_stats:
            gtime=time()-gtime
            print ("Done recursing on drive ", drive)
            print("Time: ", gtime)
    
    #Passing the generated dictionary
    try:
        queue.put((fdict, unsearched))
    except:
        return fdict 
        

def TMakeSearch(fdict, squeue=None, rqueue=None):
    '''Attempt at circumventing StopIteration(), did not see speed advantage'''
    RESULTS_PER_BATCH=50
    #batch_counter=0
    
    if whichdb(DB) in {'dbm.gnu', 'gdbm', 'dbm.ndbm', 'dbm'}:
        '''iteration is  not implemented for gdbm and (n)dbm, forced to
        pop the keys out in advance for "for key in fdict:" if any of those''' 
        fdict=fdict.keys()
    else:
        #bsddb, dumbdbm or semidbm
        fdict=fdict
    
    #extracting keys to a set, make his optional as the new "scorch mode"
    if 'win' in sys.platform:  #did not see speed improvement in Linux
        try:
            fdict=frozenset(fdict)
        except:
            fdict=frozenset(fdict.keys())
        
    search_list=None
    while True:  
        query=None
        while not squeue.empty():        #more items may get in (or not?) while condition is checked
            query=squeue.get()
        try:    
            search_list=query.lower().encode(ENCODING).split()
            if Tests.is_query_passed:
                print (search_list)
        except:
            if query:
                # True is passed when a new database has been generated
                # A new instance of TMakeSearch will be opened
                break
                
            else:
                #No new query or a new database is being generated
                sleep(0.1)
                continue
        else:
            is_new_query=True
        
        result_batch=[] 
        for key in fdict: 
            separator='*'.encode(ENCODING)   #Python 3, yaaay
            filename=key.split(separator)[0].lower()
            '''_all=all
            if _all(token in filename for token in search_list):
                    result_batch.append(key)'''
            #Add key if matching    
            for token in search_list:
                if not token in filename:
                    break
            #If loop hasn't ended abruptly
            else:     
                result_batch.append(key)
            
            #Time to send off a batch?    
            if len(result_batch)>=RESULTS_PER_BATCH: 
                rqueue.put((result_batch, is_new_query))
                if Tests.is_result_batch: 
                    print(result_batch, len(result_batch))
                    print('is_result_batch: results on queue')
                result_batch=[]
                #print (len(result_batch))
                is_new_query=False
                sleep(0.1)
                if not squeue.empty(): 
                    break
     
        #If the for loop ended naturally, with some batch<50        
        rqueue.put((result_batch, is_new_query))    
 
#/-----------------------Logic/Algo--------------------------------


#-------------------------------------------------------------------------------
##Graphics-------------Graphics-------------------------------------------------
#-------------------------------------------------------------------------------
''' includes: '''

class SearchBox(Frame):
    '''A Treeview widget on top, Entry on bottom, using queues for
     interaction with outside functions'''
   
    def __init__(self, parent=None, db=DB, fdict={}):
        Frame.__init__(self, parent)
        self.Tests=Tests
        self.db=db
        self.fdict=dbm.open(self.db, 'c')
        #self.fdict['**']=''
        self.db_update=False
        #will hold the query to be processed
        self.query=None 
        self.drives=self.get_drives()
        self.start_func=StartFunc()   #platform dependent double-click response
            
        self.results=iter(())   #initiating query results as an empty generator
        self.total_width=self.winfo_screenwidth() #to adjust column widths relative to screen size
        #Remember scorch mode
        self.scorch=False 
        self.encoding=ENCODING
        
        #for scorch mode 
        #self.keylist=self.fdict.keys()    
        self.keylist_index=0
        self.keylist_counter=0
        
        #keystroke indicator
        self.counter=0
        
        #queues for passing search queries and results
        self.query_queue= Queue()
        self.result_queue=Queue()
        
        #for usage by db generating function
        self.dbinit_queue=Queue()
        
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
        
        #--Widget Bindings
        #self.master.bind('<Ctrl-Z>', self.quit)  #alternative to Alt-F4
        self.master.bind('<Control-equal>', self.scaleup)
        self.master.bind('<Control-Button-4>', self.scaleup)   
        self.master.bind('<Control-minus>', self.scaledown)
        self.master.bind('<Control-Button-5>', self.scaledown)
        self.master.bind('<Control-MouseWheel>', self.scale_mouse)
        
        self.panel.bind('<Double-1>', self.doubleclick)
        self.panel.bind('<Return>', self.doubleclick)
        
        #allow scrolling and typing without switching focus       
        self.entry_box.bind('<MouseWheel>', self.scroll_from_entry)
        self.entry_box.bind('<Button-4>', self.scroll_from_entry)
        self.entry_box.bind('<Button-5>', self.scroll_from_entry) 
        
        self.master.bind('<F5>', self.make_database)
        #self.master.bind('<F12>', self.scorch_mode)
        
        #--Starting up with entry box active     
        self.entry_box.focus_set()  
        
        #--Generating a starting message based on existence of a database
        if not self.fdict:
            self.panel.insert('', 'end', text='No cache database found', values=('Hit F5 to generate database',))
        else:
            self.panel.insert('', 'end', text='Type to search.   [F5 - Refresh Database]', values=('[Ctrl - +/-/MouseWheel - Adjust font size]',)) 
        # [Ctrl-O - Options]. [Ctrl-I - Info] 
            #self.panel.insert('', 'end', text='Scorch Mode is faster but uses more memory', values=('Loads the entire database into RAM',))
            
        self.update_searchbox()
        #Initializing the query managing function in a separate thread (upgrade to pool?)
        thread.start_new_thread(TMakeSearch, (self.fdict, self.query_queue, self.result_queue))
    
    ##GUI functionality--------------------------------------------------------   
    #O change to initiation from parameter to SearchBox for more modularity
    def get_drives(event):
        return GetDrives() 
    
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
           
        #getting file/folder name and removing '[' and ']' for folders
        selection=self.panel.item(self.panel.focus())
        filename=selection['text']
        #remove folder indicating square brackets
        if filename[0]=='[':
            filename=filename[1:-2]
        
        #SPLIT_TOKEN='\\' if 'win' in sys.platform else '/'
        full_path=selection['values'][0] + SPLIT_TOKEN + filename
        self.start_func(full_path)
    
    def quit(self, event):
        '''Currently Alt-F4 exits program, in case I want to add more shortcuts.
        Also add thread closing management here'''
    
        self.master.destroy()
    
    ##Cheese: update_database()->is_sb_generated(), trace_results(), update_query()    
    def make_database(self, event):
        '''Using a thread to generate the dictionary to prevent GUI freezing'''
        
        #* dbm might not be thread safe - best might be to restart TMakeSearch
        self.gtime=time()  # for testing
        self.entry_var.set('Updating Database')
        self.entry_box.icursor('end')
        
        #Resulting dicitionay will be passed via dbinint_queue
        thread.start_new_thread(RecursiveCreateDict, (self.drives, self.dbinit_queue, self.fdict))
        
        #Wait for the dictionary to be generated
        self.is_db_generated()      
   
    def is_db_generated(self): 
        '''Update database if available or sleep and try again'''
    
        if not self.dbinit_queue.empty():
            #A new dictionary was passed
            
            #retrieving new dict
            self.newdict, self.unsearched= self.dbinit_queue.get()
            #Messaging TMakeSearch to stop querying the dictionary
            self.db_update=True
            self.query_queue.put(None)             
            sleep(0.11)       #TMakeSearch takes 0.1s naps. Check further '''
            
            if whichdb(self.db)==('dbhash'):
                '''For dumbdbm, this jams the app, as does manual updating. it's
                not dumb, it's just not worthy'''
                self.fdict.update(self.newdict)
            else: 
                for key in self.newdict:
                    self.fdict[key]=self.newdict[key]
            print ('fdict is created')
            self.db_update=False
            #save new database
            self.fdict.sync()
            print ('fdict synced')
            
            #Open a new TMakeSearch with the updated database
            #thread.start_new_thread(TMakeSearch, (self.fdict, self.query_queue, self.result_queue))
            
            #Cleaning up
            self.newdict.clear()
            self.newdict=None
          
            self.gtime=time()-self.gtime
            #to read about {}.format              #also, a label may be simpler
            self.entry_var.set('Database generation time- '+ str(self.gtime) + 's. Type to search. [F5 - Refresh Database]')
            
            #Pass a signal to close TMakeSearch, then reopen it
            self.query_queue.put(True)
            thread.start_new_thread(TMakeSearch, (self.fdict, self.query_queue, self.result_queue))
            
            self.entry_box.icursor(0)
            #self.loading.destroy()
            self.panel.delete(*self.panel.get_children())
            self.panel.insert('', 0, text='Scorch Mode is faster but uses more memory', values=('Loads database into RAM',))
            #self.keylist=fdict.keys()   #for scorch mode
            self.counter=0
            #self.IS_1ST_PRESS=True
            #for testing
            #print time()-self.start
            #print self.dict_size()           
        else:
            self.after(100, self.is_db_generated) 
      
    def update_searchbox(self):
        '''Update GUI with new result batches '''
        
        self.even=True
        #for splitting size and date from the keys
        self.separator=' * '.encode(self.encoding)
        while not self.result_queue.empty():
            qresult=self.result_queue.get()
            #print ('is_batch_recieved:', qresult)
            #if qcounter==self.counter:  #currently assuming results will arrive by querying order
                #break
        try:
            #if nothing in queue this will raise an error, saves a preemptive if clause
            self.results, self.is_new=qresult
            if Tests.is_batch_recieved:
                print ('is_batch_recieved:', self.results)
        except:
            pass #no new results
            if Tests.is_batch_recieved:
                print ('is_batch_recieved: no new results')    
        else:
            #if self.panel.get_children()!=(): 
            #results for a newer query, erase old results 
            if self.is_new:
                self.panel.delete(*self.panel.get_children())
            
            for key in self.results:
                try:
                    name, size, date=key.decode(self.encoding).split(u'*')
                    #name, size, date=key.split(self.separator)
                    if Tests.is_result_parsed:
                        print(name)
                except:
                    if Tests.is_result_parsed:
                        print ('parsing issue with', key)
                else:
                    path=self.fdict[key].decode(self.encoding)
                    '''if 'win' in sys.platform and top[0] is u'/':
                        top=u'C:\\'+top[1:] '''
                    color='color1' if self.even else 'color2'
                    self.even=not self.even
                    self.panel.insert('', 'end', text=name, values=(path, size, date), tags=(color,))
         
        self.after(60, self.update_searchbox) 
    
    def update_query(self, x=None, y=None, z=None):
        '''Invoked by StringVar().trace() method, which passes 3 arguments that are honorably ditched '''
        
        #Deactivate while switching dictionaries
        if self.db_update:
            pass
    
        #Cleaning up for 1st keystroke or after a message in the Entry box
        if not self.counter:   
           '''Entry box needs to be cleaned, the new char put in and the cursor
           placed after it'''
           #get&set the 1st search char. user may've changed cursor location b4 typing 
           self.entry_var.set(self.entry_var.get()[self.entry_box.index(INSERT)-1]) 
           #move cursor after the first char
           self.entry_box.icursor(1)
                       
        #counter goes up either way
        self.counter+=1
        self.query=self.entry_var.get()  
        self.query_queue.put(self.query)
        if Tests.is_query_sent:
            print (self.query)
            print (self.counter)    
        

    ##Not in use ----------------------------------------------------------------  
    
    def trace_query(self):
        '''If I opt for periodically checking the StringVar'''
    
        if self.counter:  #when counter=0 there's a message/notification in the entry box
            if self.query!=self.entry_var.get():
                self.query=self.entry_var.get()
                self.query_queue.put(self.query)
        
        self.after(100, self.trace_query)
    
    def trace_and_update(self):
        ''' In-GUI implementation of query searching, uses a list for iterating 
        over the keys'''
        
        '''works smoother when results are generated quickly, but with
        sparse results GUI becomes unresponsive for short whiles. Relevant
        only if results are guaranteed to be generated swiftly'''      
        
        #print self.query
        #if new query, resetting search parameters and GUI
        if self.query!=self.entry_var.get(): 
            self.keylist_counter=0
            self.query=self.entry_var.get()
            self.search_list=self.query.lower().split()
            self.panel.delete(*self.panel.get_children())
         
        self.insertion_counter=0
        self.keylist_index=self.keylist_counter    
        for key in self.keylist[self.keylist_index:]:    
            filename=key.split('*')[0].lower()
            #If a match, parse and add to the Treeview
            if self.all(token in filename for token in self.search_list):
                name, size, date=key.split('*')
                self.panel.insert('', 'end', text=name, values=(self.fdict[key], size, date))
                self.insertion_counter+=1 
            self.keylist_counter+=1
            
            if self.insertion_counter>=self.INSERTIONS_PER_CYCLE: #50  ##or not dict_counter:
                break  #nap time
                
        self.after(60, self.trace_and_update)
    #/Not in use----------------------------------------------------------------------     
      
##Memos/Misc------------------------------------------------------
# getting name of selection:  panel.item(panel.selection(), 'text')

'''
    #why such sequence (pack, process, unpack) doesn't work properly on tkinter)
    load_screen=Message(text='Updating Database...')
    load_screen.pack()
    fdict=CreateDict(drives)
    load_screen.destroy()
    '''

##Initializing---------------Initializing--------------------------

def allrightythen():
    '''Windows arrangements, load GUI'''
    
    if 'win' in sys.platform:
        try: 
            #Enable DPI awareness on newer versions of Windows
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass  #well, shit.
        
    sb=SearchBox()
    sb.pack()
    mainloop()


if __name__=='__main__':
    allrightythen()  
