
from __future__ import division, with_statement

import time

from Data import DB
from QtUtil import *
from Config import *

from PyQt4.QtCore import *
from PyQt4.QtGui import *



class WordModel(AmphModel):
    def signature(self):
        self.words = []
        return (["Item", "Speed", "Accuracy", "Count", "Mistakes"],
                [None, "%.1f wpm", "%.1f%%", None, None])

    def populateData(self, idx):
        if len(idx) != 0:
            return []

        return self.words

    def setData(self, words):
        self.words = map(list, words)
        self.reset()




class StringStats(QWidget):
    def __init__(self, *args):
        super(StringStats, self).__init__(*args)

        self.model = WordModel()
        tw = AmphTree(self.model)
        tw.setIndentation(0)
        tw.setUniformRowHeights(True)
        tw.setRootIsDecorated(False)
        self.stats = tw

        ob = SettingsCombo('ana_which', [
                    ('wpm asc', 'slowest'),
                    ('wpm desc', 'fastest'),
                    ('accuracy asc', 'least accurate'),
                    ('misses desc', 'most mistyped'),
                    ('total desc', 'most common'),
                    ])

        lim = SettingsEdit('ana_many')
        self.w_count = SettingsEdit('ana_count')

        self.connect(Settings, SIGNAL("change_ana_which"), self.update)
        self.connect(Settings, SIGNAL("change_ana_many"), self.update)
        self.connect(Settings, SIGNAL("change_ana_count"), self.update)
        self.connect(Settings, SIGNAL("history"), self.update)

        self.setLayout(AmphBoxLayout([
                ["Display statistics about the", ob, "words", None, AmphButton("Update List", self.update)],
                ["Limit list to", lim, "items and don't show items with a count less than", self.w_count,
                    None, None],
                (self.stats, 1)
            ]))

    def update(self, *arg):

        ord = Settings.get('ana_which')
        limit = Settings.get('ana_many')
        count = Settings.get('ana_count')
        hist = time.time() - Settings.get('history') * 86400.0

        sql = """select data,12.0/time as wpm,
            100.0-100.0*misses/cast(total as real) as accuracy,total,misses
                from
                    (select data,agg_median(time) as time,
                    sum(count) as total,sum(mistakes) as misses
                    from statistic where w >= ? group by data)
                where total >= ?
                order by %s limit %d""" % (ord, limit)

        self.model.setData(DB.fetchall(sql, (hist, count)))

