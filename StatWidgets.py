
from __future__ import division, with_statement

import time

from Data import DB
from QtUtil import *
from Config import *

from PyQt5.QtCore import *
from PyQt5.QtGui import *



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
        self.words = list(map(list, words))
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

        h = SettingsCombo('ana_how', ['current', 'recent'])
        ob = SettingsCombo('ana_which', [
                    ('wpm asc', 'slowest'),
                    ('wpm desc', 'fastest'),
                    ('accuracy asc', 'least accurate'),
                    ('misses desc', 'most mistyped'),
                    ('total desc', 'most common'),
                    ])

        lim = SettingsEdit('ana_many')
        self.w_count = SettingsEdit('ana_count')

        Settings['ana_how'].change.connect(self.update)
        Settings['ana_which'].change.connect(self.update)
        Settings['ana_many'].change.connect(self.update)
        Settings['ana_count'].change.connect(self.update)
        Settings['history'].change.connect(self.update)

        self.setLayout(AmphBoxLayout([
                ["Display", h, "statistics about the", ob, "words", None, AmphButton("Update List", self.update)],
                ["Limit list to", lim, "items and don't show items with a count less than", self.w_count,
                    None, None],
                (self.stats, 1)
            ]))

    def update(self, *arg):

        ord = Settings.get('ana_which')
        limit = Settings.get('ana_many')
        count = Settings.get('ana_count')
        hist = time.time() - Settings.get('history') * 86400.0
        
        if Settings.get('ana_how'):
            how = '''(select word,agg_median(mpw) as mpw,sum(count) as seen,sum(mistakes) as mistakes
                    from statistic where w >= ? group by word)'''
        else:
            how = '''(select word,agg_median_firstN(mpw, 10) as mpw,agg_sum_firstN(count, 10) as seen,agg_sum_firstN(mistakes, 10) as mistakes
                     from (select * from statistic where w >= ? order by w desc) group by word)'''

        sql = """select w.word,1.0/mpw as wpm,
            100.0-100.0*mistakes/cast(seen as real) as accuracy,seen,mistakes
                from %s as s join words as w on (s.word = w.rowid)
                where s.seen >= ? order by %s limit %d""" % (how, ord, limit)

        self.model.setData(DB.fetchall(sql, (hist, count)))

