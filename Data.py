

from __future__ import division, with_statement



from itertools import *
import time
import math
import bisect
import sqlite3
import re
from PyQt5.QtWidgets import QApplication, QMessageBox


def trimmed_average(total, series):
        s = 0.0
        n = 0

        start = 0
        cutoff = total // 3
        while cutoff > 0:
            cutoff -= series[start][1]
            start += 1
        if cutoff < 0:
            s += -cutoff * series[start-1][0]
            n += -cutoff

        end = len(series)-1
        cutoff = total // 3
        while cutoff > 0:
            cutoff -= series[end][1]
            end -= 1
        if cutoff < 0:
            s += -cutoff * series[end+1][0]
            n += -cutoff

        while start <= end:
            s += series[start][1] * series[start][0]
            n += series[start][1]
            start += 1

        return s/n


class Statistic(list):
    def __init__(self):
        super(Statistic, self).__init__()
        self.flawed_ = 0

    def append(self, x, flawed=False):
        bisect.insort(self, x)
        if flawed:
            self.flawed_ += 1

    def __cmp__(self, other):
        return cmp(self.median(), other.median())

    def measurement(self):
        return trimmed_average(len(self), map(lambda x:(x, 1), self))

    def median(self):
        l = len(self)
        if l == 0:
            return None
        if l & 1:
            return self[l // 2]
        return (self[l//2] + self[l//2-1])/2.0

    def flawed(self):
        return self.flawed_





class MedianAggregate(Statistic):
    def step(self, val):
        self.append(val)

    def finalize(self):
        return self.median()

class MedianAggregateFirstN(MedianAggregate):
    def step(self, val, N):
        if len(self) < N:
            self.append(val)

class MeanAggregate(object):
    def __init__(self):
        self.sum_ = 0.0
        self.count_ = 0

    def step(self, value, count):
        self.sum_ += value * count
        self.count_ += count

    def finalize(self):
        return self.sum_ / self.count_

class MeanAggregateFirstN(MeanAggregate):
    def __init__(self):
        self.sum_ = 0.0
        self.count_ = 0
        self.steps_ = 0
        
    def step(self, val, count, N):
        if self.steps_ < N:
            self.sum += value * count
            self.count_ += count
            self.steps_ += 1

class FirstAggregate(object):
    def __init__(self):
        self.val = None

    def step(self, val):
        if self.val is None:
            self.val = val

    def finalize(self):
        return self.val

class SumFirstN(object):
    def __init__(self):
        self.sum_ = 0.0
        self.steps_ = 0

    def step(self, value, N):
        if self.steps_ < N:
            self.sum_ += value
            self.steps_ += 1

    def finalize(self):
        return self.sum_


class AmphDatabase(sqlite3.Connection):
    def __init__(self, *args):
        super(AmphDatabase, self).__init__(*args)

        self.setRegex("")
        self.resetCounter()
        self.resetTimeGroup()
        self.create_function("counter", 0, self.counter)
        self.create_function("regex_match", 1, self.match)
        self.create_function("abbreviate", 2, self.abbreviate)
        self.create_function("time_group", 2, self.time_group)
        self.create_function("pow", 2, lambda base, exp: None if base is None else math.pow(base, exp))
        self.create_aggregate("agg_median", 1, MedianAggregate)
        self.create_aggregate("agg_mean", 2, MeanAggregate)
        self.create_aggregate("agg_first", 1, FirstAggregate)
        self.create_aggregate("agg_median_firstN", 2, MedianAggregateFirstN)
        self.create_aggregate("agg_mean_firstN", 3, MeanAggregateFirstN)
        self.create_aggregate("agg_sum_firstN", 2, SumFirstN)
        #self.create_aggregate("agg_trimavg", 2, TrimmedAverarge)
        self.create_function("ifelse", 3, lambda x, y, z: y if x else z)

        try:
            self.fetchall("select * from settings,sources,words,source_words,statistic limit 1")
        except:
            self.newDB()

    def resetTimeGroup(self):
        self.lasttime_ = 0.0
        self.timecnt_ = 0

    def time_group(self, d, x):
        if abs(x-self.lasttime_) >= d:
            self.timecnt_ += 1
        self.lasttime_ = x
        return self.timecnt_

    def setRegex(self, x):
        self.regex_ = re.compile(x)

    def abbreviate(self, x, n):
        if len(x) <= n:
            return x
        return x[:n-3] + "..."

    def match(self, x):
        if self.regex_.search(x):
            return 1
        return 0

    def counter(self):
        self._count += 1
        return self._count
    def resetCounter(self):
        self._count = -1

    def newDB(self):
        self.executescript("""
create table settings (name text primary key, value text);
create table sources (name text, active integer);
create table words (word text, active integer);
create table source_words (source integer, word integer);
create table statistic (w real, word integer, mpw real, count integer, mistakes integer);
create view active_words as
    select distinct w.rowid as id, w.word
    from sources as s
    join source_words as sw on (s.rowid = sw.source)
    join words as w on (sw.word = w.rowid)
    where s.active = 1 and w.active = 1;
create view word_status as
    select word,agg_median_firstN(mpw, 10) as mpw,agg_sum_firstN(mistakes, 10)/agg_sum_firstN(count, 10) as err_rate
    from (select * from statistic order by w desc) group by word;
        """)
        self.commit()

    def executemany_(self, *args):
        super(AmphDatabase, self).executemany(*args)
    def executemany(self, *args):
        super(AmphDatabase, self).executemany(*args)
        #self.commit()

    def fetchall(self, *args):
        return self.execute(*args).fetchall()

    def fetchone(self, sql, default, *args):
        x = self.execute(sql, *args)
        g = x.fetchone()
        if g is None:
            return default
        return g



# GLOBAL
DB = None
dbname = ''

def load_db(new_db):
    global DB, dbname
    if DB is not None:
        DB.commit()
    try:
        nDB = sqlite3.connect(new_db,5,0,"DEFERRED",False,AmphDatabase)
        DB = nDB
        dbname = new_db
    except Exception as e:
        app = QApplication([])
        QMessageBox.information(None, "Database Error", "Failed to load database:\n" + str(e))




#Item = ItemStatistics()


