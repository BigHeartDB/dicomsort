import sys
import wx
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin,CheckListCtrlMixin,TextEditMixin

class AutoWidthCheckListCtrl(wx.ListCtrl,ListCtrlAutoWidthMixin,
        CheckListCtrlMixin,TextEditMixin):

    def __init__(self,parent):
        wx.ListCtrl.__init__(self,parent,-1,style=wx.LC_REPORT)
        ListCtrlAutoWidthMixin.__init__(self)

        # The order here matter because we favor Check over Edit
        TextEditMixin.__init__(self)
        CheckListCtrlMixin.__init__(self)

        self.editColumns = []

    def GetCheckedIndexes(self):
        return [i for i in range(self.ItemCount) if self.IsChecked(i)]

    def SetColumnEditable(self,column):
        if column not in self.editColumns:
            self.editColumns.append(column)

    def SetColumnLocked(self,column):
        if column in self.editcolumns:
            self.editColumns.remove(column)

    def SetStringItems(self,items):
        self.DeleteAllItems()

        for item in items:
            if isinstance(item,str):
                item = [item,]

            row = self.InsertStringItem(sys.maxint,item[0])

            for col in range(1,len(item)):
                self.SetStringItem(row,col,item[col])

    def CheckItems(self,itemIndex):
        [self.CheckItem(index) for index in itemIndex]

    def GetCheckedItems(self,col=None):
        return [self.GetItemList(r,col) for r in self.GetCheckedIndexes()]

    def UnCheckAll(self):
        [self.CheckItem(index,False) for index in range(self.ItemCount)]

    def GetCheckedStrings(self,col=None):
        return [self.GetStringItem(r,col) for r in self.GetCheckedIndexes()]

    def GetItemList(self,column = None):
        if column == None:
            return [self.GetItemList(c) for c in range(self.ColumnCount)]
        else:
            return [self.GetItem(r,column) for r in range(self.ItemCount)]

    def GetStringItem(self,row,column=None):
        if column == None:
            return [self.GetStringItem(row,c) for c in range(self.ColumnCount)]
        else:
            return self.GetItem(row,column).Text

    def OpenEditor(self,column,row):
        """
        Overloaded method to render certain columns un-editable
        """
        if column not in self.editColumns:
            return
        else:
            # Call superclass edit method
            TextEditMixin.OpenEditor(self,column,row)

class AnonymizeList(AutoWidthCheckListCtrl):

    def __init__(self,*args,**kwargs):
        AutoWidthCheckListCtrl.__init__(self,*args,**kwargs)

        self.InsertColumn(0,'DICOM Property',width=200)
        self.InsertColumn(1,'Replacement Value')

        self.SetColumnEditable(1)

    def GetReplacements(self):
        res = dict()

        for row in self.GetChangedIndex():
            res[self.GetStringItem(row,0)] = self.GetStringItem(row,1)

        return res

    def GetAnonDict(self):

        anonDict = dict()

        for key,val in self.GetCheckedStrings():
            anonDict[key] = val

        return anonDict

    def ClearColumn(self,col):
        [self.SetStringItem(i,col,'') for i in range(self.ItemCount)]

    def FindStrings(self,strings,col=0):
        strings = [unicode(string) for string in strings]

        fields = [item.Text for item in self.GetItemList(col)]

        inds = list()

        for string in strings:
            try:
                inds.append(fields.index(unicode(string)))
            except ValueError:
                inds.append(None)

        return inds

    def SetReplacements(self,dictionary):
        keys = dictionary.keys()
        inds = self.FindStrings(keys,0)

        for i,row in enumerate(inds):
            if row == None:
                continue

            self.SetStringItem(row,1,dictionary[keys[i]])

    def CheckStrings(self,strings,col=0):
        print self.FindStrings(strings,col)
        inds = [ind for ind in self.FindStrings(strings,col) if ind != None]
        self.CheckItems(inds)

    def GetDicomField(self,row):
        return self.GetItem(row,0).Text

    def GetItemList(self,column=0):
        return [self.GetItem(i,column) for i in range(self.ItemCount)]

    def GetChangedIndex(self):
        return [i for (i,val) in enumerate(self.GetItemList(1)) if len(val.Text)>0]

    def GetAnonymousFields(self):
        return [self.GetDicomField(i) for i in self.GetAnonymousIndex()]
