import configobj
import dicomsort
import os
import re
import sys
import traceback
import wx

from six.moves.urllib.parse import urlencode
from six.moves.urllib.request import urlopen

from dicomsort import config
from dicomsort.dicomsorter import DicomSorter
from dicomsort.errors import DicomFolderError
from dicomsort.gui import errors, events, help, icons, preferences, widgets
from dicomsort.gui.anonymizer import QuickRenameDlg
from dicomsort.gui.update import UpdateChecker


def ExceptHook(type, value, tb):
    dlg = CrashReporter(type, value, tb)
    dlg.ShowModal()
    dlg.Destroy()


class DicomSort(wx.App):
    def __init__(self, *args):
        wx.App.__init__(self, *args)
        self.frame = MainFrame(None, -1, "DicomSort", size=(500, 500))
        self.SetTopWindow(self.frame)
        self.frame.Show()

        sys.excepthook = ExceptHook

        # Check for updates
        UpdateChecker(self.frame, listener=self.frame)
        self.frame.Bind(events.EVT_UPDATE, self.frame.OnNewVersion)

    def MainLoop(self, *args):
        wx.App.MainLoop(self, *args)


class CrashReporter(wx.Dialog):
    def __init__(self, type=None, value=None, tb=None, fullstack=None):
        super(
            CrashReporter, self).__init__(None, -1, 'DicomSort Crash Reporter',
                                          size=(400, 400))
        self.type = type
        self.value = value
        self.tb = tb

        if fullstack:
            self.traceback = fullstack
        else:
            self.traceback = '\n'.join(
                traceback.format_exception(type, value, tb))

        self.Create()
        self.SetIcon(icons.main.GetIcon())

    def Create(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        heading = wx.StaticText(self, -1, "Epic Fail")
        heading.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD))

        vbox.Add(heading, 0, wx.LEFT | wx.TOP, 15)

        text = ''.join(['Dicom Sorting had a problem and crashed.\n',
                        'In order to help diagnose the problem, you can send a '
                        'crash report.'])

        static = wx.StaticText(self, -1, text)
        vbox.Add(static, 0, wx.ALL, 15)

        vbox.Add(wx.StaticText(self, -1, 'Comments:'), 0, wx.LEFT, 15)

        self.comments = wx.TextCtrl(self, style=wx.TE_MULTILINE)

        defComments = '\n\n\n--------------DO NOT EDIT BELOW ------------\n'

        self.comments.SetValue(defComments + self.traceback)
        vbox.Add(self.comments, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        label = 'Email me when a fix is available'
        self.email = wx.CheckBox(self, -1, label=label)
        vbox.Add(self.email, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.email.Bind(wx.EVT_CHECKBOX, self.OnEmail)

        self.emailAddress = wx.TextCtrl(
            self, -1, 'Enter your email address here',
            size=(200, -1))
        self.emailAddress.Enable(False)

        vbox.Add(self.emailAddress, 0, wx.LEFT | wx.RIGHT, 35)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.sender = wx.Button(self, -1, "Send Report")
        self.cancel = wx.Button(self, -1, "Cancel")

        self.sender.Bind(wx.EVT_BUTTON, self.Report)
        self.cancel.Bind(wx.EVT_BUTTON, self.OnCancel)

        hbox.Add(self.cancel, 0, wx.RIGHT, 10)
        hbox.Add(self.sender, 0, wx.RIGHT, 15)

        vbox.Add(hbox, 0, wx.TOP | wx.BOTTOM | wx.ALIGN_RIGHT, 10)

        self.SetSizer(vbox)

    def OnCancel(self, *evnt):
        self.Destroy()

    def OnEmail(self, *evnt):
        if self.email.IsChecked():
            self.emailAddress.Enable()
        else:
            self.emailAddress.Enable(False)

    def Report(self, *evnt):
        if self.email.IsChecked():
            email = self.ValidateEmail()
        else:
            email = None

        url = 'http://www.suever.net/software/dicomSort/bug_report.php'
        values = {
            'OS': sys.platform,
            'version': dicomsort.__version__,
            'email': email,
            'comments': self.comments.GetValue().strip('\n')
        }

        data = urlencode(values)
        urlopen(url, data)
        self.OnCancel()

    def ValidateEmail(self):
        email = self.emailAddress.GetValue()

        regex = '[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}'

        if not re.search(regex, email, re.UNICODE | re.IGNORECASE):
            errors.throw_error('Please enter a valid email address', parent=self)

        return email


class MainFrame(wx.Frame):

    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)

        self.Create()
        self._InitializeMenus()

        # Use os.getcwd() for now
        self.dicom_sorter = DicomSorter()

        # Store the selected output directory to speed it up
        self.outputDirectory = None

        # Get config from parent
        self.config = configobj.ConfigObj(config.configuration_file)
        # Set interpolation to false since we use formatted strings
        self.config.interpolation = False

        # Check to see if we need to populate the config file
        if len(self.config.keys()) == 0:
            self.config.update(config.default_configuration)
            self.config.write()
        elif 'Version' not in self.config or self.config['Version'] != config.configuration_version:
            self.config.update(config.default_configuration)
            self.config.write()

        self.prefDlg = preferences.PreferenceDlg(
            None, -1, "DicomSort Preferences",
            config=self.config, size=(400, 400))

        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        self.CreateStatusBar()
        self.SetStatusText("Ready...")

    def OnNewVersion(self, evnt):
        dlg = widgets.UpdateDlg(self, evnt.version)
        dlg.Show()

    def Create(self):

        # Set Frame icon
        if os.path.isfile(os.path.join(sys.executable, 'DSicon.ico')):
            self.exedir = sys.executable
        else:
            self.exedir = sys.path[0]

        self.SetIcon(icons.main.GetIcon())

        vbox = wx.BoxSizer(wx.VERTICAL)

        self.pathEditor = widgets.PathEditCtrl(self, -1)
        vbox.Add(self.pathEditor, 0, wx.EXPAND)

        self.selector = widgets.FieldSelector(self, titles=['DICOM Properties',
                                                            'Properties to Use'])

        self.selector.Bind(events.EVT_SORT, self.Sort)

        vbox.Add(self.selector, 1, wx.EXPAND)

        self.SetSizer(vbox)

        self.pathEditor.Bind(events.EVT_PATH, self.FillList)

    def Sort(self, evnt):

        if self.dicom_sorter.is_sorting():
            return

        self.anonymize = evnt.anon

        miscTab = self.prefDlg.pages['Miscpanel']
        self.dicom_sorter.series_first = miscTab.seriesFirst.IsChecked()
        self.dicom_sorter.keep_original = miscTab.keepOriginal.IsChecked()

        if self.anonymize:
            anon_tab = self.prefDlg.pages['Anonymization']
            rules = anon_tab.anonList.GetAnonDict()
            self.dicom_sorter.set_anonymization_rules(rules)
        else:
            self.dicom_sorter.set_anonymization_rules(dict())

        directory_format = evnt.fields

        filename_method = int(self.config['FilenameFormat']['Selection'])
        filename_format = ''

        if filename_method == 0:
            # Image (0001)
            filename_format = '%(ImageType)s (%(InstanceNumber)04d)%(FileExtension)s'
        elif filename_method == 1:
            # Use the original filename
            filename_format = ''
            self.dicom_sorter.keep_filename = True
            # Alternately we could pass None to dicom_sorter
        elif filename_method == 2:
            # Use custom format
            filename_format = self.config['FilenameFormat']['FilenameString']

        self.dicom_sorter.filename = filename_format
        self.dicom_sorter.folders = directory_format

        self.outputDirectory = self.SelectOutputDir()

        if not self.outputDirectory:
            return

        # Use for the real deal
        self.dicom_sorter.sort(self.outputDirectory, listener=self)

        self.Bind(events.EVT_COUNTER, self.OnCount)

    def OnCount(self, event):
        status = '%s / %s' % (event.Count, event.total)
        self.SetStatusText(status)

    def SelectOutputDir(self):
        if not self.outputDirectory:
            # Then don't set a default path
            dlg = wx.DirDialog(self, "Please select an output directory")
        else:
            dlg = wx.DirDialog(self, "Please select an output directory",
                               self.outputDirectory)

        dlg.CenterOnParent()

        if dlg.ShowModal() == wx.ID_OK:
            outputDir = dlg.GetPath()
        else:
            outputDir = None

        dlg.Destroy()

        return outputDir

    def OnPreferences(self, *_event):
        self.config = self.prefDlg.ShowModal()

    def OnQuit(self, *_event):
        sys.exit()

    def OnAbout(self, *_event):
        widgets.AboutDlg()

    def OnHelp(self, *_event):
        help.HelpDlg(self)

    def _MenuGenerator(self, parent, name, arguments):
        menu = wx.Menu()

        for item in arguments:
            if item == '----':
                menu.AppendSeparator()
            else:
                menuitem = wx.MenuItem(menu, -1, '\t'.join(item[0:2]))
                if item[2] != '':
                    self.Bind(wx.EVT_MENU, item[2], menuitem)

                menu.Append(menuitem)

        parent.Append(menu, name)

    def LoadDebug(self, *_event):
        size = self.Size
        pos = self.Position

        pos = (pos[0] + size[0], pos[1])

        self.debug = wx.Frame(
            None, -1, 'DicomSort DEBUGGER', size=(700, 500), pos=pos)
        self.crust = wx.py.crust.Crust(self.debug)
        self.debug.Show()

    def QuickRename(self, *_event):
        self.anonList = self.prefDlg.pages['Anonymization'].anonList
        dlg = QuickRenameDlg(None, -1, 'Anonymize', size=(250, 160),
                             anonList=self.anonList)
        dlg.ShowModal()
        dlg.Destroy()

    def _InitializeMenus(self):
        menubar = wx.MenuBar()

        file = [['&Open Directory', 'Ctrl+O', self.pathEditor.BrowsePaths],
                '----',
                ['&Preferences...', 'Ctrl+,', self.OnPreferences],
                '----',
                ['&Exit', 'Ctrl+W', self.OnQuit]]

        self._MenuGenerator(menubar, '&File', file)

        win = [['Quick &Rename', 'Ctrl+R', self.QuickRename], '----',
               ['&Debug Window', 'Ctrl+D', self.LoadDebug]]

        self._MenuGenerator(menubar, '&Window', win)

        help = [['About', '', self.OnAbout],
                ['&Help', 'Ctrl+?', self.OnHelp]]

        self._MenuGenerator(menubar, '&Help', help)

        self.SetMenuBar(menubar)

    def FillList(self, event):
        self.dicom_sorter.pathname = event.path
        try:
            fields = self.dicom_sorter.available_fields()
        except DicomFolderError:
            message = ''.join([';'.join(event.path), ' contains no DICOMs'])
            errors.throw_error(message, 'No DICOMs Present', parent=self)
            return

        self.selector.SetOptions(fields)

        # Now set seriesDescription as the default
        if len(self.selector.selected.Items) == 0:
            self.selector.selected.Append('SeriesDescription')

        # This is clunky
        # TODO: Change PrefDlg to a dict
        self.prefDlg.pages['Anonymization'].SetDicomFields(fields)

        self.Notify(events.PopulateEvent, fields=fields)

    def Notify(self, evntType, **kwargs):
        event = evntType(**kwargs)
        wx.PostEvent(self, event)