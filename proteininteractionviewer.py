about = """///////////////////////////////////////////////////////////////////////////////////////////////
// ProteinInteractionViewer.py
//
//  Version:           0.2.2
//
//
// authors:
//    initials    name                 organization                email
//   ---------   -----------------    ------------------------    ----------------------------
//     KER        Kyle Roberts          Duke University           ker17@duke.edu
//     JDJ        Jonathan Jou          Duke University           jj@cs.duke.edu
//
///////////////////////////////////////////////////////////////////////////////////////////////


   Written by Kyle Roberts (2013-2014)
 
   The goal of this pymol plugin is to provide easy access to the 
   Probe and Reduce software tools made available from the Richardson 
   Lab (http://kinemage.biochem.duke.edu/software/index.php)    

   In order for this plugin to work you must have Probe and Reduce installed
   which can be found in the above link. Also the two programs must be in
   the operating system's PATH variable and named "probe" (or "probe.exe")
   and "reduce" (or "reduce.exe")

   This library is free software; you can redistribute it and/or
   modify it under the terms of the GNU Lesser General Public
   License as published by the Free Software Foundation; either
   version 2.1 of the License, or (at your option) any later version.
   This library is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
   Lesser General Public License for more details.
   You should have received a copy of the GNU Lesser General Public
   License along with this library; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
   USA

    Contact Info:
        Bruce Donald
        Duke University
        Department of Computer Science
        Levine Science Research Center (LSRC)
        Durham
        NC 27708-0129 
        USA
        brd@cs.duke.edu
        http://www.cs.duke.edu/~brd/

    If you use or publish any results derived from the use of this
    program please cite:

    Kyle E. Roberts and Bruce R. Donald (2014). Protein Interaction Viewer. 
    http://www.cs.duke.edu/donaldlab/software/proteinInteractionViewer/

    Copyright (C) 2013-2014 Kyle Roberts, and Bruce R. Donald

    <signature of Bruce Donald>, 2 Jul, 2013
    Bruce Donald, Professor of Computer Science
"""

import tkinter.simpledialog
import tkinter.messagebox
from pymol import cmd
from pymol import util 
from pymol import stored 
from pymol import menu
import sys, urllib.request, urllib.parse, urllib.error, zlib
import tkinter
from tkinter import *
from tkinter.filedialog import askopenfilename
from tkinter.filedialog import asksaveasfilename
import Pmw
import subprocess
import os,math,re
import string
from pymol.cgo import *
import queue
import threading
import platform



def __init__(self):
    self.menuBar.addmenuitem('Plugin', 'command', 'ProteinInteractionViewer',label = 'ProteinInteractionViewer',
                            command = lambda s=self : ProteinInteractionViewer(s))
    rewritePymolMenu(self)


probeExe = ""
reduceExe = ""
reduceDB = ""

reduceError = 'Could not find "reduce" executable. Please make sure the program is in your PATH variable and named "reduce"'
probeError = 'Could not find "probe" executable. Please make sure the program is in your PATH variable and named "probe"'

