

from __future__ import with_statement, division

from QtUtil import *

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from Config import *
from Data import DB, dbname
import time
import locale
locale.setlocale(locale.LC_ALL, '')


class IncrementalProgress(QProgressBar):
    def __init__(self, maxi, *args):
        QProgressBar.__init__(self, *args)

        self.setRange(0, maxi)
        self.setValue(0)
        self.hide()

    def show(self):
        self.setValue(0)
        QProgressBar.show(self)

    def inc(self, val=1):
        self.setValue(self.value() + val)

class DatabaseWidget(QWidget):
    def __init__(self, *args):
        super(DatabaseWidget, self).__init__(*args)

        self.stats_ = QLabel("\nPress Update to fetch database statistics\n")
        self.progress_ = IncrementalProgress(6+2)

        self.setLayout(AmphBoxLayout([
                [AmphButton("Update", self.update), 150,
                    (["Current database:", QLabel(dbname)], 1)
                ], #AmphButton("Import", self.importdb), "external DB file"]]],
                self.stats_,
                None,
                "After heavy use for several months the database can grow quite large since " \
                    +"lots of data are generated after every result and it's all stored indefinitely. " \
                    +"Here you can group old statistics into larger batches. This will speed up " \
                    +"data retrieval for statistics. It is recommended you do it once a month or so if you use the program regularly.\n",
                ["Group data older than", SettingsEdit('group_month'), "days into months, data older than",
                    SettingsEdit('group_week'), "days into weeks, and data older than",
                    SettingsEdit('group_day'), "days into days.",
                    None],
                [AmphButton("Go!", self.cleanup), None],
                [self.progress_],
                None
            ]))

    def importdb(self):
        pass

    def update(self):
        self.progress_.show()
        n_words = DB.fetchone('''select count(*) from words''', (0,))[0] ; self.progress_.inc(2)
        n_seen = DB.fetchone('''select count(*) from (select word from statistic group by word)''', (0,))[0] ; self.progress_.inc(2)
        n_trials = DB.fetchone('''select sum(count) from statistic''', (0,))[0] ; self.progress_.inc(2)
        n_first = DB.fetchone('''select w from statistic order by w asc limit 1''',
            (time.time(),))[0] ; self.progress_.hide()

        self.stats_.setText(locale.format_string(
'''Words: %d of %d seen (%.1f%%)
Trials: %d
First result was %.2f days ago.\n''',
  (n_seen, n_words, 100.0*n_seen/n_words, n_trials, (time.time()-n_first)/86400.0)))

    def cleanup(self):
        day = 24*60*60
        now = time.time()
        q = []

        self.progress_.show()
        for grp, lim in [(30.0, Settings.get('group_month')),
                (7.0, Settings.get('group_week')),
                (1.0, Settings.get('group_day'))]:

            w = now - day*lim
            g = grp * day
            q.extend( DB.fetchall('''
                select avg(w),word,agg_mean(mpw,count),sum(count),sum(mistakes)
                from statistic where w <= %f
                group by word,cast(w/%f as int)''' % (w, g)) )
            self.progress_.inc()

            DB.execute('''delete from statistic where w <= ?''', (w, ))
            self.progress_.inc()

        DB.executemany('''insert into statistic (w,word,mpw,count,mistakes)
            VALUES (?,?,?,?,?)''', q)
        self.progress_.inc()
        DB.commit()
        DB.execute('vacuum')
        self.progress_.inc()
        DB.commit()
        self.progress_.hide()


if __name__ == '__main__':
    app = QApplication([])
    dw = DatabaseWidget()
    dw.show()
    app.exec_()


