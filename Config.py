
from __future__ import with_statement

import pickle
from Data import DB
from QtUtil import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtCore import pyqtSignal as Signal

class AmphSetting(QObject):

    change = Signal()
    
    def __init__(self, name):
        super(AmphSetting, self).__init__()
        self.name = name
        # Check database for setting value
        value = DB.fetchall('''select value from settings where name = ?''', (name,))
        if (len(value) > 0):
            # Load value from database
            self.value = pickle.loads(value[0][0])
            self.in_db = True
        elif name in AmphSettings.defaults:
            # Use default value
            self.value = AmphSettings.defaults[name]
            self.in_db = False
        else:
            # Error: No such setting
            raise KeyError(name)
    
    def get(self):
        return self.value
    
    def set(self, value):
        if self.value == value: return
        self.value = value
        if self.in_db:
            DB.execute('''update settings set value = ? where name = ?''',
                       (pickle.dumps(value), self.name))
        else:
            DB.execute('''insert into settings (name,value) values (?,?)''',
                       (self.name, pickle.dumps(value)))
            self.in_db = True
        self.change.emit()


class AmphSettings(QObject):

    defaults = {
            "typer_font": str(QFont("Arial", 14).toString()),
            "ignore_case": True,
            "progressive": True,
            "prog_times": 3,
            "prog_min": 15,
            "prog_avg": 20,
            "history": 30.0,
            "perf_group_by": 0,
            "perf_items": 100,
            "text_regex": r"",
            "num_rand": 10,
            "graph_what": 3,
            "show_xaxis": False,
            "chrono_x": False,
            "dampen_graph": False,

            "minutes_in_sitting": 60.0,
            "dampen_average": 10,

            "group_month": 365.0,
            "group_week": 30.0,
            "group_day": 7.0,

            "ana_how": 1,
            "ana_which": "wpm asc",
            "ana_many": 30,
            "ana_count": 1,

            "gen_copies": 3,
            "gen_take": 2,
            "gen_mix": 'c',
            #"gen_stats": False,
            "str_clear": 's',
            "str_extra": 10,
            "str_what": 'e'
        }
        
    def __init__(self):
        super(AmphSettings, self).__init__()
        self.cache = {}
    
    def __getitem__(self, k):
        if k not in self.cache:
            self.cache[k] = AmphSetting(k)
        return self.cache[k]
    
    def get(self, k):
        return self[k].get()

    def getFont(self, k):
        qf = QFont()
        qf.fromString(self.get(k))
        return qf

    def getColor(self, k):
        return QColor(self.get(k))

    def set(self, k, v):
        p = self.get(k)
        if p == v:
            return
        self[k].set(v)



Settings = AmphSettings()


class SettingsColor(AmphButton):
    def __init__(self, key, text):
        self.key_ = key
        super(SettingsColor, self).__init__(Settings.get(key), self.pickColor)
        self.updateIcon()

    def pickColor(self):
        color = QColorDialog.getColor(Settings.getColor(self.key_), self)
        if not color.isValid():
            return
        Settings.set(self.key_, color.name())
        self.updateIcon()

    def updateIcon(self):
        pix = QPixmap(32, 32)
        c = Settings.getColor(self.key_)
        pix.fill(c)
        self.setText(Settings.get(self.key_))
        self.setIcon(QIcon(pix))



class SettingsEdit(AmphEdit):
    def __init__(self, setting):
        sttg = Settings[setting]
        val = sttg.get()
        typ = type(val)
        validator = None
        if isinstance(val, float):
            validator = QDoubleValidator
        elif isinstance(val, int):
            validator = QIntValidator
        if validator is None:
            self.fmt = lambda x: x
        else:
            self.fmt = lambda x: "%g" % x
        super(SettingsEdit, self).__init__(
                            self.fmt(val),
                            lambda: Settings.set(setting, typ(self.text())),
                            validator=validator)
        sttg.change.connect(lambda : self.setText(str(sttg.get())) )


class SettingsCombo(QComboBox):
    def __init__(self, setting, lst, *args):
        super(SettingsCombo, self).__init__(*args)

        sttg = Settings[setting]
        prev = sttg.get()
        self.idx2item = []
        for i in range(len(lst)):
            if isinstance(lst[i], str):
                # not a tuple, use index as key
                k, v = i, lst[i]
            else:
                k, v = lst[i]
            self.addItem(v)
            self.idx2item.append(k)
            if k == prev:
                self.setCurrentIndex(i)

        self.activated.connect(lambda x: sttg.set(self.idx2item[x]))

class SettingsCheckBox(QCheckBox):
    def __init__(self, setting, *args):
        super(SettingsCheckBox, self).__init__(*args)
        sttg = Settings[setting]
        self.setCheckState(Qt.Checked if sttg.get() else Qt.Unchecked)
        self.stateChanged.connect(lambda x: sttg.set(x == Qt.Checked))

class PreferenceWidget(QWidget):
    def __init__(self):
        super(PreferenceWidget, self).__init__()

        self.font_lbl = QLabel()

        self.setLayout(AmphBoxLayout([
            ["Typer font is", self.font_lbl, AmphButton("Change...", self.setFont), None],
            [SettingsCheckBox("ignore_case", "Ignore capitalization"), None],
            [SettingsCheckBox("progressive", "Activate new words progressively"), None],
            ["Activate words when you have typed words accurately",
              SettingsEdit("prog_times"), "times, ", None ],
            ["with a minimum speed of",
              SettingsEdit("prog_min"), "WPM and an average speed of",
              SettingsEdit("prog_avg"), "WPM.", None ],
            ["Show", SettingsEdit('num_rand'), "words at a time.", None],
            ["Data is considered too old to be included in analysis after",
                SettingsEdit("history"), "days.", None],
            ["When grouping by sitting on the Performance tab, consider results more than",
                SettingsEdit('minutes_in_sitting'), "minutes away to be part of a different sitting.", None],
            ["When smoothing out the graph, display a running average of", SettingsEdit('dampen_average'), "values", None]
        ]))

        self.updateFont()

    def setFont(self):
        font, ok = QFontDialog.getFont(Settings.getFont('typer_font'), self)
        Settings.set("typer_font", font.toString())
        self.updateFont()

    def updateFont(self):
        self.font_lbl.setText(Settings.get("typer_font"))
        qf = Settings.getFont('typer_font')
        self.font_lbl.setFont(qf)
