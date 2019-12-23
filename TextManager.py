
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
        return (["Source", "Words", "Progress", "WPM", "Dis."],
                [None, None, "%.1f%%", "%.1f", None])

    def populateData(self, idxs):
        # FIXME: Seems like WPM should be recent/time-bound, instead of global avg
        if len(idxs) == 0:
            return list(map(list, DB.fetchall("""
            select s.rowid,s.name,r.total,100.0*r.seen/r.total,r.wpm,ifelse(nullif(r.total,r.dis),'No','Yes')
                    from source as s
                    left join (select source, count(*) as total, count(wpm) as seen, avg(wpm) as wpm, count(disabled) as dis
                               from text as t
                               left join (select data, agg_median(12.0/time) as wpm from statistic group by data) as w
                               on (t.text = w.data)
                               group by source) as r
                    on (s.rowid = r.source)
                    where s.disabled is null
                    order by s.name""")))

        if len(idxs) > 1:
            return []

        r = self.rows[idxs[0]]

        return list(map(list, DB.fetchall("""select t.rowid,t.text,r.count as total,NULL as progress,r.wpm,ifelse(t.disabled,'Yes','No')
                from (select rowid,* from text where source = ?) as t
                left join (select data,sum(count) as count,agg_median(12.0/time) as wpm from statistic group by data) as r
                    on (t.text = r.data)
                order by t.rowid""", (r[0], ))))



class TextManager(QWidget):

    refreshSources = Signal()
    addWords = Signal(list)

    def __init__(self, *args):
        super(TextManager, self).__init__(*args)

        self.model = SourceModel()
        tv = AmphTree(self.model)
        tv.resizeColumnToContents(1)
        tv.setColumnWidth(0, 300)
        tv.doubleClicked.connect(self.doubleClicked)
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
                            AmphButton("Enable All", self.enableAll),
                            AmphButton("Delete Disabled", self.removeDisabled), None,
                            AmphButton("Update List", self.update)],
                        [ #AmphButton("Remove", self.removeSelected), "or",
                            AmphButton("Toggle disabled", self.disableSelected),
                            "on all selected texts that match <a href=\"http://en.wikipedia.org/wiki/Regular_expression\">regular expression</a>",
                            SettingsEdit('text_regex')]
                ], QBoxLayout.TopToBottom))

    def addFiles(self):

        qf = QFileDialog(self, "Import Text From File(s)", filter="UTF-8 text files (*.txt);;All files (*)")
        qf.setFileMode(QFileDialog.ExistingFiles)
        qf.setAcceptMode(QFileDialog.AcceptOpen)

        qf.filesSelected.connect(self.setImpList)

        qf.show()

    def setImpList(self, files):
        self.sender().hide()
        #self.progress.show()
        for x in files:
            #self.progress.setValue(0)
            fname = path.basename(x)
            # Import one word per line,
            #  optionally tab delimited with stroke following
            words = [ line.split('\t')[0].strip() for line in
                       codecs.open(x, "r", "utf_8_sig") ]
            #lm.progress(self.progress.setValue)
            self.addTexts(fname, words, update=False)

        #self.progress.hide()
        self.update()
        DB.commit()

    def addTexts(self, source, texts, update=True):
        id = DB.getSource(source)
        r = []
        for x in texts:
            h = hashlib.sha1()
            h.update(x.encode('utf-8'))
            txt_id = h.hexdigest()
            try:
                DB.execute("insert into text (id,text,source,disabled) values (?,?,?,?)",
                           (txt_id, x, id, None))
                r.append(txt_id)
            except Exception as e:
                pass # silently skip ...
        if update:
            self.update()
        return r

    def update(self):
        self.refreshSources.emit()
        self.model.reset()

    def genWords(self):
        num_words = Settings.get('num_rand')
        # Fetch random words
        v = DB.execute("select id,source,text from text where disabled is null order by random() limit %d" % num_words).fetchall()
        if len(v) > 0 :
            v = [ row[2] for row in v ]
            self.addWords.emit(v)

    def removeDisabled(self):
        # FIXME
        return
        #self.update()
        #DB.commit()

    def enableAll(self):
        DB.execute('update text set disabled = null where disabled is not null')
        self.update()

    def disableSelected(self):
        cats, texts = self.getSelected()
        DB.setRegex(Settings.get('text_regex'))
        DB.executemany("""update text set disabled = ifelse(disabled,NULL,1)
                where rowid = ? and regex_match(text) = 1""",
                       map(lambda x:(x, ), texts))
        DB.executemany("""update text set disabled = ifelse(disabled,NULL,1)
                where source = ? and regex_match(text) = 1""",
                       map(lambda x:(x, ), cats))
        self.update()

    def getSelected(self):
        texts = []
        cats = []
        for idx in self.tree.selectedIndexes():
            if idx.column() != 0:
                continue
            if idx.parent().isValid():
                texts.append(self.model.data(idx, Qt.UserRole)[0])
            else:
                cats.append(self.model.data(idx, Qt.UserRole)[0])
        return (cats, texts)

    def doubleClicked(self, idx):
        p = idx.parent()
        if not p.isValid():
            return

        q = self.model.data(idx, Qt.UserRole)
        v = DB.fetchall('select id,source,text from text where rowid = ?', (q[0], ))



