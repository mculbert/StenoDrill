
from __future__ import with_statement, division

#import psyco
import os.path as path
import time
import hashlib
import codecs

from Data import DB
from QtUtil import *
from Config import *

from PyQt4.QtCore import *
from PyQt4.QtGui import *



class SourceModel(AmphModel):
    def signature(self):
        self.hidden = 1
        return (["Source", "Length", "Results", "WPM", "Dis."],
                [None, None, None, "%.1f", None])

    def populateData(self, idxs):
        if len(idxs) == 0:
            return map(list, DB.fetchall("""
            select s.rowid,s.name,t.count,r.count,r.wpm,ifelse(nullif(t.dis,t.count),'No','Yes')
                    from source as s
                    left join (select source,count(*) as count,count(disabled) as dis from text group by source) as t
                        on (s.rowid = t.source)
                    left join (select source,count(*) as count,avg(wpm) as wpm from result group by source) as r
                        on (t.source = r.source)
                    where s.disabled is null
                    order by s.name"""))

        if len(idxs) > 1:
            return []

        r = self.rows[idxs[0]]

        return map(list, DB.fetchall("""select t.rowid,substr(t.text,0,40)||"...",length(t.text),r.count,r.m,ifelse(t.disabled,'Yes','No')
                from (select rowid,* from text where source = ?) as t
                left join (select text_id,count(*) as count,agg_median(wpm) as m from result group by text_id) as r
                    on (t.id = r.text_id)
                order by t.rowid""", (r[0], )))



class TextManager(QWidget):

    defaultText = ("", 0, """Welcome to Amphetype!
A typing program that not only measures your speed and progress, but also gives you detailed statistics about problem keys, words, common mistakes, and so on. This is just a default text since your database is empty. You might import a novel or text of your choosing and text excerpts will be generated for you automatically. There are also some facilities to generate lessons based on your past statistics! But for now, go to the "Sources" tab and try adding some texts from the "txt" directory.""")


    def __init__(self, *args):
        super(TextManager, self).__init__(*args)

        self.model = SourceModel()
        tv = AmphTree(self.model)
        tv.resizeColumnToContents(1)
        tv.setColumnWidth(0, 300)
        self.connect(tv, SIGNAL("doubleClicked(QModelIndex)"), self.doubleClicked)
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

        qf = QFileDialog(self, "Import Text From File(s)")
        qf.setFilters(["UTF-8 text files (*.txt)", "All files (*)"])
        qf.setFileMode(QFileDialog.ExistingFiles)
        qf.setAcceptMode(QFileDialog.AcceptOpen)

        self.connect(qf, SIGNAL("filesSelected(QStringList)"), self.setImpList)

        qf.show()

    def setImpList(self, files):
        self.sender().hide()
        #self.progress.show()
        for x in map(unicode, files):
            #self.progress.setValue(0)
            fname = path.basename(x)
            # Import one word per line,
            #  optionally tab delimited with stroke following
            words = [ line.split('\t')[0].strip() for line in
                       codecs.open(x, "r", "utf_8_sig") ]
            #self.connect(lm, SIGNAL("progress(int)"), self.progress.setValue)
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
            except Exception, e:
                pass # silently skip ...
        if update:
            self.update()
        return r

    def update(self):
        self.emit(SIGNAL("refreshSources"))
        self.model.reset()

    def nextText(self):
        num_words = Settings.get('num_rand')
        # Fetch random words
        v = DB.execute("select id,source,text from text where disabled is null order by random() limit %d" % num_words).fetchall()
        if len(v) == 0:
            v = self.defaultText
        else:
            v = ('', 0, ' '.join([ row[2] for row in v ]))
        self.emit(SIGNAL("setText"), v)

    def removeUnused(self):
        DB.execute('''
            delete from source where rowid in (
                select s.rowid from source as s
                    left join result as r on (s.rowid=r.source)
                    left join text as t on (t.source=s.rowid)
                group by s.rowid
                having count(r.rowid) = 0 and count(t.rowid) = 0
            )''')
        DB.execute('''
            update source set disabled = 1 where rowid in (
                select s.rowid from source as s
                    left join result as r on (s.rowid=r.source)
                    left join text as t on (t.source=s.rowid)
                group by s.rowid
                having count(r.rowid) > 0 and count(t.rowid) = 0
            )''')
        self.emit(SIGNAL("refreshSources"))

    def removeDisabled(self):
        DB.execute('delete from text where disabled is not null')
        self.removeUnused()
        self.update()
        DB.commit()

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

        self.cur = v[0] if len(v) > 0 else self.defaultText
        self.emit(SIGNAL("setText"), self.cur)
        self.emit(SIGNAL("gotoText"))



