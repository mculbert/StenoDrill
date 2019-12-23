
from __future__ import with_statement, division

import time
from itertools import *
import operator

from Data import DB
from Config import *
from QtUtil import *

import Plotters

from PyQt4.QtCore import *
from PyQt4.QtGui import *


def dampen(x, n=10):
    ret = []
    s = sum(x[0:n])
    q = 1/n
    for i in range(n, len(x)):
        ret.append(s*q)
        s += x[i] - x[i-n]
    return ret


class ResultModel(AmphModel):
    def signature(self):
        self.source = None
        self.data_ = []
        self.hidden = 1
        return (["When", "Words", "WPM", "Accuracy"],
                [self.formatWhen, None, "%.1f", "%.1f%%"])

    def populateData(self, idx):
        if len(idx) > 0:
            return []

        return self.data_

    def setData(self, d):
        self.data_ = d
        self.reset()

    def formatWhen(self, w):
        d = time.time() - w

        if d < 60.0:
            return "%.1fs" % d
        d /= 60.0
        if d < 60.0:
            return "%.1fm" % d
        d /= 60.0
        if d < 24.0:
            return "%.1fh" % d
        d /= 24.0
        if d < 7.0:
            return "%.1fd" % d
        d /= 7.0
        if d < 52.0:
            return "%.1fw" % d
        d /= 52.0
        return "%.1fy" % d


class PerformanceHistory(QWidget):
    def __init__(self, *args):
        super(PerformanceHistory, self).__init__(*args)

        self.plotcol = 3
        self.plot = Plotters.Plotter()

        self.editflag = False
        self.model = ResultModel()

        self.cb_source = QComboBox()
        self.refreshSources()
        self.cb_source.currentIndexChanged.connect(self.updateData)

        t = AmphTree(self.model)
        t.setUniformRowHeights(True)
        t.setRootIsDecorated(False)
        t.setIndentation(0)
        #t.doubleClicked.connect(self.doubleClicked)
        Settings['graph_what'].change.connect(self.updateGraph)
        Settings['show_xaxis'].change.connect(self.updateGraph)
        Settings['chrono_x'].change.connect(self.updateGraph)
        Settings['dampen_graph'].change.connect(self.updateGraph)

        self.setLayout(AmphBoxLayout([
                ["Show", SettingsEdit("perf_items"), "items from",
                    self.cb_source,
                    "and group by", SettingsCombo('perf_group_by',
                        ["minute", "sitting", "day", "week", "month"]),
                    None, AmphButton("Update", self.updateData)],
                (t, 1),
                ["Plot", SettingsCombo('graph_what', ((2, 'Words'), (3, 'WPM'), (4, 'accuracy'), )),
                    SettingsCheckBox("show_xaxis", "Show X-axis"),
                    SettingsCheckBox("chrono_x", "Use time-scaled X-axis"),
                    SettingsCheckBox("dampen_graph", "Dampen graph values"), None],
                (self.plot, 1)
            ]))

        Settings['perf_items'].change.connect(self.updateData)
        Settings['perf_group_by'].change.connect(self.updateData)

    def updateGraph(self):
        pc = Settings.get('graph_what')
        y = map(lambda x:x[pc], self.model.rows)

        if Settings.get("chrono_x"):
            x = map(lambda x:x[1], self.model.rows)
        else:
            x = range(len(y))
            x.reverse()

        if Settings.get("dampen_graph"):
            y = dampen(y, Settings.get('dampen_average'))
            x = dampen(x, Settings.get('dampen_average'))

        self.p = Plotters.Plot(x, y)
        self.plot.setScene(self.p)

    def refreshSources(self):
        self.editflag = True
        self.cb_source.clear()
        self.cb_source.addItem("<ALL>")

        for id, v in DB.fetchall('select rowid,abbreviate(name,30) from source order by name'):
            self.cb_source.addItem(v, QVariant(id))
        self.editflag = False

    def updateData(self, *args):
        if self.editflag:
            return

        sql = '''select agg_first(r.data),avg(r.w) as w, sum(count) as num,
            agg_median(12.0/r.time) as wpm,
            100-100.0*sum(mistakes)/sum(count) as accuracy
            from statistic as r
            %s %s
            order by w desc limit %d'''

        if self.cb_source.currentIndex() <= 0:
            where = ''
        else:
            s = self.cb_source.itemData(self.cb_source.currentIndex())
            where = 'join text as s on (r.data = s.text) where (s.source = %d)' % s.toInt()[0]

        g = Settings.get('perf_group_by')
        group = ''
        if g == 0: # minute
            group = "group by cast(r.w/60 as int)"
        elif g == 1: # by sitting
            mis = Settings.get('minutes_in_sitting') * 60.0
            DB.resetTimeGroup()
            group = "group by time_group(%f, r.w)" % mis
        elif g == 2: # by day
            group = "group by cast((r.w+4*3600)/86400 as int)"
        elif g == 3: # by week
            group = "group by cast((r.w+4*3600)/604800 as int)"
        elif g == 4: # by month (30 days)
            group = "group by cast((r.w+4*3600)/2592000 as int)"

        n = Settings.get("perf_items")

        sql = sql % (where, group, n)

        self.model.setData(map(list, DB.fetchall(sql)))
        self.updateGraph()

    def doubleClicked(self, idx):
        r = self.model.rows[idx.row()]
        return # silently ignore