class ProteinInteractionViewer:

    AAtypes = None
    rotResList = []
    rotResIList = []
    origRotVals = []
    curAAtype = None
    hasFocus = False

    dotQueue = queue.Queue();


    def __init__(self,app):
    
        #Initialize the rotamers for the SC rotator
        self.setupAAtypes()
        
        #Find Probe and Reduce Executables
        findExecutables()
        
        #Start a thread to calculate dots when doing SC rotation
        self.dotThread = ThreadDots(self.dotQueue)
        self.dotThread.start()
        
        #Get the parent window for our plugin
        parent = app.root
        self.parent = parent
        
        # Create the dialog.
        self.dialog = Pmw.Dialog(parent,
                                buttons = ('Close','About'),
                                title = 'Protein Interaction Viewer',
                                command = self.execute)
        self.dialog.withdraw()
        #self.dialog.protocol('WM_TAKE_FOCUS',self.updateSels)
        self.dialog.bind('<FocusIn>',self.updateSels)
        
               
        #define comboBoxes that will need to be updated when selections are updated
        self.cBoxes = []

        # Set up the main page
        self.notebook = Pmw.NoteBook(self.dialog.interior())
        self.notebook.pack(fill='both',expand=1,padx=1,pady=1)

        #Add Hydrogen page
        ########################################
        page = self.notebook.add('Edit H')
        group = Pmw.Group(page,tag_text='Hydrogen Options')
        group.pack(fill = 'both', expand = 1, padx = 1, pady = 5)
        self.h_sel = Pmw.ScrolledListBox(group.interior(),
                                  label_text = 'Selection: ',
                                  labelpos = 'nw',
                                  #scrolledlist_items = self.getSels(),
                                  #dropdown = 0,
                                  listbox_height = 10)
        #self.cBoxes.append(self.h_sel)
        self.h_newSel = Pmw.EntryField(group.interior(),
                                       labelpos = 'w',
                                       label_text = 'New Object Name')

        self.h_buttons = Pmw.ButtonBox(group.interior())

        self.h_buttons.add('Clear H', command = self.clearH)
        self.h_buttons.add('Add H', command = self.addH)
        
        self.replVar = IntVar()
        self.replaceCheck = tkinter.Checkbutton(self.h_buttons.interior(), text = 'Replace',variable=self.replVar)
        self.replaceCheck.grid(row = 0, column = 4)

        for widget in (self.h_sel, self.h_newSel, self.h_buttons):
            widget.pack(fill = 'x',padx=1,pady=1)

        ##################################################

	    #Add Dots page
        page = self.notebook.add('Load Dots')
        group = Pmw.Group(page,tag_text='Load Dots')
        group.pack(fill = 'both',expand = 1, padx = 1, pady = 5)
        frame = Frame(group.interior())
        frame.pack(fill='x')
        
        
        self.d_sel1 = Pmw.ComboBox(frame,
                                   label_text = 'Sel1: ',
                                   labelpos = 'nw',
                                   #scrolledlist_items = self.getSels(),
                                   dropdown = 0,
                                   listbox_height = 10)
        self.cBoxes.append(self.d_sel1)
        self.d_sel2 = Pmw.ComboBox(frame,
                                   label_text = 'Sel2: ',
                                   labelpos = 'nw',
                                   #scrolledlist_items = self.getSels(),
                                   dropdown = 0,
                                   listbox_height = 10)
        self.cBoxes.append(self.d_sel2)
        self.d_sel1.pack(side=LEFT,padx=10)
        self.d_sel2.pack(side=LEFT,padx=10)

        self.d_name   = Pmw.EntryField(group.interior(),
                                       labelpos = 'w',
                                       label_text = 'Dots Name',
                                       value = 'dots')
        self.d_params = Pmw.EntryField(group.interior(),
                                       labelpos = 'w',
                                       label_text = 'Additional Parameters')
        self.d_buttons = Pmw.ButtonBox(group.interior())
        self.d_buttons.add('Load Dots', command = self.loadDotsButton)

        optionFrame = Frame(group.interior())

        self.d_selfVar = IntVar()
        self.d_selfCheck = tkinter.Checkbutton(optionFrame, text="Self", variable=self.d_selfVar)

        
        self.dotSizeEntry = Pmw.EntryField(optionFrame, labelpos='w',label_text="Dot Size: ", value=0,validate='real')
        self.dotSizeEntry.component("entry").configure(width=5)
        self.lineSizeEntry = Pmw.EntryField(optionFrame, labelpos='w',label_text="Line Size: ", value=1,validate='real')
        self.lineSizeEntry.component("entry").configure(width=5)

        self.d_name.pack(fill='x')
        self.d_params.pack(fill='x')
        optionFrame.pack(fill='x')
        self.d_selfCheck.pack(side=LEFT,padx=10)
        self.dotSizeEntry.pack(side=LEFT, padx=10)
        self.lineSizeEntry.pack(side=LEFT, padx=10)
        self.d_buttons.pack()
        
        #########################################################

        #Add SC rotator page
        page = self.notebook.add('Side-chain Rotator')
        group = Pmw.Group(page, tag_text='Side-chain Rotator')
        group.pack(fill='both',expand = 1, padx = 1, pady = 5)
        frame = Frame(group.interior())
        frame.pack(fill='x')
        
        
        self.resLabel = tkinter.Label(frame, text="")
        self.resLabel.grid(row=0,column=2)
        
        self.dihVar = []
        self.dihScale = []
        for i in range(4):
            self.dihVar.append(IntVar())
            self.dihScale.append(Scale( frame, from_=-180, to=180, highlightthickness=0,sliderlength=20,resolution = 1,length = 130,variable = self.dihVar[i], command=lambda x, index=i: self.changeDihedral(index,x),orient=HORIZONTAL, label="Chi "+ str(i)))
            self.dihScale[i].grid(row=i+1,column=2)
            self.dihScale[i].bind("<ButtonRelease-1>",self.rotRelease)
            self.dihScale[i].bind('<KeyRelease>',self.rotRelease)
            
            self.dihScale[i].grid_remove()      
        
        self.rotBox = Pmw.ScrolledListBox(frame,
                                  label_text = 'Rotamer: ',
                                  labelpos = 'nw',
                                  listbox_height = 15,
                                  selectioncommand = self.rotBoxCommand)
        self.rotBox.grid(rowspan=4,row=1,column=1)
        
        self.showDotsCheckVar = IntVar()
        self.showDotsCheck = tkinter.Checkbutton(frame, text="Show Dots", variable=self.showDotsCheckVar,command=self.dotCheckCB)
        self.showDotsCheck.grid(row=5,column=1)
        
        self.notebook.setnaturalsize()
        
        #get the window to open next to pymol and not on top of it
        #first get screen size so we don't go off the screen
        swidth = parent.winfo_screenwidth()
        pwidth = parent.winfo_width()
        rootx = parent.winfo_rootx()
        dwidth = self.dialog.winfo_width()
        
        xpos = min(rootx+pwidth+8,swidth-dwidth)
        
        self.dialog.geometry("+%d+%d" % (xpos,0))
        
        self.dialog.show()
   
    def dotCheckCB(self):
        dotList = ["small_overlap_scRotDots", "bad_overlap_scRotDots","vdw_contact_scRotDots","H-bonds_scRotDots"]
        selections = cmd.get_names_of_type("object:cgo");
        
        if(self.showDotsCheckVar.get()==0):
            for name in dotList:
                if name in selections:
                    cmd.hide("cgo", name)
        else:
            curObj = self.getSelObject("_kropkresi")
            self.dotQueue.put(curObj)
            for name in dotList:
                if name in selections:
                    cmd.show("cgo", name) 
        
    def hideRotDots(self):
        dotList = ["small_overlap_scRotDots", "bad_overlap_scRotDots","vdw_contact_scRotDots","H-bonds_scRotDots"]
        selections = cmd.get_names_of_type("object:cgo");
        
        for name in dotList:
            if name in selections:
                cmd.hide("cgo", name)   
    
        
    def rotRelease(self,Event):
        Event.widget.focus_set()
        if(self.showDotsCheckVar.get() > 0):
            #get object the residue is in
            curObj = self.getSelObject('_kropkresi')
            #submit the job   
            self.dotQueue.put(curObj)
    
    #assumes that there is only one residue in the selection
    def getSelObject(self,sel):
        myspace = {'objList': []}
        cmd.iterate(sel+' and name CA', 'objList.append(model)',  space=myspace)
        return myspace['objList'][0]
      
    def rotBoxCommand(self):
        sels = self.rotBox.curselection()
        if len(sels) == 1:
            dihVals = []
            if sels[0] == '0':
                dihVals = self.origRotVals
                for dihNum,val in enumerate(dihVals):
                    AAtype.setDihVal("_kropkresi", self.curAAtype.dihAtomNames[dihNum], dihNum, val)
                    self.dihScale[dihNum].set(val)
            else:
                self.curAAtype.setRotamer("_kropkresi", int(sels[0])-1)
                for dihNum,val in enumerate(self.curAAtype.dihVals[int(sels[0])-1]):
                    self.dihScale[dihNum].set(val)
                #self.curAAtype.setRotamer("sele",int(sels[0])-1)
            #self.rotRelease(None)
 
        #For every AA type we need to define the dihedrals and the values
    def setupAAtypes(self):
        self.AAtypes = {} 
        self.AAtypes['VAL'] = AAtype('VAL',[['N','CA','CB','CG1']],[[63],[175],[-60]])
        self.AAtypes['LEU'] = AAtype('LEU',[['N','CA','CB','CG'],['CA','CB','CG','CD1']],[[62,80],[-177,65],[-172,145],[-85,65],[-65,175]])
        self.AAtypes['ILE'] = AAtype('ILE',[['N','CA','CB','CG1'],['CA','CB','CG1','CD1']],[[62,100],[62,170],[-177,66],[-177,165],[-65,100],[-65,170],[-57,-60]])
        self.AAtypes['PHE'] = AAtype('PHE',[['N','CA','CB','CG'],['CA','CB','CG','CD1']],[[62,90],[-177,80],[-65,-85],[-65,-30]])
        self.AAtypes['TYR'] = AAtype('TYR',[['N','CA','CB','CG'],['CA','CB','CG','CD1']],[[62,90],[-177,80],[-65,-85],[-65,-30]])
        self.AAtypes['TRP'] = AAtype('TRP',[['N','CA','CB','CG'],['CA','CB','CG','CD1']],[[62,-90],[62,90],[-177,-105],[-177,90],[-65,-90],[-65,-5],[-65,95]])
        self.AAtypes['CYS'] = AAtype('CYS',[['N','CA','CB','SG']],[[62],[-177],[-65]])
        self.AAtypes['MET'] = AAtype('MET',[['N','CA','CB','CG'],['CA','CB','CG','SD'],['CB','CG','SD','CE']],[[62,180,75],[62,180,-75],[-177,65,75],[-177,65,180],[-177,180,75],[-177,180,180],[-177,180,-75],[-67,180,75],[-67,180,180],[-67,180,-75],[-65,-65,103],[-65,-65,180],[-65,-65,-70]])
        self.AAtypes['SER'] = AAtype('SER',[['N','CA','CB','OG']],[[62],[-177],[-65]])
        self.AAtypes['THR'] = AAtype('THR',[['N','CA','CB','OG1']],[[62],[-175],[-65]])
        self.AAtypes['LYS'] = AAtype('LYS',[['N','CA','CB','CG'],['CA','CB','CG','CD'],['CB','CG','CD','CE'],['CG','CD','CE','NZ']],[[62,180,68,180],[62,180,180,65],[62,180,180,180],[62,180,180,-65],[62,180,-68,180],[-177,68,180,65],[-177,68,180,180],[-177,68,180,-65],[-177,180,68,65],[-177,180,68,180],[-177,180,180,65],[-177,180,180,180],[-177,180,180,-65],[-177,180,-68,180],[-177,180,-68,-65],[-90,68,180,180],[-67,180,68,65],[-67,180,68,180],[-67,180,180,65],[-67,180,180,180],[-67,180,180,-65],[-67,180,-68,180],[-67,180,-68,-65],[-62,-68,180,65],[-62,-68,180,180],[-62,-68,180,-65],[-62,-68,-68,180]])
        self.AAtypes['ARG'] = AAtype('ARG',[['N','CA','CB','CG'],['CA','CB','CG','CD'],['CB','CG','CD','NE'],['CG','CD','NE','CZ']],[[62,180,65,85],[62,180,65,-175],[62,180,180,85],[62,180,180,180],[62,180,180,-85],[62,180,-65,175],[62,180,-65,-85],[-177,65,65,85],[-177,65,65,-175],[-177,65,180,85],[-177,65,180,180],[-177,180,65,85],[-177,180,65,-175],[-177,180,65,-105],[-177,180,180,85],[-177,180,180,180],[-177,180,180,-85],[-177,180,-65,105],[-177,180,-65,175],[-177,180,-65,-85],[-67,180,65,85],[-67,180,65,-175],[-67,180,65,-105],[-67,180,180,85],[-67,180,180,180],[-67,180,180,-85],[-67,180,-65,105],[-67,180,-65,175],[-67,-167,-65,-85],[-62,-68,180,85],[-62,-68,180,180],[-62,-68,180,-85],[-62,-68,-65,175],[-62,-68,-65,-85]])
        self.AAtypes['HID'] = AAtype('HID',[['N','CA','CB','CG'],['CA','CB','CG','ND1']],[[62,-75],[62,80],[-177,-165],[-177,-80],[-177,60],[-65,-70],[-65,165],[-65,80]])
        self.AAtypes['HIE'] = AAtype('HIE',[['N','CA','CB','CG'],['CA','CB','CG','ND1']],[[62,-75],[62,80],[-177,-165],[-177,-80],[-177,60],[-65,-70],[-65,165],[-65,80]])
        self.AAtypes['HIP'] = AAtype('HIP',[['N','CA','CB','CG'],['CA','CB','CG','ND1']],[[62,-75],[62,80],[-177,-165],[-177,-80],[-177,60],[-65,-70],[-65,165],[-65,80]])
        self.AAtypes['HIS'] = AAtype('HIS',[['N','CA','CB','CG'],['CA','CB','CG','ND1']],[[62,-75],[62,80],[-177,-165],[-177,-80],[-177,60],[-65,-70],[-65,165],[-65,80]])
        self.AAtypes['ASP'] = AAtype('ASP',[['N','CA','CB','CG'],['CA','CB','CG','OD1']],[[62,-10],[62,30],[-177,0],[-177,65],[-70,-15]])
        self.AAtypes['GLU'] = AAtype('GLU',[['N','CA','CB','CG'],['CA','CB','CG','CD'],['CB','CG','CD','OE1']],[[62,180,-20],[70,-80,0],[-177,65,10],[-177,180,0],[-177,-80,-25],[-65,85,0],[-67,180,-10],[-65,-65,-40]])
        self.AAtypes['ASN'] = AAtype('ASN',[['N','CA','CB','CG'],['CA','CB','CG','OD1']],[[62,-10],[62,30],[-174,-20],[-177,30],[-65,-20],[-65,-75],[-65,120]])
        self.AAtypes['GLN'] = AAtype('GLN',[['N','CA','CB','CG'],['CA','CB','CG','CD'],['CB','CG','CD','OE1']],[[62,180,20],[70,-75,0],[-177,65,-100],[-177,65,60],[-177,180,0],[-65,85,0],[-67,180,-25],[-65,-65,-40],[-65,-65,100]])




    def changeDihedral(self, dihNum, newVal):
        if(len(self.rotResList) == 1):
            aa = self.curAAtype
            if(dihNum < len(aa.dihAtomNames)):
                AAtype.setDihVal("_kropkresi", aa.dihAtomNames[dihNum],dihNum, newVal);
        else:
            print("Please select one protein residue")

    def clearH(self):
        if reduceExe:
            seles = self.h_sel.getvalue()
            seleStr = " or ".join(seles)
            
            if seleStr:
                cmd.do('remove (hydro and ('+seleStr+'))')
            else:
                print('Could not find selection')
        else:
            print(reduceError)

    def addH(self):
        if reduceExe: 
            seles = self.h_sel.getvalue()
            for sele in seles:
                if sele != '':
                    pdbStr = cmd.get_pdbstr(sele)
                    args = '"'+reduceExe+'"' + ' -BUILD -DB '+ '"'+reduceDB+'" -'
                    print(args+" ")
                    p = subprocess.Popen(args,shell=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    newpdb = p.communicate(pdbStr.encode())[0]
                    mynewsel = sele + '_H'
                    if self.h_newSel.getvalue() != '':
                        mynewsel = self.h_newSel.getvalue()
                    if self.replVar.get() == 1:
                        mynewsel = sele
                        cmd.delete(sele)
                    cmd.read_pdbstr(newpdb, mynewsel)
                else:
                    print("Could not determine selection")
        else:
            print(reduceError)

    def getSels(self):
        sels = cmd.get_names("public_selections");
        fakeSels = ["sele","pk1","pk2","pkbond","pkmol","pkresi","pkchain","pkobject"]
        for sel in fakeSels:
            if sel in sels:
                sels.remove(sel)
        return sels;

    def loadDotsButton(self):
        if probeExe:
            loadDotsFromSels(self.d_sel1.get(), self.d_sel2.get(), self.d_name.getvalue(),
                         self.d_params.getvalue(),float(self.dotSizeEntry.getvalue())/100.,
                         float(self.lineSizeEntry.getvalue()),self.d_selfVar.get())
        else:
            print(probeError)

    def execute(self,result):
        if result == 'OK':
            self.remote(self.pdbCode.get())
        elif result == 'Close':
            self.quit()
        elif result == 'About':
            print(about)
        else:
            self.quit()
                
    def quit(self):
        self.dotQueue.put("stop")
        self.hideRotDots()
        if __name__ == '__main__':
            self.parent.destroy()
        else:
            self.dialog.destroy()

    def detectLostFocus(self,event):
        if (event.widget.widgetName == "toplevel"):
            print("Lost Focus", event.widget.widgetName)

    def updateSels(self,event):
        
        if (event.widget.widgetName == "toplevel"):
            selections = self.getSels()
            
            #set objects in box for adding Hs
            objects = cmd.get_names_of_type("object:molecule");
            if list(self.h_sel.get()) != list(objects):
                self.h_sel.setlist(objects)
            
            selections = objects+selections
            for cBox in self.cBoxes:
                listEles = cBox.component('scrolledlist').get()
                #listEles = cBox.get()
                if list(selections) != list(listEles):
                    cBox.setlist(selections)
            
            #Rotamer Dihedral Code
            if('pkresi' in cmd.get_names("public_selections")):
                cmd.select('_kropkresi','pkresi')       
                myspace = {'resName': [], 'resNum': []}
                cmd.iterate('_kropkresi and name CA', 'resName.append(resn);resNum.append(resi)',  space=myspace)
                
                if(list(myspace['resName']) != list(self.rotResList) or list(myspace['resNum']) != list(self.rotResIList)):
                    self.rotResList = myspace['resName']
                    self.rotResIList = myspace['resNum']
                    if(len(self.rotResList) == 1):
                        resn = self.rotResList[0].upper()
                    
                        if(resn in self.AAtypes):
                            aa = self.AAtypes[resn]
                            self.curAAtype = aa
                            numDih = len(aa.dihAtomNames)
                            
                            #set orig dihVals
                            self.origRotVals = []
                            for atoms in self.AAtypes[resn].dihAtomNames:
                                self.origRotVals.append(cmd.get_dihedral('_kropkresi and name ' + atoms[0], '_kropkresi and name ' + atoms[1], '_kropkresi and name ' + atoms[2], 
                                                 '_kropkresi and name ' + atoms[3]))
                                
                            for i,val in enumerate(self.origRotVals):
                                self.dihScale[i].grid()
                                self.dihScale[i].set(val)
                            for i in range(numDih,4):
                                self.dihScale[i].grid_remove()    
                                
                            self.rotsToAdd = []
                            self.rotsToAdd.append("orig")
                            for vals in self.AAtypes[resn].dihVals:
                                self.rotsToAdd.append(vals)
                                
                            self.rotBox.setlist(self.rotsToAdd)
                            resStr = self.rotResList[0] + " " + str(self.rotResIList[0])
                            self.resLabel.config(text=resStr)
                            self.dotCheckCB()    
                                    
                        else:
                            self.clearRot()
                    else:
                        self.clearRot()
                    
            

    def clearRot(self):
        for i in range(4):
            self.dihScale[i].grid_remove()
        self.hideRotDots()
        self.rotBox.setlist([])
        self.resLabel.config(text="")

    def remote(self,pdbCode):
        pdbCode = pdbCode.upper()
        try:
            pdbFile = urllib.request.urlopen('http://www.rcsb.org/pdb/cgi/export.cgi/' +
                                       pdbCode + '.pdb.gz?format=PDB&pdbId=' +
                                       pdbCode + '&compression=gz')
            cmd.read_pdbstr(zlib.decompress(pdbFile.read()[22:], -zlib.MAX_WBITS), pdbCode)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            tkinter.messagebox.showerror('Invalid Code',
                                   'You entered an invalid pdb code:' + pdbCode)
def get_binary_suffix_windows(name):
    if not name.endswith('.exe'):
        name = name.join(name, '.exe')
    return name

def get_binary_suffix_posix(name):
    if name.endswith('.exe'):
        name = name[:-4]
    return name

suffix_getter = {
    'Linux':get_binary_suffix_posix,
    'Windows':get_binary_suffix_windows,
    'Darwin':get_binary_suffix_posix
}
            
def verify(name):
    scriptdir = os.path.dirname(os.path.abspath(__file__))+"/"
    searchDirs = [scriptdir]
    #searchDirs.extend(string.split(os.environ["PATH"], os.pathsep))
    osname = platform.system()
    name = suffix_getter.get(osname)(name)
   
    for d in searchDirs:
        d = d+osname+'/'
        f = os.path.join( d, name )  # make path/name.py
        #print "trying",f
        if os.path.exists(f):
            return f
        elif name.endswith('.exe'):
            f = os.path.join( d, name[:-4] )  # make path/name.py
            #print "trying",f
            if os.path.exists(f):
                return f
        elif name.endswith('.py'):
            f = os.path.join( d, name[:-3] )  # make path/name.py
            #print "trying",f
            if os.path.exists(f):
                return f
        
    print("Could not find default location for file: %s" % name)
    return ""

def findExecutables():
    global probeExe
    global reduceExe
    global reduceDB
    probeExe = verify("probe.exe")
    reduceExe = verify("reduce.exe")

    if probeExe:
        print("Found: "+probeExe)
    if reduceExe:
        print("Found: "+reduceExe)
        if "REDUCE_HET_DICT" in os.environ:
            reduceDB = os.environ["REDUCE_HET_DICT"]
        else:
            reduceDB = os.path.dirname(reduceExe)+os.sep+'reduce_wwPDB_het_dict.txt'


#run this when the plugin is first loaded so "loadDotsFromSels" 
findExecutables()

colorDict = {'sky': [COLOR, 0.0, 0.76, 1.0 ],
             'sea': [COLOR, 0.0, 0.90, 0.5 ],
             'yellowtint': [COLOR, 0.88, 0.97, 0.02 ],
             'hotpink': [COLOR, 0.90, 0.40, 0.70 ],
             'greentint': [COLOR, 0.50, 0.90, 0.40 ],
             'blue': [COLOR, 0.0, 0.0, 1.0 ],
             'green': [COLOR, 0.0, 1.0, 0.0 ],
             'yellow': [COLOR, 1.0, 1.0, 0.0 ],
             'orange': [COLOR, 1.0, 0.5, 0.0],
             'red': [COLOR, 1.0, 0.0, 0.0],
             'gray': [COLOR, 0.9, 0.9, 0.9] }

def loadDotsFromSels(sel1, sel2, dotsName='dots', extraParams="", dotSize=0,lineSize=1,doSelf=0):
    """
    DESCRIPTION
     
        "loadDotsFromSels" creates a contact dot group for the interaction between two selections/objects.
     
    USAGE
        
        loadDotsFromSels sel1, [sel2 [, dotsName [, extraParams [, dotSize [, lineSize [, doSelf ]]]]]]
     
    ARGUMENTS
     
        sel1 = string: first atom selection
     
        sel2 = string: second atom selection
     
        dotsName = string: name of dots group 
        
        extraParams = string: extra parameters that are passed on to probe
     
        dotSize = float: size to render the probe dots
     
        lineSize = float: size to render the clash lines

        doSelf = int: if not 0 will calculate dots within sel1 only
     
    EXAMPLES
     
        loadDotsFromSels prot, ligand, prot_lig_dots
     
        loadDotsFromSels sel1, doSelf=1
     
    NOTES
     
        This function is a wrapper for the program probe that can be used to display
        contact dots within pymol. By default MinOccupancy is set to 0.0 so even
        atoms with zero occupancy will be included in the calculation. 
        
    """
    
    pdb1 = cmd.get_pdbstr(sel1).splitlines()
    if(doSelf==0):
        pdb2 = cmd.get_pdbstr(sel2).splitlines()
    
        for pdb, name in zip([pdb1,pdb2], ["FIRS", "SECO"]):
            atom = re.compile("^(ATOM  |HETATM)")
            for i in range(0,len(pdb)):
                if(atom.match(pdb[i])):
                    pdb[i] = pdb[i][:72] + name + pdb[i][76:81]
        
        pdbStr = pdb1 + pdb2
        pdbStr = "\n".join(pdbStr)
    
        #get the results of the probe dots
        #args = 'probe -MinOccupancy0.0 -MC -both "'+probeStr[0]+'" "'+probeStr[1]+'" -'
        args = '"'+probeExe+'" '+extraParams+' -MinOccupancy0.0 -MC -both "SEGFIRS" "SEGSECO" -'
    else:
        pdbStr = pdb1
        pdbStr = "\n".join(pdbStr)
        args = '"'+probeExe+'" '+extraParams+' -MinOccupancy0.0 -MC -self "all" -'

    
    print(args)
    
    p = subprocess.Popen(args,shell=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    dots = p.communicate(pdbStr.encode())[0]
    #p = subprocess.Popen('probe -both "1" "3" -',shell=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    #stdout_val = p.communicate("ATOM      1  N   GLY     1       7.920  25.950  15.720  1.00  0.00")[0]

    #f = open(dotsName+'.txt', 'w')
    #f.write(dots)
    #loadDots(dots,dotsName,dotSize,lineSize)
    cmd.async_("loadDots",dots,dotsName,dotSize,lineSize)

cmd.extend("loadDotsFromSels",loadDotsFromSels)

def loadDotsFromSelsAsync(sel1, sel2, dotsName='dots', extraParams="", dotSize=0,lineSize=1,doSelf=0):
    cmd.async_('loadDotsFromSels', sel1, sel2, dotsName=dotsName, extraParams="", dotSize=dotSize, lineSize=lineSize, doSelf=doSelf)
cmd.extend("loadDotsFromSelsAsync",loadDotsFromSelsAsync)
    
def drawDots (dotList, vectorList, dotSize = 0, lineSize = 1 ):
    obj = []
    for pair in dotList:
        color = pair[0]
        coords = pair[1]
        
        colorToAdd = colorDict[color]
        if dotSize <= 0:
            obj.extend([BEGIN, POINTS])
            obj.extend(colorToAdd)
            obj.extend([VERTEX, float(coords[0]), float(coords[1]), float(coords[2])])
            obj.append(END)
        else:
            obj.extend(colorToAdd)
            obj.extend([SPHERE, float(coords[0]), float(coords[1]), float(coords[2]), dotSize])
        
    for pair in vectorList:
        color = pair[0]
        coords1 = pair[1]
        coords2 = pair[2]
        colorToAdd = colorDict[color]
        obj.extend([LINEWIDTH, lineSize])
        obj.extend([BEGIN, LINES])
        obj.extend(colorToAdd)
        obj.extend([VERTEX, float(coords1[0]), float(coords1[1]), float(coords1[2])])
        obj.extend([VERTEX, float(coords2[0]), float(coords2[1]), float(coords2[2])])
        obj.append(END)
    
    return obj

def loadDotsFromFile(file,dotsName='dots'):
        print(file)
        
        #slurp up the data file
        input = open(file,'r')
        fp = input.read()
        input.close()
    
        #call loadDots
        loadDots(fp,dotsName)
           
def loadDots(data,dotsName='dots', dotSize=0, lineSize=1):
    dots = []
    dotList = []
    vectorList = []
    data = data.decode().split('\n')

    dotDict = {"small_overlap":[], "bad_overlap":[],"vdw_contact":[],"H-bonds":[]}
    vectorDict = {"small_overlap":[], "bad_overlap":[],"vdw_contact":[],"H-bonds":[]}

    dotlistRE = re.compile('dotlist.*master=\{([\w\-\s]+)\}')
    vectorlistRE = re.compile('vectorlist.*master=\{([\w\-\s]+)\}')
    regexp1 = re.compile('\}([\w]+).* ([\-\d\.]+,[\-\d\.]+,[\-\d\.]+)')
    regexp2 = re.compile('\}([\w]+).* ([\-\d\.]+,[\-\d\.]+,[\-\d\.]+).*\}.* ([\-\d\.]+,[\-\d\.]+,[\-\d\.]+)') 
    
    master = ""
    for line in data:
        m = dotlistRE.search(line)
        if m:
            master = m.group(1)
            master = master.replace(" ", "_")
            if not master in dotDict:
                dotDict[master] = []
            if not master in vectorDict:
                vectorDict[master] = []
        m = vectorlistRE.search(line)
        if m:
            master = m.group(1)
            master = master.replace(" ", "_")
            if not master in vectorDict:
                vectorDict[master] = []
            if not master in dotDict:
                dotDict[master] = []
        m = regexp1.search(line)
        if m:
            coords = m.group(2).split(',')
            tmpList = [m.group(1), coords]
            dotDict[master].append(tmpList)
        m = regexp2.search(line)
        if m:
            coords1 = m.group(2).split(',')
            coords2 = m.group(3).split(',')
            tmpList = [m.group(1), coords1, coords2]
            vectorDict[master].append(tmpList)
    
    newObjects = ""  
    for category in dotDict:
        objectName = category+'_'+dotsName
        newObjects = newObjects+' '+objectName      
        obj = drawDots(dotDict[category], vectorDict[category],dotSize,lineSize)
        cmd.load_cgo(obj,objectName,1.0,zoom=0)
    
    #group the dots I just made
    cmd.group(dotsName, newObjects)
    
    #print "Loaded Dots..."
    
    return
cmd.extend('loadDots', loadDots)
#cmd.extend('loadDotsFromFile', loadDotsFromFile)

class AAtype:
    dihAtomNames = []
    dihVals = []
    name = ""
    
    def __init__(self,name, dihAtomNames,dihVals):
        self.dihVals = dihVals 
        self.dihAtomNames = dihAtomNames
        self.name = name

    @staticmethod
    def setDihVal(sele,atomNames,dih,val):
        cmd.set_dihedral(sele +" and name "+atomNames[0], sele +" and name "+atomNames[1], 
                             sele +" and name "+atomNames[2], sele +" and name "+atomNames[3], val,quiet=1)

    def setRotamer(self,sele,rotNum):
        for dih in range(len(self.dihAtomNames)):
            self.setDihVal(sele,self.dihAtomNames[dih],dih,self.dihVals[rotNum][dih])
            
class ThreadDots(threading.Thread):
    """Threaded way to create dots"""

    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue
        self.stop = threading.Event()    

    def run(self):
        while True:
            #get cur job from queue
            job = self.queue.get()
            
            if job == "stop":
                return
            #skip job if there is another one to do
            if self.queue.empty():
                #cmd.delete("scRotDots")
                loadDotsFromSels("_kropkresi", job+" and not _kropkresi", "scRotDots") 
                
                
            self.queue.task_done()

def computePPI(selection1, selection2, radius=6):
    cmd.select(selection1+'_PPI', selection1+' and byres '+selection2+' around '+str(radius))
    cmd.select(selection2+'_PPI', selection2+' and byres '+selection1+' around '+str(radius))
cmd.extend("computePPI", computePPI)

def autoEnsembleDots():
    for model in cmd.get_object_list():
        pattern = model[:model.index(".")]
        number = model[model.index(".")+1:]
        sequenceDict = dict((x.strip(), y.strip()) \
                       for x, y in (element.split('-') \
                       for element in pattern.split('_')))
        chain = ""
        resiList = []
        for resi in list(sequenceDict.keys()):
            chain = resi[0]
            resnum = resi[1:]
            resiList.append(resnum)
        selection = "chain "+chain+" and resi "+"+".join(resiList)
            
    loadEnsembleDots(pattern+".*", selection, 1, len(cmd.get_object_list())+1, len(number))
    util.cbac('chain B')
    util.cbag('chain A')
cmd.extend('autoEnsemble', autoEnsembleDots)

def multiStateEnsembleDots(startConf=1, endConf=10):
    startConf = int(startConf)
    endConf = int(endConf)
    print("Generating dots for conformations "+str(startConf)+" through "+str(endConf)+"...")
    needSplit = False
    pattern = "(error)"
    firstObj = cmd.get_object_list()[0]
    pattern = firstObj
    for index in range(startConf, endConf+1):
        if pattern+"_"+str(index) not in cmd.get_object_list():
            needSplit = True
            break
    if needSplit:
        # assume one multi-state object is first in the list.
        # cmd.async_("split_states", cmd.get_object_list()[0])
        cmd.split_states(cmd.get_object_list()[0], startConf, endConf)
    orientResiList = []
    selection = "(error)"
    number = "(error)"
    chain = "(error)"
    model = cmd.get_object_list()[1]
    separatorIndex = model.rindex("_")
    pattern = model[:separatorIndex]
    number = model[separatorIndex+1:]
    print("Pattern: "+pattern)
    print("Number: "+number)
    sequenceDict = dict((x.strip().replace("seq.B",""), y.strip()) \
                   for x, y in (element.split('_') \
                   for element in pattern.split('_B')))
    chain = "B"
    resiList = []
    for resi in list(sequenceDict.keys()):
        resnum = resi[0:]
        resiList.append(resnum)
    selection = "chain "+chain+" and resi "+"+".join(resiList)
    orientResiList = resiList
            
    loadEnsembleDots(pattern+"_*", selection, startConf, endConf+1, len(number))
    #cmd.async_("loadEnsembleDots", pattern+"_*", selection, startConf, startConf+numConfs, len(number))
    colorMultiEnsemble(orientResiList)
    #cmd.async_("colorMultiEnsemble", orientResiList)
cmd.extend('multiStateEnsemble', multiStateEnsembleDots)

def multiEnsembleAsync(startConf=1, endConf=10):
    cmd.async_('multiStateEnsemble', startConf=startConf, endConf=endConf)
cmd.extend('multiEnsemble', multiEnsembleAsync)

def renderMultiEnsemble(mutSel):
    util.cbac('chain B')
    util.cbag('chain A')
    cmd.show('sticks', mutSel)
    cmd.show('lines', "byres "+mutSel+" around 6")
    cmd.hide('ribbon')
    cmd.show('cartoon')
cmd.extend('renderMultiEnsemble', renderMultiEnsemble)


def colorMultiEnsemble(orientResiList):
    util.cbac('chain B')
    util.cbag('chain A')
    cmd.orient('chain B and resi '+"+".join(orientResiList))
    cmd.hide('ribbon')
    cmd.show('cartoon')
cmd.extend('colorMultiEnsemble', colorMultiEnsemble)

def loadEnsembleDots(pattern, selection, start, end, padding, radius=5):
    for i in [str(id0).rjust(int(padding), '0') for id0 in range(int(start), int(end))]: 
        object_selection = pattern.replace("*",i)
        if str(i)+'dots' in cmd.get_names('objects'):
            print("dots object for "+str(i)+" already present, skipping...")
            continue
        print("processing selection "+object_selection+" for residues within "+str(radius)+" of "+selection)
        loadDotsFromSels(object_selection+" and "+selection, object_selection+" and byres "+selection+" around "+str(radius), str(i)+"dots")
    cmd.show("sticks", selection)
    cmd.show("lines", "byres "+selection+" around 5")
    cmd.orient("byres "+selection+" around 5")
cmd.extend("loadEnsembleDots", loadEnsembleDots)

def loadDotsAroundModel(model, selection, radius=4):
    loadDotsFromSels("%s and byres %s" % (model, selection), "%s and byres (%s and byres %s) around %d" % (model, model, selection, radius), model+"dots")
cmd.extend("loadDotsAroundModel", loadDotsAroundModel)
    
            
def loadDotsForSelf(selection, colorResidues=False):
    selectionName = selection.replace(" ","_")
    if selectionName == 'sele':
        defaultCounter = len(cmd.get_names('public_selections'))
        selectionName =  "default"+str(defaultCounter)
    identifier = selectionName
    print("selection: "+selection)
    print("Selection name: "+selectionName)
    cmd.select(selectionName, selection)
    loadDotsFromSels(selection, selection, identifier+"dots", doSelf=1)
    if colorResidues:
        util.cbc()
        util.cbag(selectionName)
    cmd.show("sticks", selection)
    cmd.hide("everything", "hydrogens")
    cmd.orient(selectionName)
    
cmd.extend("loadDotsForSelf",loadDotsForSelf)

def dotify(targetObject):
    objects = cmd.get_object_list()
    cmd.keyword['cnbc'][0]()
    if targetObject in objects:
        loadDotsFromSels('%s and chain A' % targetObject, '%s and chain B' % targetObject, '%s_dots' % targetObject)
cmd.extend("dotify", dotify)

def loadDotsForResidueShell(selection, radius, colorResidues=False):
    """
    DESCRIPTION

        "loadDotsFromSels" creates a contact dot group for the interaction between two selections/objects.

    USAGE

        loadDotsFromSels sel1, [sel2 [, dotsName [, extraParams [, dotSize [, lineSize [, doSelf ]]]]]]

    ARGUMENTS

        sel1 = string: first atom selection

        sel2 = string: second atom selection

        dotsName = string: name of dots group 

        extraParams = string: extra parameters that are passed on to probe

        dotSize = float: size to render the probe dots

        lineSize = float: size to render the clash lines

        doSelf = int: if not 0 will calculate dots within sel1 only

    EXAMPLES

        loadDotsFromSels prot, ligand, prot_lig_dots

        loadDotsFromSels sel1, doSelf=1

    NOTES

        This function is a wrapper for the program probe that can be used to display
        contact dots within pymol. By default MinOccupancy is set to 0.0 so even
        atoms with zero occupancy will be included in the calculation. 

    """
    print("Hello World!")
    selectionName = selection.replace(" ","_")
    if selectionName == 'sele':
        defaultCounter = len(cmd.get_names('public_selections'))
        selectionName =  "default"+str(defaultCounter)
    identifier = selectionName
    shellName = selectionName+"shell" 
    print("selection: "+selection)
    print("Selection name: "+selectionName)
    print("Shell name: "+shellName)
    cmd.select(selectionName, selection)
    cmd.select(shellName, "byres "+selection+" around "+str(radius))
    loadDotsFromSels(selection, shellName, identifier+"dots")
    if colorResidues:
        util.cbc()
        util.cbac(shellName)
        util.cbag(selectionName)
    cmd.show("sticks", selection)
    cmd.show("lines", shellName)
    cmd.hide("everything", "hydrogens")
    cmd.orient(shellName)

def probe_dots(self_cmd, sele):
    if 'loadDotsForResidueShell' not in  self_cmd.keyword:
        print("Trying to initialize plugins.")
        import pymol.plugins
        pymol.plugins.initialize(-1)
    rsele = repr(sele)
    sele_morphs = lambda x: [[ 1, a, 'cmd.keyword[\'loadDotsFromSels\'][0](%s,%s,%s)' % (rsele, repr(a),
            "\'"+rsele[1:-1]+repr(a)[1:-1]+"dots\'") ] for a in x if a != sele]
    sele_ranges= lambda x: [[ 1, "within "+str(a)+" Angstroms", 
            'cmd.keyword[\'loadDotsForResidueShell\'][0](%s,%s)' % (rsele, repr(a)) ] for a in x if a != sele]
    return [[ 2, 'Dots:'       ,''                        ],
                  [ 1, 'with itself', 'cmd.keyword[\'loadDotsForSelf\'][0]('+rsele+')' ],
                  [ 1, 'with neighbors', sele_ranges(list(range(2,7,2))) ],
                  [ 1, 'with selection', sele_morphs(self_cmd.get_names('public_selections')[:25]) ],
                  [ 1, 'dotify', 'cmd.keyword[\'dotify\'][0]('+rsele+')' ],
              ]

def gavilan_cmd(self_cmd, sele):
    rsele = repr(sele)
    return [[ 2, 'Design:'       ,''                        ],
                  [ 1, 'set mutable', 'cmd.keyword[\'setmutable\'][0]('+rsele+')'],
                  [ 1, 'set flexible', 'cmd.keyword[\'setflexible\'][0]('+rsele+')'],
                  [ 1, 'define strand', 'cmd.keyword[\'setStrand\'][0]('+rsele+')'],
                  [ 1, 'set backbone flexibility...', [
                        [ 2, 'BB Flex', ''],
                        [ 1, 'CATS', 'cmd.keyword[\'setBBFlex\'][0](\'cats\','+rsele+')'],
                        [ 1, 'DEEPer', 'cmd.keyword[\'setBBFlex\'][0](\'deeper\','+rsele+')'],
                  ]],
                  [ 1, 'export search parameters', [
                        [ 2, 'Design type', ''],
                        [ 1, 'K* (affinity)', 'cmd.keyword[\'generateConfigFile\'][0](\'markstar\')'],
                        [ 1, 'GMEC (stability)', 'cmd.keyword[\'generateConfigFile\'][0](\'gmec\')'],
                  ]],
           ]

def setBBFlex(flexType, selection):
    print("Adding "+flexType+" flexibility to "+selection)
    cmd.show("sticks", selection)
    if flexType in cmd.get_names('public_selections'):
        cmd.select(flexType, selection+" or "+flexType)
    else:
        cmd.select(flexType, selection)
    cmd.group('bb_flex', 'cats deeper')
    cmd.select("none", "none")

cmd.extend("setBBFlex", setBBFlex)

def setStrand(selection):
    print("defining strand "+selection)
    cmd.show("ribbon", selection)
    strandsSoFar = cmd.get_names('public_selections')
    index = 1
    strandName = "strand"+str(index)
    while strandName in strandsSoFar:
        index = index+1
        strandName = "strand"+str(index)
    cmd.select(strandName, selection)
    cmd.select("none", "none")

cmd.extend("setStrand", setStrand)


def setmutable(selection):
    print("setting mutations for "+selection)
    cmd.show("sticks", selection)
    util.cbao(selection)
    if 'mutable' in cmd.get_names('public_selections'):
        cmd.select("mutable", selection+" or mutable")
    else:
        cmd.select("mutable", selection)
    cmd.select("none", "none")

cmd.extend("setmutable", setmutable)

def setflexible(selection):
    print("setting flexiblity for "+selection)
    cmd.show("lines", selection)
    util.cbac(selection)
    if 'flexible' in cmd.get_names('public_selections'):
        cmd.select("flexible", selection+" or flexible")
    else:
        cmd.select("flexible", selection)
    cmd.select("none", "none")

cmd.extend("setflexible", setflexible)

def generateConfigFile(runType):
    my_dict = { 'mutable' : [], 'flexible': [], 'strands':{}, 'bb_cats':[], 'bb_deeper':[]}
    print("Generating design configuration file for "+runType+" run")
    
    # check for relevant parameters
    names = cmd.get_names('public_selections')
    if "mutable" not in names and "flexible" not in names:
        print("ERROR: at least one residue must be flexible or mutable")
        return
    if "mutable" in names:
        cmd.iterate("(name ca and mutable)", "mutable.append([chain+resi, resn])", space=my_dict)
    if "flexible" in names:
        cmd.iterate("(name ca and flexible)", "flexible.append([chain+resi, resn])", space=my_dict)
    if "cats" in names:
        cmd.iterate("(name ca and cats)", "bb_cats.append([chain+resi, resn])", space=my_dict)
    if "deeper" in names:
        cmd.iterate("(name ca and deeper)", "bb_deeper.append([chain+resi, resn])", space=my_dict)
    index = 1
    strandName = "strand"+str(index)
    while strandName in names:
        my_dict['strands'][strandName] = []
        cmd.iterate("(name ca and "+strandName+")", strandName+".append(chain+resi)", space=my_dict['strands'])
        index = index+1
        strandName = "strand"+str(index)

    print("Mutable:")
    print(my_dict['mutable'])
    print("Flexible:")
    print(my_dict['flexible'])
    print("Backbone flexibility:")
    print("CATS:")
    print(my_dict['bb_cats'])
    print("DEEPer:")
    print(my_dict['bb_deeper'])
    print("Defined strands:")
    print(my_dict['strands'])

    filename = asksaveasfilename(initiadir="/", title="Select Config File Save Location", \
        filetypes=(("cfg", "*.cfg"),("All files", "*.*")))
    print("Saving config file to ["+filename+"]")

    with open(filename, 'w+') as configFile:
        print("runtype "+runType)
        configFile.write("# config file auto-generated by OSPREY Design Plugin for PyMol\n")
        configFile.write("runtype "+runType+"\n")
        print("# mutable")
        configFile.write("# mutable residues\n")
        for (resi, resn) in my_dict['mutable']:
            print(resi)
            configFile.write(resi+"\n")
        print("# flexible")
        configFile.write("# flexible residues\n")
        for (resi, resn) in my_dict['flexible']:
            print(resi)
            configFile.write(resi+" addWTRotamers continuousRotamers\n")
        for strandDef in my_dict['strands']:
            configFile.write(strandDef+" "+" ".join(my_dict['strands'][strandDef])+"\n")
            print((strandDef+" "+" ".join(my_dict['strands'][strandDef])))

cmd.extend("generateConfigFile", generateConfigFile)

def loadDesignFromConfigFile():
    filename = askopenfilename(initiadir="/", title="Select Config File to Load", \
        filetypes=(("cfg", "*.cfg"),("All files", "*.*")))
    with open(filename, 'r+') as configFile:
        for count, line in enumerate(configFile):
            if line.startswith('#'):
                continue
            if '#' in line:
                line = line.split('#', 1)[0]
            m = re.match("(\w?\d+) ?((((\w\w\w)|(WT))\s)+)?(addWTRotamers)? ?(continuousRotamers)? ?(addWTRotamers)?", line) 
            if m is not None:
                [residue_number, allowed_AAs, last_AA, last_WT_or_AA, last_non_WT, WT, \
                    add_wild_type_rotamers_string, continuous_rotamers_string, \
                    add_wild_type_rotamers_backup_string] = m.groups()         
                if allowed_AAs is None or ( len(allowed_AAs) < 2 and 'WT' in allowed_AAs ):
                    setflexible('chain '+residue_number[0]+' and resi '+residue_number[1:])
                else:
                    setmutable('chain '+residue_number[0]+' and resi '+residue_number[1:])
            if line.startswith('strand'):
                strand_residues = line.strip().split(" ")[1:]
                for index, residue_number in enumerate(strand_residues):
                    strand_residues[index] = "(chain "+residue_number[0]+" and resi "+residue_number[1:]+")"
                setStrand("+".join(strand_residues))

cmd.extend("loadDesignFromConfigFile", loadDesignFromConfigFile)



def rewritePymolMenu(self):
    print("Added probe dots command to context menu.")
    menu.PrePIVCompute = menu.compute
    menu.probe_dots = probe_dots
    def computeWithDotsMenu(self_cmd, sele):
        output = menu.PrePIVCompute(self_cmd, sele)
        output.append([ 1, 'probe dots', menu.probe_dots(self_cmd, sele)])
        return output
    menu.compute = computeWithDotsMenu

cmd.extend("loadDotsForResidueShell",loadDotsForResidueShell)

