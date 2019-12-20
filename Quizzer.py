# -*- coding: UTF-8 -*-

from __future__ import with_statement, division


#import psyco
import platform
import collections
import time
import re

from Data import Statistic, DB
from Config import Settings

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from QtUtil import *


if platform.system() == "Windows":
    # hack hack, hackity hack
    timer = time.clock
    timer()
else:
    timer = time.time


class Typer(QTextEdit):
    def __init__(self, *args):
        super(Typer, self).__init__(*args)

        self.setPalettes()

        self.connect(self, SIGNAL("textChanged()"), self.checkText)
        #self.setLineWrapMode(QTextEdit.NoWrap)
        self.connect(Settings, SIGNAL("change_quiz_wrong_fg"), self.setPalettes)
        self.connect(Settings, SIGNAL("change_quiz_wrong_bg"), self.setPalettes)
        self.connect(Settings, SIGNAL("change_quiz_right_fg"), self.setPalettes)
        self.connect(Settings, SIGNAL("change_quiz_right_bg"), self.setPalettes)
        self.target = None

    def sizeHint(self):
        return QSize(600, 10)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.emit(SIGNAL("cancel"))
        return QTextEdit.keyPressEvent(self, e)

    def setPalettes(self):
        self.palettes = {
            'wrong': QPalette(Qt.black,
                Qt.lightGray, Qt.lightGray, Qt.darkGray, Qt.gray,
                Settings.getColor("quiz_wrong_fg"), Qt.white, Settings.getColor("quiz_wrong_bg"), Qt.yellow),
            'right': QPalette(Qt.black,
                Qt.lightGray, Qt.lightGray, Qt.darkGray, Qt.gray,
                Settings.getColor("quiz_right_fg"), Qt.yellow, Settings.getColor("quiz_right_bg"), Qt.yellow),
            'inactive': QPalette(Qt.black, Qt.lightGray, Qt.lightGray, Qt.darkGray,
                                 Qt.gray, Qt.black, Qt.lightGray)}
        self.setPalette(self.palettes['inactive'])

    def setTarget(self,  text):
        self.editflag = True
        self.target = text
        self.when = [0] * (len(self.target)+1)
        self.times = [0] * len(self.target)
        self.mistake = [False] * len(self.target)
        self.mistakes = {} #collections.defaultdict(lambda: [])
        self.where = 0
        self.clear()
        self.setPalette(self.palettes['inactive'])
        self.setText(self.getWaitText())
        self.selectAll()
        self.editflag = False

    def getWaitText(self):
        if Settings.get('req_space'):
            return "Press SPACE and then immediately start typing the text\n" + \
                    "Press ESCAPE to restart with a new text at any time"
        else:
            return "Press ESCAPE to restart with a new text at any time"

    def checkText(self):
        if self.target is None or self.editflag:
            return

        v = unicode(self.toPlainText())
        if self.when[0] == 0:
            space = len(v) > 0 and v[-1] == u" "
            req = Settings.get('req_space')

            self.editflag = True
            if space:
                self.when[0] = timer()
                self.clear()
                self.setPalette(self.palettes['right'])
            elif req:
                self.setText(self.getWaitText())
                self.selectAll()
            self.editflag = False

            if req or space:
                return
            else:
                self.when[0] = -1

        y = 0
        for y in xrange(min(len(v), len(self.target)), -1, -1):
            if v[0:y] == self.target[0:y]:
                break
        lcd = v[0:y]
        self.where = y

        if self.when[y] == 0 and y == len(v):
            self.when[y] = timer()
            if y > 0:
                self.times[y-1] = self.when[y] - self.when[y-1]

        if lcd == self.target:
            self.emit(SIGNAL("done"))
            return

        if y < len(v) and y < len(self.target):
            self.mistake[y] = True
            self.mistakes[y] = self.target[y] + v[y]

        if v == lcd:
            self.setPalette(self.palettes['right'])
        else:
            self.setPalette(self.palettes['wrong'])

    def getMistakes(self):
        inv = collections.defaultdict(lambda: 0)
        for p, m in self.mistakes.iteritems():
            inv[m] += 1
        return inv

    def getStats(self):
        return self.when[self.where]-self.when[0], self.where, self.times, self.mistake, self.getMistakes()

class Quizzer(QWidget):
    def __init__(self, *args):
        super(Quizzer, self).__init__(*args)
        
        self.result = QLabel()
        self.typer = Typer()
        self.label = WWLabel()
        #self.label.setFrameStyle(QFrame.Raised | QFrame.StyledPanel)
        #self.typer.setBuddy(self.label)
        #self.info = QLabel()
        self.connect(self.typer,  SIGNAL("done"), self.done)
        self.connect(self.typer,  SIGNAL("cancel"), self.resetStats)
        self.connect(Settings, SIGNAL("change_typer_font"), self.readjust)

        self.text = ('','', 0, None)

        layout = QVBoxLayout()
        #layout.addWidget(self.info)
        #layout.addSpacing(20)
        layout.addWidget(self.result, 0, Qt.AlignRight)
        layout.addWidget(self.label, 1, Qt.AlignBottom)
        layout.addWidget(self.typer, 1)
        self.setLayout(layout)
        self.readjust()
        self.resetStats()

    def resetStats(self):
        self.wpm_num = 0
        self.wpm_denom = 0
        self.acc_num = 0
        self.acc_denom = 0
        self.result.setText('')
    
    def readjust(self):
        f = Settings.getFont("typer_font")
        self.label.setFont(f)
        self.typer.setFont(f)

    def setText(self, text):
        self.text = text
        self.label.setText(self.text[2].replace(u"\n", u"↵\n"))
        self.typer.setTarget(self.text[2])
        self.typer.setFocus()

    def done(self):
        now = time.time()
        elapsed, chars, times, mis, mistakes = self.typer.getStats()

        assert chars == len(self.text[2])

        accuracy = 1.0 - len(filter(None, mis)) / chars
        spc = elapsed / chars

        self.wpm_num += chars / 5.0
        self.wpm_denom += elapsed / 60.
        self.acc_num += chars - len(filter(None, mis))
        self.acc_denom += chars
        self.result.setText("Speed: %.1fwpm\tAccuracy: %.1f%%" %
                            (self.wpm_num / self.wpm_denom,
                             100. * self.acc_num / self.acc_denom))

        self.emit(SIGNAL("statsChanged"))

        stats = collections.defaultdict(Statistic)
        text = self.text[2]

        def gen_tup(s, e):
            perch = sum(times[s:e])/(e-s)
            return (text[s:e], perch, len(filter(None, mis[s:e])) )

        regex = re.compile(r"(\w|'(?![A-Z]))+(-\w(\w|')*)*")

        for w, t, m in [gen_tup(*x.span()) for x in regex.finditer(text)]:
            stats[w].append(t, m > 0)

        vals = []
        for k, s in stats.iteritems():
            vals.append( (s.median(), now, len(s), s.flawed(), k) )

        DB.executemany_('''insert into statistic
            (time,w,count,mistakes,data) values (?,?,?,?,?)''', vals)
        
        self.emit(SIGNAL("wantText"))

