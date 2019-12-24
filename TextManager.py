
from __future__ import with_statement, division

#import psyco
import os.path as path
import time
import hashlib
import codecs

from Data import DB
from QtUtil import *
from Config import *

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtCore import pyqtSignal as Signal


class SourceModel(AmphModel):
    def signature(self):
        self.hidden = 1
        return (["Source", "Words", "Progress", "WPM", "Act."],
                [None, None, "%.1f%%", "%.1f", None])

    def populateData(self, idxs):
        # FIXME: Seems like WPM should be recent/time-bound, instead of global avg
        if len(idxs) == 0:
            return list(map(list, DB.fetchall("""
            select s.rowid,s.name,r.total,100.0*r.seen/r.total,r.wpm,ifelse(s.active,'Y','N')
                    from sources as s
                    left join (select source, count(*) as total, count(wpm) as seen, avg(wpm) as wpm
                               from source_words as sw
                               left join (select word, 1.0/agg_median(mpw) as wpm from statistic group by word) as ss
                               on (sw.word = ss.word)
                               group by source) as r
                    on (s.rowid = r.source)
                    order by s.name""")))

        if len(idxs) > 1:
            return []

        r = self.rows[idxs[0]]

        return list(map(list, DB.fetchall("""select w.rowid,w.word,r.count as total,NULL as progress,r.wpm,ifelse(w.active,'Y','N')
                from (select * from source_words where source = ?) as sw
                join words as w on (sw.word = w.rowid)
                left join (select word, sum(count) as count, 1.0/agg_median(mpw) as wpm from statistic group by word) as r
                    on (w.rowid = r.word)
                order by w.rowid""", (r[0], ))))



class TextManager(QWidget):

    refreshSources = Signal()

    def __init__(self, *args):
        super(TextManager, self).__init__(*args)

        self.model = SourceModel()
        tv = AmphTree(self.model)
        tv.resizeColumnToContents(1)
        tv.setColumnWidth(0, 300)
        #tv.doubleClicked.connect(self.doubleClicked)
        self.tree = tv

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()

        self.setLayout(AmphBoxLayout(
                [
                        "Below you will see the different text sources used. Disabling texts or sources deactivates them so they won't be selected for typing. You can double click a text to do that particular text.\n",
                        (self.tree, 1),
                        self.progress,
                        [AmphButton("Import Texts", self.addFiles), None,
                            AmphButton("Toggle Selected", self.toggleSelected),
                            AmphButton("Enable All", self.enableAll),
                            #AmphButton("Delete Disabled", self.removeDisabled),
                            None,
                            AmphButton("Update List", self.update)],
                ], QBoxLayout.TopToBottom))

    def addFiles(self):

        qf = QFileDialog(self, "Import Text From File(s)", filter="UTF-8 text files (*.txt);;All files (*)")
        qf.setFileMode(QFileDialog.ExistingFiles)
        qf.setAcceptMode(QFileDialog.AcceptOpen)

        qf.filesSelected.connect(self.importFiles)

        qf.show()

    def importFiles(self, files):
        self.sender().hide()
        for x in files:
            fname = path.basename(x)
            # Import one word per line,
            #  optionally tab delimited with stroke following
            words = [ line.split('\t')[0].strip() for line in
                       codecs.open(x, "r", "utf_8_sig") ]
            # Get new source id
            DB.execute("insert into sources (name,active) values (?,1)", (fname,))
            source_id = DB.fetchall("select rowid from sources where name = ?", (fname,))[0][0]
            # Get existing words
            cur_words = {}
            for (word,) in DB.fetchall("select word from words"):
                cur_words[word] = None
            # Insert new words
            DB.executemany("insert into words (word,active) values (?,%d)" %
                           0 if Settings.get('progressive') else 1,
                           map(lambda x: (x,), filter(lambda x: x not in cur_words, words)))
            # Fetch word ids
            for (word,word_id) in DB.fetchall("select word,rowid from words"):
                cur_words[word] = word_id
            # Link words to source
            DB.executemany("insert into source_words (source,word) values (%d,?)" % source_id,
                           map(lambda x: (cur_words[x],), words))

        self.update()
        DB.commit()

    def update(self):
        self.refreshSources.emit()
        self.model.reset()

    def removeDisabled(self):
        # FIXME
        return
        #self.update()
        #DB.commit()

    def enableAll(self):
        DB.execute('update sources set active = 1')
        DB.execute('update words set active = 1')
        self.update()

    def toggleSelected(self):
        sources, words = self.getSelected()
        if len(sources) > 0:
            current = DB.fetchall('''select rowid, active from sources where rowid in (%s)''' % ','.join(map(str, sources)))
            DB.executemany('''update sources set active = ? where rowid = ?''',
                           map(lambda row: (1-row[1], row[0]), current))
        if len(words) > 0:
            current = DB.fetchall('''select rowid, active from words where rowid in (%s)''' % ','.join(map(str, words)))
            DB.executemany('''update words set active = ? where rowid = ?''',
                           map(lambda row: (1-row[1], row[0]), current))
        self.update()

    def getSelected(self):
        sources = []
        words = []
        for idx in self.tree.selectedIndexes():
            if idx.column() != 0:
                continue
            if idx.parent().isValid():
                words.append(self.model.data(idx, Qt.UserRole)[0])
            else:
                sources.append(self.model.data(idx, Qt.UserRole)[0])
        return (sources, words)

    def doubleClicked(self, idx):
        if idx.parent().isValid():  # Word
            DB.execute('''update words set active = 0 where rowid = ?''',
                       (self.model.data(idx, Qt.UserRole)[0],))
        else:                       # Source
            DB.execute('''update sources set active = 0 where rowid = ?''',
                       (self.model.data(idx, Qt.UserRole)[0],))
        self.update()



